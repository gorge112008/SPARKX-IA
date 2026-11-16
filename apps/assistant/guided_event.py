"""Human-guided local steps. Navigation/prefill never saves or invokes a model."""
from datetime import date, timedelta
import hashlib
import json
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from apps.directory.queries import exact_directory_matches, organizations_for, people_for, suggested_directory_matches
from apps.events.forms import EventEditForm
from apps.events.interview import QUESTIONS
from apps.events.models import Event
from apps.events.services import require_event_owner
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate
from .creation_language import clean_text, parse_time
from .date_language import parse_scheduled_dates
from .event_creation import _directory_confirmation, _directory_answer_only, _duration_minutes, _key
from .local_commands import human_organizer
from .models import EventCreationDraft
from . import social_language

VERSION = 1
STATE_KEY = "_guided_v1"
ACTIONS = frozenset({"open_event", "open_agenda", "open_preparation", "open_calendar", "open_generate", "open_approval",
    "open_edit_speaker", "open_schedule", "open_organization_create", "open_speaker_create"})
STEPS = frozenset({"overview", "event", "agenda", "preparation", "calendar", "generate", "approval", "speaker", "schedule", "organization", "speaker_create", "waiting"})
WAITING = frozenset({"", "date", "time", "organization", "speaker", *(question.key for question in QUESTIONS)})
CHANGE = {"cambiar", "cambia", "cambio", "cambiemos", "modificar", "modifica", "ajustar", "ajusta", "reemplazar", "reemplaza", "sustituir", "sustituye", "editar", "edita", "corregir", "corrige"}
CREATE = {"crear", "crea", "creemos", "creame", "registrar", "registra", "registrame", "agregar", "agrega", "añadir", "anadir"}
GENERATE = {"generar", "genera", "generame", "crear", "crea", "preparar", "prepara", "preparame", "armar", "arma", "hacer", "haz", "construir", "construye", "planificar", "planifica"}


def _intent(text):
    words = set(_key(text).split())
    if not words or re.search('["“”«»]', text) or words & {"dijo", "dijeron", "comentaron", "simular"}:
        return None
    if words & {"no", "nunca", "tampoco", "cancelar", "cancela"}:
        return "cancel"
    if "estado" in words or {"que", "falta"} <= words or {"donde", "quedamos"} <= words:
        return "overview"
    org = bool(words & {"institucion", "instituciones", "empresa", "empresas", "organizacion", "organizaciones"})
    speaker = bool(words & {"expositor", "expositores", "expositora", "ponente", "ponentes", "asesor"})
    if org and words & CREATE:
        return "organization"
    if speaker and words & CREATE:
        return "speaker_create"
    if speaker and words & CHANGE:
        return "speaker"
    if words & {"hora", "horas", "horario", "horarios", "fecha", "fechas"} and words & CHANGE:
        return "schedule"
    if any(word.startswith("aprob") for word in words):
        return "approval"
    if words & {"calendario", "calendarios"}:
        return "calendar"
    if words & {"agenda", "agendas", "propuesta", "propuestas", "plan", "planes"}:
        return "generate" if words & GENERATE else "approval" if words & {"propuesta", "propuestas"} else "agenda"
    if words & {"preparacion", "tarea", "tareas"}:
        return "preparation"
    if words & {"siguiente", "continuar", "continua", "continuemos", "seguimos", "sigamos", "listo", "guardado", "guarde"} or {"que", "sigue"} <= words:
        return "next"
    if words & {"evento", "eventos", "ficha"} and not words & (CREATE | {"buscar", "busca", "buscame"}):
        return "event"
    return None


def _state(value):
    empty = {"v": VERSION, "step": "overview", "waiting": "", "choice_ids": [], "event_revision": 0}
    if (type(value) is not dict or set(value) != set(empty) or type(value.get("v")) is not int or value.get("v") != VERSION
            or type(value.get("step")) is not str or value["step"] not in STEPS
            or type(value.get("waiting")) is not str or value["waiting"] not in WAITING
            or type(value.get("event_revision")) is not int or value["event_revision"] < 0
            or type(value.get("choice_ids")) is not list or len(value["choice_ids"]) > 3):
        return empty
    try:
        if any(type(item) is not str or str(uuid.UUID(item)) != item for item in value["choice_ids"]):
            raise ValueError
    except (ValueError, TypeError):
        return empty
    return dict(value)


def _reply(event=None, *, status="info", reply="", step="overview", action=None, url=None, **extra):
    result = {"handled": True, "status": status, "reply": reply[:300], "step": step,
        "event_id": str(event.pk) if event else "", "event_revision": event.revision if event else 0,
        "draft_id": "", "revision": 0, "awaiting": ""}
    if action is not None:
        if action not in ACTIONS or not isinstance(url, str) or not url.startswith("/") or url.startswith("//"):
            raise ValidationError("La acción guiada no está disponible.")
        result.update(action=action, url=url)
    result.update(extra)
    return result


def _route(event, step, text, **extra):
    detail = reverse("events:detail", args=[event.pk])
    routes = {"event": ("open_event", detail), "agenda": ("open_agenda", detail + "#agenda"),
        "preparation": ("open_preparation", reverse("events:preparation", args=[event.pk])),
        "calendar": ("open_calendar", reverse("events:calendar")), "generate": ("open_generate", detail + "#proposal-form"),
        "approval": ("open_approval", detail + "#candidate"), "speaker": ("open_edit_speaker", reverse("events:edit", args=[event.pk])),
        "schedule": ("open_schedule", reverse("events:schedule_editor", args=[event.pk]))}
    action, url = routes[step]
    return _reply(event, status="ready", reply=text, step=step, action=action, url=url, **extra)


def _directory_route(event, kind, *, name=""):
    values = ({"name": name} if name else {}) if kind == "organization" else {"category": "speaker", **({"full_name": name} if name else {})}
    if kind != "organization" and event and event.organization_id and organizations_for(event.owner).filter(pk=event.organization_id, is_active=True).exists():
        values["organization"] = str(event.organization_id)
    return _reply(event, status="ready", step=kind, action="open_organization_create" if kind == "organization" else "open_speaker_create",
        url=reverse("directory:organization_create" if kind == "organization" else "directory:person_create"), field_values=values,
        reply=("Completa el nombre de la institución; las siglas son opcionales. Revisa y pulsa Guardar para registrarla."
            if kind == "organization" else "Completa el nombre del expositor y elige su institución. El correo es opcional. Revisa y pulsa Guardar para registrarlo."))


def _validated_patch(event, actor, values):
    form = EventEditForm(actor=actor, instance=event)
    form = EventEditForm({**form.initial, **values, "expected_revision": event.revision}, actor=actor, instance=event)
    if not form.is_valid():
        raise ValidationError("Ese dato todavía no es válido para la ficha. Revísalo en el formulario antes de guardarlo.")
    return values


def _missing(event):
    if not event.starts_at:
        return "time" if event.scheduled_dates else "date"
    for question in QUESTIONS:
        answer = event.interview_answers.get(question.key, {})
        if answer.get("status") != "confirmed" or not answer.get("value"):
            return question.key
    own = people_for(event.owner).filter(is_active=True, category="speaker")
    if not event.directory_people.filter(role="speaker", status__in=["planned", "confirmed"], person__in=own).exists():
        return "speaker"
    return ""


def _question(field):
    prompts = {"date": "¿Qué día será el evento? Puedes indicar día, mes y año.", "time": "¿A qué hora comienza? Por ejemplo, 19:30.",
        "organization": "¿Qué institución quieres asignar? Dime su nombre o sigla.", "speaker": "¿Quién será el expositor? Dime su nombre o elige uno de tu directorio."}
    prompts.update({question.key: question.prompt for question in QUESTIONS})
    return prompts[field]


def _ask(event, state, field):
    state.update(step="speaker" if field == "speaker" else "generate", waiting=field, choice_ids=[])
    return _reply(event, status="clarify", reply=_question(field), step=state["step"])


def _repeat_question(event, actor, state, prefix=""):
    """A courtesy or status request never fills or abandons a pending slot."""
    extra = {}
    if state["waiting"] in {"speaker", "organization"} and state["choice_ids"]:
        organization = state["waiting"] == "organization"
        source = organizations_for(actor) if organization else people_for(actor).filter(category="speaker")
        available = {str(item.pk): item for item in source.filter(is_active=True, pk__in=state["choice_ids"])}
        options = [available[key] for key in state["choice_ids"] if key in available]
        if options:
            extra["choices"] = [{"value": str(item.pk), "label": item.name if organization else item.full_name} for item in options]
    return _reply(event, status="clarify", reply=(prefix + " " if prefix else "") + _question(state["waiting"]), step=state["step"], **extra)


def _overview(event, actor, state):
    if state["waiting"]:
        return _repeat_question(event, actor, state, "Seguimos en este dato.")
    state.update(step="overview", choice_ids=[])
    if event.jobs.filter(status__in=[Job.Status.QUEUED, Job.Status.RUNNING]).exists():
        text = "Hay una solicitud en curso. Puedes abrir el evento para consultar su estado; no he iniciado otra."
    elif event.candidates.filter(status="pending", base_revision=event.revision, base_plan_id=event.active_plan_id, created_by=actor).exists():
        text = "Tienes una propuesta vigente pendiente de revisión. Puedes pedirme revisar la propuesta; sólo tu clic puede aprobarla."
    elif event.active_plan_id:
        text = "Tu agenda está aprobada. Podemos revisar la agenda, preparación o calendario, o preparar un cambio de expositor u horario."
    else:
        missing = _missing(event)
        if missing:
            return _ask(event, state, missing)
        text = "La ficha tiene los datos para preparar la propuesta. Puedes pedirme preparar la agenda y revisar sus opciones; no se ha iniciado ninguna llamada."
    return _reply(event, reply=text, step="overview")


def _answer(event, actor, state, text):
    field = state["waiting"]
    if field in {"organization", "speaker"}:
        kind = "organization" if field == "organization" else "person"
        source = organizations_for(actor) if field == "organization" else people_for(actor).filter(category="speaker")
        source = source.filter(is_active=True)
        available = {str(item.pk): item for item in source.filter(pk__in=state["choice_ids"])}
        choices = [available[key] for key in state["choice_ids"] if key in available]
        selected = next((item for item in choices if str(item.pk) == text or _key(item.name if kind == "organization" else item.full_name) == _key(text)), None)
        if selected is None and choices:
            confirmation = _directory_confirmation(text)
            if confirmation is True and len(choices) == 1:
                selected = choices[0]
            elif re.fullmatch("[1-3]", text) and int(text) <= len(choices):
                selected = choices[int(text) - 1]
            elif confirmation is False:
                state["choice_ids"] = []
                return _reply(event, status="clarify", reply="Dime otro nombre o utiliza el registro del directorio.", step=state["step"])
        if selected is None and _directory_answer_only(text):
            return _reply(event, status="clarify", reply="Necesito el nombre, una opción concreta o cancelar esta elección.", step=state["step"])
        if selected is None:
            name = clean_text(text, max_length=160)
            exact = exact_directory_matches(actor, name, kind=kind).filter(is_active=True)
            if kind == "person":
                exact = exact.filter(category="speaker")
            matches = list(exact[:4])
            if len(matches) == 1:
                selected = matches[0]
            else:
                suggested = suggested_directory_matches(actor, name, kind=kind).filter(is_active=True)
                if kind == "person":
                    suggested = suggested.filter(category="speaker")
                suggestions = matches[:3] or list(suggested[:3])
                if suggestions:
                    state["choice_ids"] = [str(item.pk) for item in suggestions]
                    return _reply(event, status="clarify", step=state["step"], reply="¿Te refieres a una de estas opciones? Elige su nombre o número; también puedes decir no.",
                        choices=[{"value": str(item.pk), "label": item.name if kind == "organization" else item.full_name} for item in suggestions])
                return _directory_route(event, "organization" if field == "organization" else "speaker_create", name=name)
        values = {"organization_id" if field == "organization" else "speaker_id": str(selected.pk)}
    elif field == "date":
        days = parse_scheduled_dates(text, reference_date=timezone.localdate())
        values = {"scheduled_dates": ", ".join(date.fromisoformat(day).strftime("%d/%m/%Y") for day in days)}
        if event.starts_at:
            from zoneinfo import ZoneInfo
            values["starts_at"] = days[0] + "T" + event.starts_at.astimezone(ZoneInfo(event.timezone)).strftime("%H:%M")
    elif field == "time":
        values = {"starts_at": event.scheduled_dates[0] + "T" + parse_time(text)}
    else:
        values = {field: _duration_minutes(text) if field == "duration_minutes" else clean_text(text, max_length=300)}
    values = _validated_patch(event, actor, values)
    state.update(waiting="", choice_ids=[])
    return _reply(event, status="ready", reply="Preparé ese dato en el formulario. Revísalo y pulsa Guardar; todavía no he cambiado el evento.",
        step=state["step"], action="open_edit_speaker" if field == "speaker" else "open_event",
        url=reverse("events:edit", args=[event.pk]), field_values=values)


def _resolve(event, actor, state, text):
    intent = _intent(text)
    if state["waiting"] in {"organization", "speaker"} and _directory_answer_only(text):
        return _answer(event, actor, state, text)
    if state["waiting"] and intent is None:
        social = social_language.resolve(text)
        if social and social["kind"] in {"greeting", "courtesy", "person_greeting", "wellbeing", "farewell"}:
            return _repeat_question(event, actor, state, social["reply"])
    if intent == "cancel":
        state.update(step="overview", waiting="", choice_ids=[])
        return _reply(event, reply="De acuerdo. No cambiaré el evento. Cuando quieras, dime qué paso deseas revisar.")
    if intent == "overview":
        return _overview(event, actor, state)
    if state["waiting"] and intent is None and text:
        return _answer(event, actor, state, text)
    if intent in {"organization", "speaker_create"}:
        state.update(step=intent, waiting="", choice_ids=[])
        return _directory_route(event, intent)
    if intent is None and text:
        return _reply(event, status="clarify", handled=False, reply="Puedo ayudarte con la agenda, preparación, calendario, expositor u horarios. ¿Qué paso quieres hacer?", step=state["step"])
    if intent in {None, "next"}:
        if event.jobs.filter(status__in=[Job.Status.QUEUED, Job.Status.RUNNING]).exists():
            state.update(step="waiting", waiting="", choice_ids=[])
            return _route(event, "event", "Hay una solicitud en curso. Abro el evento para ver su estado; no iniciaré otra.")
        candidate = event.candidates.filter(status="pending", base_revision=event.revision, base_plan_id=event.active_plan_id, created_by=actor).order_by("-created_at").first()
        intent = "approval" if candidate else "generate" if not event.active_plan_id else "agenda"
    state.update(step=intent, waiting="", choice_ids=[])
    if intent == "generate":
        missing = _missing(event)
        if missing:
            return _ask(event, state, missing)
        from .demo_pilot import PILOT_EVENT_ID
        if not event.is_synthetic and event.pk != PILOT_EVENT_ID:
            return _route(event, "generate", "La IA real de este prototipo está acotada al piloto autorizado. Abro las opciones de propuesta; configurar un perfil humano no amplía ese alcance.")
        return _route(event, "generate", "Abro la preparación de propuesta. Revisa perfil, presupuesto y prompt; la generación se inicia sólo desde su control habitual.")
    if intent == "approval":
        candidate = event.candidates.filter(status=PlanCandidate.Status.PENDING, base_revision=event.revision,
            base_plan_id=event.active_plan_id, created_by=actor).order_by("-created_at").first()
        if candidate is None:
            return _reply(event, status="clarify", reply="No hay una propuesta vigente para aprobar. Puedes preparar una nueva y revisarla primero.", step=intent)
        return _route(event, "approval", "Abro esta propuesta exacta para que la revises. Sólo tu clic en Aprobar puede aplicar el plan.", candidate_id=str(candidate.pk))
    if intent == "speaker":
        return _ask(event, state, "speaker")
    if intent in {"agenda", "preparation", "schedule"} and not event.active_plan_id:
        return _reply(event, status="clarify", reply="Primero necesitamos preparar y aprobar una agenda. Puedes pedirme preparar la propuesta.", step=intent)
    messages = {"event": "Abro la ficha del evento.", "agenda": "Abro la agenda aprobada.", "preparation": "Abro la preparación. Los cambios de tareas necesitan tu confirmación.",
        "calendar": "Abro el calendario para localizar tu evento.", "schedule": "Abro el editor de horarios. Guardar prepara una propuesta; después debes revisarla y aprobarla."}
    return _route(event, intent, messages[intent])


@transaction.atomic
def guided_turn(actor, text="", *, event_id=None, draft_id=None, expected_revision=0, request_id):
    """Only private guide metadata is persisted, never an Event or model action."""
    actor = human_organizer(actor)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("Envía una revisión válida de la guía.")
    if not draft_id and expected_revision != 0:
        raise ValidationError("Comienza la guía con revisión 0.")
    try:
        request_id = uuid.UUID(str(request_id))
        identifier = uuid.UUID(str(draft_id)) if draft_id else None
        event_id = uuid.UUID(str(event_id)) if event_id else None
        text = clean_text(text, max_length=300) if text else ""
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Revisa el texto y los identificadores de la guía.") from None
    source = EventCreationDraft.objects.filter(pk=identifier, owner=actor).first() if identifier else None
    if identifier and source is None:
        raise Http404("Guía no disponible.")
    if source is not None and source.event_id is None:
        if event_id is None:
            return _reply(handled=False, reply="Puedes continuar la creación que ya está abierta; no cambié tu borrador.")
        raise ValidationError("Completa y confirma el borrador antes de continuar la guía del evento.")
    if source and source.event_id:
        if event_id is not None and event_id != source.event_id:
            raise ValidationError("La guía pertenece a otro evento.")
        event_id = source.event_id
    if event_id is None:
        intent = _intent(text)
        if intent in {"organization", "speaker_create"}:
            return _directory_route(None, intent)
        return _reply(status="clarify", handled=False, reply="Abre el evento que quieres trabajar o dime crear evento. También puedo abrir el registro de institución o expositor.", step="overview")
    try:
        event = Event.objects.select_for_update().get(pk=event_id)
    except Event.DoesNotExist:
        raise Http404("Evento no disponible.") from None
    require_event_owner(event, actor)
    actor = human_organizer(actor, lock=True)
    require_event_owner(event, actor)
    draft = EventCreationDraft.objects.select_for_update().filter(owner=actor, event=event).first()
    if draft is None:
        if identifier:
            raise ValidationError("Este borrador todavía no tiene un evento creado.")
        draft = EventCreationDraft.objects.create(owner=actor, event=event, status="created", step="", data={}, expires_at=timezone.now() + timedelta(hours=24))
    digest = hashlib.sha256(json.dumps({"operation": "guide", "text": text, "revision": expected_revision, "event": str(event.pk)}, sort_keys=True).encode()).hexdigest()
    if draft.last_request_id == request_id:
        if draft.last_request_hash == digest:
            if draft.last_response.get("event_revision") != event.revision:
                return _reply(event, status="conflict", reply="El evento cambió. Repite tu orden para usar su ficha actual.", draft_id=str(draft.pk), revision=draft.revision)
            return draft.last_response
        return _reply(event, status="conflict", reply="Esta solicitud ya se usó para otra respuesta.", draft_id=str(draft.pk), revision=draft.revision)
    if identifier is not None and expected_revision != draft.revision:
        return _reply(event, status="conflict", reply="La guía cambió en otra pestaña. Revisa el paso actual antes de continuar.", draft_id=str(draft.pk), revision=draft.revision)
    state = _state(draft.data.get(STATE_KEY))
    if state["waiting"] and state["event_revision"] != event.revision:
        state.update(waiting="", choice_ids=[], step="overview")
        result = _reply(event, status="clarify", reply="La ficha cambió mientras conversábamos. Dime qué paso quieres continuar; usaré sus datos actuales.")
    else:
        try:
            result = _resolve(event, actor, state, text)
        except (ValueError, ValidationError, IndexError):
            result = _reply(event, status="clarify", step=state["step"], reply="No pude validar ese dato. Repite sólo el dato solicitado o usa el formulario para revisarlo.")
    state["event_revision"] = event.revision
    draft.data = {**draft.data, STATE_KEY: _state(state)}
    draft.revision += 1
    result.update(draft_id=str(draft.pk), revision=draft.revision, awaiting=state["waiting"])
    draft.last_request_id, draft.last_request_hash, draft.last_response = request_id, digest, result
    draft.save(update_fields=["data", "revision", "last_request_id", "last_request_hash", "last_response", "updated_at"])
    return result
