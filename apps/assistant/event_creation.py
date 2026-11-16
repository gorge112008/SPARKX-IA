"""Owner-private event interview. Local validation only; explicit final creation.

User rows serialize mutations in PostgreSQL. Revision checks also reject stale
tabs, and request identities make the latest delivery replayable without effects.
SQLite tests exercise the protocol, not PostgreSQL's concurrent row locks.
"""

from datetime import timedelta
import hashlib
import json
import re
import unicodedata
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from apps.directory.queries import exact_directory_matches, organizations_for, people_for, suggested_directory_matches
from apps.directory.services import assign_person, upsert_organization, upsert_person
from apps.events.forms import EventForm
from apps.events.interview import QUESTIONS, QUESTION_BY_KEY, normalize_interview_answers
from apps.events.models import validate_timezone
from apps.events.schedule_dates import normalize_scheduled_dates
from apps.events.services import create_event

from .creation_language import clean_text, is_creation_request, parse_bool, parse_integer, parse_time
from .date_language import DateYearRequired, parse_scheduled_dates, spoken_dates, year_question
from .local_commands import human_organizer
from .models import EventCreationDraft


BASE_STEPS = (
    ("title", "Nombre del evento", "¡Vamos a crearlo! ¿Cómo se llamará tu evento?"),
    ("organization", "Institución", "¿Qué institución organiza el evento? Dime su nombre, una sigla o «sin institución»."),
    ("brief", "Descripción", "Cuéntame brevemente de qué trata el evento y qué deseas conseguir."),
    ("date", "Fechas", "¿Qué días será? Puedes decir «5, 6 y 7 de septiembre de 2026», «del 5 al 9 de septiembre de 2026» o «pendiente»."),
    ("time", "Hora", "¿A qué hora comienza? Por ejemplo, 19:30 o 7:30 p. m. También puedes decir «pendiente»."),
    ("timezone", "Zona horaria", "¿Usamos la hora de Perú, America/Lima? Di «sí» o indica otra zona IANA, por ejemplo Europe/Madrid."),
    ("capacity", "Capacidad", "¿Cuántas personas esperas? Indica una cantidad entre 1 y 100000."),
    ("is_synthetic", "Tipo de datos", "¿Es un evento de demostración con datos ficticios? Responde sí o no."),
)
STEPS = BASE_STEPS + tuple((q.key, q.label, ("¿Con qué expositores, invitados y recursos cuentas? Para vincular una persona, di su nombre registrado, «el expositor es nombre» o «el invitado es nombre»." if q.key == "resources" else q.prompt) + " Puedes decir «pendiente».") for q in QUESTIONS)
STEP_KEYS = tuple(item[0] for item in STEPS)
STEP_BY_KEY = {item[0]: item for item in STEPS}
ACTIVE = (EventCreationDraft.Status.COLLECTING, EventCreationDraft.Status.REVIEW)
ALLOWED_OPERATIONS = {"turn", "resume", "back", "cancel", "review", "edit", "confirm"}
PENDING = {"pendiente", "por definir", "no se", "no lo se", "aun no se", "omitir", "saltar"}
CONFIRMATIONS = {"crear evento", "si crear evento", "crear el evento", "si crear el evento"}
DIRECTORY_NO = {"omitir", "saltar", "sin institucion", "sin institucion asignada", "sin registrar", "sin persona"}


def _key(text):
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(
        ch for ch in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(ch)
    )).split())


def _blank():
    return {"handled": False, "status": "none", "draft_status": "none", "reply": "", "question": "",
            "draft_id": "", "revision": 0, "step_key": "", "label": "", "index": 0,
            "total": len(STEPS), "fields": {}, "directory_resolution": None, "event_url": "", "error_code": ""}


def _response(draft, *, reply=None, error_code="", status=None):
    values = {key: value for key, value in draft.data.items() if not key.startswith("_")}
    step = STEP_BY_KEY.get(draft.step)
    if reply is None:
        if draft.status == "review":
            reply = "Ya completamos la ficha. Revisa los datos y di «crear evento» o pulsa Crear evento. Puedes corregir cualquier campo antes."
        elif draft.status == "created":
            reply = "Tu evento está creado. Ahora puedes revisar la ficha y preparar una propuesta de plan; todavía no he generado ni aprobado ningún plan."
        elif draft.status == "cancelled":
            reply = "Cancelé este borrador. Cuando quieras, podemos comenzar otro evento."
        else:
            if draft.data.get("_directory_resolution", {}).get("step") == draft.step:
                reply = _directory_question(_safe_pending(draft.data["_directory_resolution"], draft.owner))
            elif draft.step == "date" and draft.data.get("_pending_date_year"):
                reply = year_question(draft.data["_pending_date_year"], timezone.localdate().year)
            else:
                reply = step[2] if step else "Revisa los datos del borrador."
                if draft.step == "date":
                    reply = reply.replace("2026", str(timezone.localdate().year))
    return {"handled": True, "status": status or draft.status, "draft_status": draft.status,
            "reply": reply[:280], "question": reply[:280], "draft_id": str(draft.pk),
            "revision": draft.revision, "step_key": draft.step, "label": step[1] if step else "Resumen",
            "index": STEP_KEYS.index(draft.step) + 1 if draft.step in STEP_KEYS else len(STEPS),
            "total": len(STEPS), "fields": values, "directory_resolution": _directory_presentation(draft),
            "event_url": reverse("events:detail", args=[draft.event_id]) if draft.event_id else "",
            "error_code": error_code}


def _directory_question(pending):
    noun = "institución" if pending["kind"] == "organization" else "persona"
    if pending["mode"] == "new_name":
        return f"¿Qué {noun} deseas buscar o registrar? Dime su nombre."
    if pending["mode"] == "choose":
        if len(pending["candidates"]) == 1:
            name = pending["candidates"][0]["name"][:65]
            return f"¿Te refieres a «{name}»? Elige la opción o responde sí o no."
        return "Hay varias coincidencias. Elige una opción o di su número. Puedes decir «otra» o «no»."
    name = pending["name"][:55] + ("…" if len(pending["name"]) > 55 else "")
    return f"No encuentro «{name}». ¿Quieres registrar esta {noun}? Responde sí o no."


def _instruction_echo(value):
    """Prompt fragments are never names or registration consent."""
    words = set(_key(value).split())
    return any(pattern <= words for pattern in (
        {"indica", "otro", "nombre"}, {"di", "si", "no"}, {"responde", "si", "no"},
        {"continuar", "sin", "hacerlo"}, {"quieres", "registrar", "institucion"},
        {"quieres", "registrar", "persona"}, {"no", "encuentro", "directorio"},
        {"hay", "varias", "coincidencias"}, {"elige", "opcion", "numero"},
        {"dime", "nombre", "registrar"}, {"te", "refieres", "responde"},
        {"que", "institucion", "dime", "nombre"},
    ))


def _safe_pending(pending, actor):
    """Recover a historical prompt-as-name without accepting or creating it."""
    if _instruction_echo(pending.get("name", "")):
        return {**pending, "mode": "new_name", "name": "", "candidates": [], "resource_value": ""}
    if pending.get("mode") == "choose":
        candidates = pending.get("candidates", [])[:3]
        source = organizations_for(actor) if pending["kind"] == "organization" else people_for(actor)
        live = {str(item.pk): item for item in source.filter(is_active=True, pk__in=[item["id"] for item in candidates])}
        if any(item["id"] not in live or _key(item["name"]) != _key(
            live[item["id"]].name if pending["kind"] == "organization" else live[item["id"]].full_name
        ) for item in candidates) or not candidates:
            return {**pending, "mode": "new_name", "name": "", "candidates": []}
        return {**pending, "candidates": candidates}
    return pending


def _directory_presentation(draft):
    pending = draft.data.get("_directory_resolution")
    if draft.status != "collecting" or not pending or pending.get("step") != draft.step:
        return None
    pending = _safe_pending(pending, draft.owner)
    return {"kind": pending["kind"], "mode": pending["mode"], "query": pending["name"],
            "candidates": pending["candidates"][:3], "can_skip": True}


def _directory_confirmation(value):
    """Independent yes/no concepts, only inside a directory confirmation."""
    folded = _key(value)
    words = set(folded.split())
    positive = bool(words & {"si", "afirmativo", "claro", "correcto"}) or {"de", "acuerdo"} <= words
    negative = bool(words & {"no", "negativo"}) or folded in DIRECTORY_NO
    uncertain = bool(words & {"quizas", "quiza", "depende", "recuerdo"}) or any(
        pattern <= words for pattern in ({"no", "se"}, {"no", "entiendo"}, {"no", "seguro"}, {"tal", "vez"})
    )
    if positive == negative or uncertain or _instruction_echo(value):
        return None
    return positive


def _directory_answer_only(value):
    """Courtesy around a Boolean isn't a name; nouns in names stay literal."""
    words = set(_key(value).split())
    vocabulary = {"si", "no", "afirmativo", "negativo", "claro", "correcto", "de", "acuerdo", "por", "favor",
                  "gracias", "muchas", "muchos", "bien", "esta", "eso", "perfecto", "bueno", "vale", "gica", "ok",
                  "mira", "estoy", "seguro", "se", "entiendo", "quizas", "quiza", "depende", "todavia", "aun"}
    return bool(words) and words <= vocabulary and (
        bool(words & {"si", "no", "afirmativo", "negativo", "claro", "correcto"}) or {"de", "acuerdo"} <= words
    )


def _another_directory_name(value):
    words = set(_key(value).split())
    return bool(words & {"otro", "otra", "nuevo", "nueva"}) and (
        words <= {"otro", "otra", "nuevo", "nueva", "nombre", "persona", "institucion"}
        or bool(words & {"registrar", "registra", "registre", "crear", "crea", "buscar", "busca"})
    )


def _person_declaration(value):
    """A singular direct declaration; descriptions/reports stay literal resources."""
    match = re.fullmatch(
        r"(?:(?:el|la|un|una)\s+)?(?P<role>expositor(?:a)?|ponente|invitad[oa])"
        r"(?:\s*:\s*|\s+(?:(?:es|ser[aá]|se\s+llama)\s+)?)"
        r"(?P<name>[^:;]+)", value, re.IGNORECASE,
    )
    if not match:
        return None
    name = match["name"].strip()
    if (re.search(r'["“”«»¿?]', name)
            or re.search(r"\b(?:no|nunca|tampoco|quizas|quiza|tal vez|si|dijo|dice|dijeron|comento|comentaron|fue|era|podria|seria|es|sera|se llama|y|o)\b", _key(name))):
        return None
    return name, "guest" if match["role"].casefold().startswith("invitad") else "speaker"


def _queue_directory(draft, data, *, kind, name, matches, role="speaker", resource_value=""):
    data["_directory_resolution"] = {"step": draft.step, "kind": kind, "name": name,
        "mode": "choose" if matches else "register", "role": role, "resource_value": resource_value,
        "candidates": [{"id": str(item.pk), "name": item.name if kind == "organization" else item.full_name}
                       for item in matches[:3]]}
    draft.data = data


def _store_directory(data, *, kind, record, role="speaker", resource_value=""):
    data.pop("_directory_resolution", None)
    if kind == "organization":
        data.update(organization_id=str(record.pk) if record else None, organization_name=record.name if record else "")
    else:
        data["directory_people"] = ([{"id": str(record.pk), "name": record.full_name, "role": role}] if record else [])
        data["interview_answers"] = normalize_interview_answers({**data.get("interview_answers", {}),
            "resources": {"status": "confirmed" if resource_value else "pending", "value": resource_value}})


def _resolve_directory_name(draft, actor, data, *, kind, name, role="speaker", resource_value=""):
    """Exact unique names link; every broader result waits for a human choice."""
    matches = list(exact_directory_matches(actor, name, kind=kind)[:4])
    if len(matches) == 1:
        _store_directory(data, kind=kind, record=matches[0], role=role, resource_value=resource_value)
        return True
    if not matches:
        matches = list(suggested_directory_matches(actor, name, kind=kind)[:3])
    _queue_directory(draft, data, kind=kind, name=name, matches=matches, role=role, resource_value=resource_value)
    return False


def _pending_directory_answer(draft, actor, data, value):
    """Unclear confirmations stay questions, never become replacement names."""
    pending = data.get("_directory_resolution")
    if not pending or pending.get("step") != draft.step:
        return False
    safe = _safe_pending(pending, actor)
    if safe != pending:
        data["_directory_resolution"] = safe
        return None
    if _instruction_echo(value):
        return None
    if pending["mode"] != "new_name":
        # Negation/conflict also governs a request containing "registrar otra".
        words = set(_key(value).split())
        explicit_name = pending["mode"] == "choose" and any(_key(item["name"]) == _key(value) for item in pending["candidates"][:3])
        if not explicit_name and {"si", "no"} <= words:
            return None
        if not explicit_name and _directory_confirmation(value) is False:
            _store_directory(data, kind=pending["kind"], record=None, role=pending["role"], resource_value=pending["resource_value"])
            return True
    if _another_directory_name(value):
        data["_directory_resolution"] = {**pending, "mode": "new_name", "name": "", "candidates": []}
        return None
    if pending["mode"] == "new_name":
        # This question asks for a name, not consent: don't reinterpret words in
        # proper names (for example, "Instituto del No") as a Boolean answer.
        only_answer = _directory_answer_only(value)
        confirmation = _directory_confirmation(value) if only_answer else None
        if confirmation is False or _key(value) in DIRECTORY_NO:
            _store_directory(data, kind=pending["kind"], record=None, role=pending["role"], resource_value=pending["resource_value"])
            return True
        if only_answer:
            return None
        name, role = value, pending["role"]
        if pending["kind"] == "person":
            declaration = _person_declaration(value)
            if declaration:
                name, role = declaration
        name = clean_text(name, max_length=160)
        return True if _resolve_directory_name(draft, actor, data, kind=pending["kind"], name=name,
            role=role, resource_value=value if pending["kind"] == "person" else "") else None
    confirmation = _directory_confirmation(value)
    if pending["mode"] == "choose":
        candidates = pending["candidates"][:3]
        selected = next((item for item in candidates if _key(item["name"]) == _key(value)), None)
        number = re.fullmatch(r"(?:(?:la\s+)?opcion\s+)?([1-3])", _key(value))
        if number and int(number[1]) <= len(candidates):
            selected = candidates[int(number[1]) - 1]
        elif confirmation is True and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            return None
        source = organizations_for(actor) if pending["kind"] == "organization" else people_for(actor)
        record = source.filter(pk=selected["id"], is_active=True).first()
        name = record.name if record and pending["kind"] == "organization" else record.full_name if record else ""
        if record is None or _key(name) != _key(selected["name"]):
            # A removed, renamed or reassigned candidate needs a fresh selection.
            _queue_directory(draft, data, **{key: pending[key] for key in ("kind", "name", "role", "resource_value")}, matches=[])
            return None
    elif confirmation is True:
        matches = list(exact_directory_matches(actor, pending["name"], kind=pending["kind"])[:4])
        if len(matches) > 1:
            _queue_directory(draft, data, **{key: pending[key] for key in ("kind", "name", "role", "resource_value")}, matches=matches)
            return None
        if matches:
            record = matches[0]  # A different tab may already have registered it.
        else:
            suggestions = list(suggested_directory_matches(actor, pending["name"], kind=pending["kind"])[:3])
            if suggestions:
                _queue_directory(draft, data, **{key: pending[key] for key in ("kind", "name", "role", "resource_value")}, matches=suggestions)
                return None
            if pending["kind"] == "organization":
                record = upsert_organization(actor=actor, name=pending["name"])
            else:
                record = upsert_person(actor=actor, full_name=pending["name"], category=pending["role"], organization_id=data.get("organization_id"))
    else:
        return None
    _store_directory(data, kind=pending["kind"], record=record, role=pending["role"], resource_value=pending["resource_value"])
    return True


def _next_missing(data):
    for key in STEP_KEYS:
        present = "organization_id" in data if key == "organization" else key in data
        if key in QUESTION_BY_KEY:
            present = key in data.get("interview_answers", {})
        if not present:
            return key
    return ""


def _record(draft, request_id, digest, *, reply=None, error_code=""):
    draft.revision += 1
    result = _response(draft, reply=reply, error_code=error_code)
    draft.last_request_id = request_id
    draft.last_request_hash = digest
    draft.last_response = result
    draft.save()
    return result


def _answer_error(error, step):
    code = str(error)
    if code == "secret_not_allowed":
        return "No incluyas contraseñas ni claves privadas en la ficha. Cuéntame sólo los datos públicos del evento."
    if code == "invalid_text":
        return "Escribe una respuesta breve, sin caracteres de control; hasta 200 caracteres para el título y 300 para las demás respuestas."
    if "date" in code:
        return "No pude reconocer esa fecha. Usa una fecha válida como 19/11/2026 o di «pendiente»."
    if "time" in code:
        return "Indica una hora válida y su franja: por ejemplo 19:30, 7:30 p. m. o «siete y media de la noche». También puedes decir «pendiente»."
    if "integer" in code:
        return "Indica la duración en minutos, entre 1 y 1440; también puedes decir «una hora y media» o «pendiente»." if step == "duration_minutes" else "Indica una cantidad entera entre 1 y 100000; por ejemplo «cincuenta personas»."
    if code == "ambiguous_confirmation":
        return "¿Usaremos datos ficticios para una demostración? Responde «sí» o «no» para dejarlo claro."
    return code


def _duration_minutes(text):
    value = _key(text)
    value = re.sub(r"^(?:durara|duracion de|sera de|seran) ", "", value)
    if value in {"media hora", "una media hora"}:
        return "30"
    hours = re.fullmatch(r"(.+?) horas?(?: y (media|cuarto|.+?)(?: minutos?)?)?", value)
    if hours:
        minutes = 60 * parse_integer(hours[1], min_value=0, max_value=24)
        if hours[2]:
            minutes += {"media": 30, "cuarto": 15}.get(hours[2], 0)
            if hours[2] not in {"media", "cuarto"}:
                minutes += parse_integer(hours[2], min_value=0, max_value=59)
        return str(parse_integer(str(minutes), min_value=1, max_value=1440))
    return str(parse_integer(value, min_value=1, max_value=1440))


def _accept(draft, actor, text):
    key = draft.step
    value = clean_text(text, max_length=200 if key == "title" else 160 if key == "organization" else 300)
    folded = _key(value)
    data = dict(draft.data)
    spoken = None
    directory_answer = _pending_directory_answer(draft, actor, data, value)
    if directory_answer is None:
        draft.data = data
        return None
    if directory_answer:
        pass
    elif key == "organization":
        only_answer = _directory_answer_only(value)
        confirmation = _directory_confirmation(value) if only_answer else None
        if _instruction_echo(value) or (only_answer and confirmation is not False):
            _queue_directory(draft, data, kind="organization", name="", matches=[])
            data["_directory_resolution"]["mode"] = "new_name"
            return None
        if confirmation is False or folded in {"sin institucion", "sin institucion asignada", "ninguna", "ninguno", "no aplica", "sin empresa"}:
            data.update(organization_id=None, organization_name="")
        else:
            if not _resolve_directory_name(draft, actor, data, kind="organization", name=value):
                return None
    elif key in {"title", "brief"}:
        if key == "brief" and len(value) < 3:
            raise ValueError("Cuéntame un poco más: la descripción necesita al menos tres caracteres.")
        data[key] = value
    elif key == "date":
        if folded in PENDING:
            data.update(date="", time="", scheduled_dates=[])
            data.pop("_pending_date_year", None)
        else:
            today = timezone.localdate()
            dates = parse_scheduled_dates(value, reference_date=today, pending=data.get("_pending_date_year"))
            dates = normalize_scheduled_dates(dates, reference_year=today.year)
            data.update(date=dates[0], scheduled_dates=dates)
            data.pop("_pending_date_year", None)
            spoken = spoken_dates(dates)
    elif key == "time":
        data[key] = "" if folded in PENDING else parse_time(value)
    elif key == "timezone":
        if folded in {"si", "si por favor", "peru", "hora peruana", "lima", "hora de peru", "america lima"}:
            value = "America/Lima"
        try:
            validate_timezone(value)
        except ValidationError as exc:
            raise ValueError("Indica una zona IANA válida, por ejemplo America/Lima, o responde «sí» para Perú.") from exc
        data[key] = value
    elif key == "capacity":
        data[key] = parse_integer(value, min_value=1, max_value=100000)
    elif key == "is_synthetic":
        data[key] = parse_bool(value)
    elif key in QUESTION_BY_KEY:
        if key == "resources" and _instruction_echo(value):
            _queue_directory(draft, data, kind="person", name="", matches=[])
            data["_directory_resolution"]["mode"] = "new_name"
            return None
        if key == "resources" and folded not in PENDING | {"no aplica", "no es aplicable", "ya esta en la ficha", "esta en la ficha", "en la descripcion"}:
            declaration = _person_declaration(value)
            name, role = declaration if declaration else (value, "speaker")
            matches = list(exact_directory_matches(actor, name, kind="person")[:6]) if len(name) <= 160 else []
            suggestions = list(suggested_directory_matches(actor, name, kind="person")[:3]) if len(name) <= 160 and not matches else []
            if matches or suggestions or declaration:
                if len(name) > 160:
                    raise ValueError("Indica un nombre de persona de hasta 160 caracteres.")
                if _instruction_echo(name):
                    _queue_directory(draft, data, kind="person", name="", matches=[], role=role)
                    data["_directory_resolution"]["mode"] = "new_name"
                    return None
                if not _resolve_directory_name(draft, actor, data, kind="person", name=name, role=role, resource_value=value):
                    return None
            else:
                data.pop("directory_people", None)
        answer = {"status": "confirmed", "value": value}
        if folded in PENDING:
            answer = {"status": "pending", "value": ""}
        elif folded in {"no aplica", "no es aplicable"}:
            answer = {"status": "not_applicable", "value": ""}
        elif folded in {"ya esta en la ficha", "esta en la ficha", "en la descripcion"}:
            answer = {"status": "in_brief", "value": ""}
        elif key == "duration_minutes":
            answer["value"] = _duration_minutes(value)
        data["interview_answers"] = normalize_interview_answers({**data.get("interview_answers", {}), key: answer})
    draft.data = data
    if data.pop("_return_to_review", False):
        draft.step = ""
        draft.status = "review"
    else:
        draft.step = _next_missing(data)
        if not draft.step:
            draft.status = "review"
    return spoken


def _build_event(draft, actor):
    data = draft.data
    if _next_missing(data):
        raise ValueError("Faltan respuestas. Completemos la ficha antes de crear el evento.")
    form = EventForm({
        "title": data["title"], "brief": data["brief"], "timezone": data["timezone"],
        "capacity": data["capacity"], "organization_id": data.get("organization_id") or "",
        "is_synthetic": data["is_synthetic"],
        "starts_at": f'{data["date"]}T{data["time"]}' if data["date"] and data["time"] else "",
        "scheduled_dates": json.dumps(normalize_scheduled_dates(data.get("scheduled_dates", [data["date"]] if data["date"] else []))),
    }, actor=actor)
    if not form.is_valid():
        raise ValueError("Revisa la ficha antes de crear: " + " ".join(str(error) for errors in form.errors.values() for error in errors))
    event = create_event(actor=actor, **form.cleaned_data)
    event.interview_answers = normalize_interview_answers(data["interview_answers"])
    event.full_clean()
    event.save(update_fields=["interview_answers"])
    for item in data.get("directory_people", []):
        person = people_for(actor).filter(pk=item["id"], is_active=True).first()
        if person is None:
            raise ValueError("La persona seleccionada ya no está disponible. Revisa Recursos antes de crear el evento.")
        assign_person(actor=actor, event_id=event.pk, person_id=person.pk, role=item["role"])
    draft.event = event
    draft.status = "created"
    draft.step = ""


@transaction.atomic
def creation_turn(actor, text="", *, draft_id=None, expected_revision=None, request_id, operation="turn", field=""):
    """Advance exactly one human answer, retaining explicit final confirmation."""
    current = human_organizer(actor, lock=True)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("Envía la revisión actual del borrador (0 al comenzar).")
    try:
        request_id = uuid.UUID(str(request_id))
        identifier = uuid.UUID(str(draft_id)) if draft_id else None
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("El identificador de la solicitud o borrador no es válido.") from exc
    if operation not in ALLOWED_OPERATIONS or not isinstance(field, str):
        raise ValidationError("La operación de creación no está permitida.")
    if not isinstance(text, str) or len(text) > 300:
        raise ValidationError("Usa una respuesta de hasta 300 caracteres.")
    if field and (operation != "edit" or field not in STEP_BY_KEY):
        raise ValidationError("El campo solicitado no es válido.")
    digest = hashlib.sha256(json.dumps({"text": text, "operation": operation, "field": field,
        "revision": expected_revision}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if identifier:
        draft = EventCreationDraft.objects.select_for_update().filter(owner=current, pk=identifier).first()
        if draft is None:
            raise Http404("No se encontró este borrador.")
    else:
        draft = EventCreationDraft.objects.select_for_update().filter(owner=current, status__in=ACTIVE).first()
    if draft and draft.last_request_id == request_id:
        if digest == draft.last_request_hash:
            return draft.last_response
        return _response(draft, reply="Ese identificador ya se usó para otra respuesta. Vuelve a intentarlo con una solicitud nueva.", status="conflict", error_code="request_reused")
    if operation == "resume":
        if draft is None:
            return _blank()
        if draft.expires_at <= timezone.now() and draft.status in ACTIVE:
            return _response(draft, status="expired", error_code="expired", reply="Este borrador caducó. Podemos comenzar uno nuevo cuando digas «crear evento».")
        pending = draft.data.get("_directory_resolution")
        if draft.status == "collecting" and pending and pending.get("step") == draft.step:
            recovered = _safe_pending(pending, current)
            if recovered != pending:
                draft.data = {**draft.data, "_directory_resolution": recovered}
                return _record(draft, request_id, digest)
        return _response(draft)
    if identifier is None and (operation != "turn" or not is_creation_request(text)):
        # An existing stored draft must not capture unrelated ordinary commands
        # after reload. Only an explicit resume or creation request can reopen it.
        return _blank()
    if draft and draft.status in ACTIVE and draft.expires_at <= timezone.now():
        if identifier:
            return _response(draft, status="expired", error_code="expired", reply="Este borrador caducó. Comienza otro con «crear evento»; no se creó ningún evento.")
        draft.status = "cancelled"
        draft.save(update_fields=["status", "updated_at"])
        draft = None
    if draft is None:
        if operation != "turn" or not is_creation_request(text):
            return _blank()
        if expected_revision != 0:
            raise ValidationError("Comienza un borrador nuevo con revisión 0.")
        draft = EventCreationDraft.objects.create(owner=current, expires_at=timezone.now() + timedelta(hours=24))
        # Creation itself is revision 1; save the replay receipt without advancing.
        result = _response(draft)
        draft.last_request_id = request_id
        draft.last_request_hash = digest
        draft.last_response = result
        draft.save(update_fields=["last_request_id", "last_request_hash", "last_response"])
        return result
    if not identifier:
        return _response(draft, reply="Retomemos tu borrador actual. " + (_response(draft)["reply"]))
    if expected_revision != draft.revision:
        return _response(draft, status="conflict", error_code="stale_revision", reply="El borrador cambió en otra pestaña. He recuperado sus datos actuales; revisa la pregunta y vuelve a responder.")
    if draft.status not in ACTIVE:
        return _response(draft)
    folded = _key(text)
    if operation == "turn":
        operation = {"cancelar creacion": "cancel", "cancelar borrador": "cancel", "atras": "back",
                     "volver atras": "back", "revisar borrador": "review"}.get(folded, "turn")
    if operation == "cancel":
        draft.status, draft.step = "cancelled", ""
        return _record(draft, request_id, digest)
    if operation == "review":
        return _response(draft, reply="Estos son los datos guardados. " + _response(draft)["reply"])
    if operation == "back":
        draft.data = {key: value for key, value in draft.data.items() if key != "_directory_resolution"}
        index = STEP_KEYS.index(draft.step) if draft.step in STEP_KEYS else len(STEPS)
        draft.step = STEP_KEYS[max(0, index - 1)]
        draft.status = "collecting"
        # Earlier subsequent answers stay visible; answering this field returns to
        # the next genuinely absent field rather than silently clearing answers.
        return _record(draft, request_id, digest)
    if operation == "edit":
        if field not in STEP_BY_KEY:
            raise ValidationError("Elige el campo que deseas corregir.")
        if draft.status == "review":
            draft.data = {**draft.data, "_return_to_review": True}
        draft.data = {key: value for key, value in draft.data.items() if key != "_directory_resolution"}
        draft.step, draft.status = field, "collecting"
        return _record(draft, request_id, digest)
    if draft.status == "review":
        if operation == "confirm" or (operation == "turn" and folded in CONFIRMATIONS):
            try:
                # Savepoint makes validation failures leave no partial Event row.
                with transaction.atomic():
                    _build_event(draft, current)
            except (ValueError, ValidationError) as exc:
                return _response(draft, reply=str(exc), error_code="invalid_event")
            return _record(draft, request_id, digest)
        return _response(draft, reply="Revisa el resumen. Para guardarlo como evento, di «crear evento» o pulsa Crear evento; para corregir, elige un campo.", error_code="confirmation_required")
    if operation == "confirm":
        return _response(draft, reply="Primero completemos los datos y revisemos el resumen.", error_code="incomplete")
    try:
        spoken = _accept(draft, current, text)
    except DateYearRequired as exc:
        draft.data = {**draft.data, "_pending_date_year": exc.pending}
        # Old accepted dates must not masquerade as the new incomplete selection
        # when the organizer is correcting this field from the final summary.
        draft.data.pop("date", None)
        draft.data.pop("scheduled_dates", None)
        return _record(draft, request_id, digest, reply=str(exc), error_code="year_required")
    except (ValueError, ValidationError) as exc:
        return _response(draft, reply=_answer_error(exc, draft.step), error_code="invalid_answer")
    reply = f"{spoken} {_response(draft)['reply']}" if spoken else None
    return _record(draft, request_id, digest, reply=reply)
