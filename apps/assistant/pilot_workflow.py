"""Explicit human-started pilot commands, using the normal event/plan services.

No provider, browser, arbitrary command, bulk deletion or admin access is exposed.
The rehearsal uses real organizer-declared identities; availability remains pending.
"""
from datetime import datetime, timedelta
import json
import uuid
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.directory.models import EventPerson, Organization, Person
from apps.directory.normalization import search_key
from apps.directory.services import upsert_person
from apps.events.forms import EventForm
from apps.events.models import Event
from apps.events.services import create_event
from apps.planning.models import PlanCandidate
from apps.planning.services import create_candidate
from .demo_pilot import PILOT_EVENT_ID
from .local_commands import human_organizer

PILOT_TITLE = "Gestión estratégica del mantenimiento: de la planificación al rendimiento"
INITIAL_DATE = "2026-11-19"
NEXT_DATE = "2026-11-26"
ORGANIZATION_NAME = "Gicaingenieros"
ROBERT_NAME = "Dr. Robert Castillo Alva"
JORGE_NAME = "Jorge Gayoso Ugas"
SESSION_KEY = "gica_pilot_journey_v1"
ANSWER_KEYS = ("objective", "audience", "modality", "duration_minutes", "location", "resources", "constraints")


def pilot_fields(speaker_id):
    return {
        "title": PILOT_TITLE,
        "brief": "Gicaingenieros presenta Tus jueves con GICA. Seminario de gestión estratégica del mantenimiento y confiabilidad para industria, minería y energía. Conectaremos la planificación y la gestión de activos con el rendimiento operativo. Tendremos exposición, caso aplicado y preguntas de los participantes.",
        "date": INITIAL_DATE, "time": "19:30", "timezone": "America/Lima", "capacity": 100,
        "is_synthetic": False, "speaker_id": str(speaker_id),
        "objective": "Aplicar criterios de planificación del mantenimiento y gestión de activos para mejorar el rendimiento operativo.",
        "audience": "Profesionales y responsables de mantenimiento de industria, minería y energía, y estudiantes de áreas afines.",
        "modality": "Virtual", "duration_minutes": "90",
        "location": "Zoom. Enlace de acceso y licencia pendientes de confirmar.",
        "resources": "Expositor: Dr. Robert Castillo Alva. Presentación, material PDF, moderación y soporte por coordinar.",
        "constraints": "Piloto con datos reales declarados por el organizador. Horario de Perú y 100 participantes previstos. Confirmar disponibilidad del expositor, acceso y materiales antes de difundir.",
    }


def _person(actor, canonical, alternatives):
    people = list(Person.objects.filter(owner=actor, name_key__in=[search_key(name) for name in [canonical, *alternatives]]))
    if len(people) > 1:
        raise ValidationError("Hay expositores homónimos. Revisa el directorio antes de continuar.")
    if people:
        person = people[0]
        if not person.is_active or person.category != Person.Category.SPEAKER or person.is_synthetic:
            raise ValidationError("Revisa la ficha real y activa del expositor en el directorio.")
        return person
    return upsert_person(actor=actor, full_name=canonical, category=Person.Category.SPEAKER, is_synthetic=False)


def _metadata(event):
    return {"event_id": str(event.pk), "event_url": reverse("events:detail", args=[event.pk]), "revision": event.revision}


def _pilot(actor, *, lock=False):
    events = Event.objects.select_for_update() if lock else Event.objects
    event = events.filter(pk=PILOT_EVENT_ID, owner=actor).first()
    if event and (event.title != PILOT_TITLE or event.is_synthetic):
        raise ValidationError("El piloto anterior requiere preparación local antes de este recorrido.")
    return event


def build_pilot_plan(event):
    """Deterministic authored programme. This is not model inference or execution evidence."""
    if not event.starts_at:
        raise ValidationError("Completa primero el inicio del evento.")
    links = list(event.directory_people.select_related("person").filter(role="speaker", status__in=["planned", "confirmed"])[:2])
    if (len(links) != 1 or links[0].person.owner_id != event.owner_id or not links[0].person.is_active
            or links[0].person.category != Person.Category.SPEAKER or links[0].person.is_synthetic):
        raise ValidationError("Selecciona un único expositor real y activo de tu directorio antes de preparar la agenda.")
    link = links[0]
    names = [("apertura", "Bienvenida y objetivos", 5), ("estrategia", "Mantenimiento estratégico y gestión de activos", 20),
             ("caso", "De la planificación al rendimiento con un caso aplicado", 35),
             ("preguntas", "Preguntas y aplicación profesional", 20), ("cierre", "Conclusiones y próximos pasos", 10)]
    current = event.starts_at.astimezone(ZoneInfo(event.timezone))
    sessions = []
    for key, title, minutes in names:
        sessions.append({"id": key, "title": title, "start": current.isoformat(), "duration_minutes": minutes,
                         "speaker": link.person.full_name, "resource": "Sala virtual Zoom"})
        current += timedelta(minutes=minutes)
    task_specs = [
        ("confirmar-datos", "Confirmar fecha, horario y aforo", [], "Revisar la ficha con la organización antes de difundir."),
        ("confirmar-expositor", "Confirmar participación del expositor", ["confirmar-datos"], "Coordinar disponibilidad, temario y autorización de materiales."),
        ("sala", "Configurar el acceso y la sala virtual", ["confirmar-datos"], "Comprobar licencia, aforo, enlace, moderación y acceso."),
        ("registro", "Preparar inscripción e información a participantes", ["sala"], "Definir los datos mínimos y el aviso de privacidad."),
        ("materiales", "Revisar presentación y material de apoyo", ["confirmar-expositor"], "Comprobar contenido, permisos y accesibilidad de los archivos."),
        ("moderacion", "Designar moderación y soporte", ["confirmar-expositor", "sala"], "Asignar responsables de bienvenida, preguntas y soporte."),
        ("ensayo", "Realizar el ensayo técnico", ["materiales", "moderacion"], "Probar sonido, pantalla, conexión y respaldo con el equipo."),
        ("difusion", "Revisar y publicar información del evento", ["registro", "confirmar-expositor"], "Publicar sólo tras confirmar los datos y responsables."),
        ("asistencia", "Registrar asistencia durante el evento", ["registro", "ensayo"], "Conservar evidencia de participación conforme al aviso de privacidad."),
        ("preguntas", "Recopilar preguntas y evaluación", ["asistencia"], "Recoger dudas y valoración de los participantes."),
        ("cierre", "Revisar el cierre y los compromisos", ["preguntas"], "Documentar acuerdos y entregables pendientes, sin certificar tareas no realizadas."),
    ]
    return {"title": event.title, "summary": "Agenda del piloto de Gicaingenieros, preparada con una plantilla local y reglas de horario. Datos de identidad declarados por el organizador. La aprobación del plan no confirma disponibilidad externa ni ejecución de las tareas.",
            "sessions": sessions, "tasks": [{"id": key, "title": title, "depends_on": dependencies, "status": "pending", "purpose": purpose} for key, title, dependencies, purpose in task_specs],
            "risks": ["Confirmar disponibilidad del expositor y moderación.", "Confirmar enlace y licencia de Zoom.", "Ensayar conexión, sonido y material de respaldo."]}


def _reply(data, status=200):
    response = JsonResponse(data, status=status)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_json_constant(value):
    raise ValueError("JSON constants must be finite")


@never_cache
@login_required
@require_POST
@transaction.atomic
def pilot_control(request):
    try:
        actor = human_organizer(request.user)
        if request.content_type != "application/json" or len(request.body) > 30000:
            return _reply({"error": "Se requiere una solicitud JSON acotada."}, 400)
        data = json.loads(request.body, object_pairs_hook=_json_pairs, parse_constant=_invalid_json_constant)
        if not isinstance(data, dict) or data.get("operation") not in {"bootstrap", "create", "plan", "replan"}:
            return _reply({"error": "La operación no está permitida."}, 400)
        allowed = {"bootstrap": {"operation"}, "create": {"operation", "run_id", "fields"}, "plan": {"operation", "run_id", "event_id", "expected_revision"}, "replan": {"operation", "run_id", "event_id", "expected_revision"}}
        operation = data["operation"]
        if set(data) != allowed[operation]:
            return _reply({"error": "Revisa los campos de la operación."}, 400)
        run = request.session.get(SESSION_KEY)
        now = timezone.now().timestamp()
        if operation == "bootstrap":
            if not isinstance(run, dict) or run.get("owner") != actor.pk or run.get("expires", 0) < now:
                run = {"id": str(uuid.uuid4()), "owner": actor.pk, "expires": now + 7200}
                request.session[SESSION_KEY] = run
            # Serializes creates for this human without changing permission or account data.
            human_organizer(actor, lock=True)
            if Event.objects.filter(pk=PILOT_EVENT_ID).exclude(owner=actor).exists():
                raise PermissionDenied("Este recorrido no está disponible para esta cuenta.")
            robert = _person(actor, ROBERT_NAME, ["Robert Castillo Alva", "Robert Castillo"])
            jorge = _person(actor, JORGE_NAME, [])
            org = Organization.objects.filter(owner=actor, name_key=search_key(ORGANIZATION_NAME), is_active=True, is_synthetic=False).first()
            event = _pilot(actor)
            return _reply({"run_id": run["id"], "event_id": str(event.pk) if event else None,
                           "event_url": reverse("events:detail", args=[event.pk]) if event else None,
                           "event_revision": event.revision if event else None, "narration_mode": "resume" if event else "create",
                           "organization": {"id": str(org.pk) if org else None, "name": ORGANIZATION_NAME, "aliases": ["GICA Ingenieros"]},
                           "speakers": {"robert": str(robert.pk), "jorge": str(jorge.pk)}, "fields": pilot_fields(robert.pk), "next_date": NEXT_DATE})
        if not isinstance(run, dict) or run.get("owner") != actor.pk or run.get("expires", 0) < now or data.get("run_id") != run.get("id"):
            return _reply({"error": "Inicia de nuevo el recorrido del piloto."}, 409)
        if operation == "create":
            human_organizer(actor, lock=True)
            if Event.objects.filter(pk=PILOT_EVENT_ID).exclude(owner=actor).exists():
                raise PermissionDenied("Este recorrido no está disponible para esta cuenta.")
            event = _pilot(actor, lock=True)
            if event:
                return _reply({**_metadata(event), "created": False})
            values = data.get("fields")
            if not isinstance(values, dict) or len(values) > 23 or any(not isinstance(key, str) or not isinstance(value, (str, int, bool)) for key, value in values.items()):
                return _reply({"error": "Revisa la ficha del piloto."}, 400)
            form = EventForm(values, actor=actor)
            if not form.is_valid():
                return _reply({"error": "Completa los campos señalados.", "errors": form.errors.get_json_data()}, 400)
            fields = form.cleaned_data
            preparation = fields.get("interview_answers", {})
            org = fields.get("organization_id")
            speaker = fields.get("speaker_id")
            expected = datetime.fromisoformat(INITIAL_DATE + "T19:30:00-05:00")
            person = Person.objects.filter(pk=speaker, owner=actor).first()
            organization = Organization.objects.filter(pk=org, owner=actor, name_key=search_key(ORGANIZATION_NAME)).first()
            if (fields["title"] != PILOT_TITLE or fields["starts_at"] != expected or fields["capacity"] != 100 or fields["is_synthetic"]
                    or fields["timezone"] != "America/Lima" or fields["scheduled_dates"] != [INITIAL_DATE]
                    or set(preparation) != set(ANSWER_KEYS)
                    or any(answer["status"] != "confirmed" or not answer["value"] for answer in preparation.values())
                    or preparation.get("duration_minutes", {}).get("value") != "90"
                    or not person or person.name_key not in {search_key(ROBERT_NAME), search_key("Robert Castillo Alva"), search_key("Robert Castillo")}
                    or not organization):
                return _reply({"error": "La ficha no corresponde al piloto autorizado."}, 400)
            event = create_event(actor=actor, event_id=PILOT_EVENT_ID, **fields)
            return _reply({**_metadata(event), "created": True}, 201)
        event = _pilot(actor, lock=True)
        if event is None or data.get("event_id") != str(event.pk):
            return _reply({"error": "El piloto no está disponible."}, 404)
        if type(data.get("expected_revision")) is not int or data["expected_revision"] != event.revision:
            return _reply({"error": "La ficha cambió. Recarga y revisa antes de continuar."}, 409)
        payload = build_pilot_plan(event)
        candidate = PlanCandidate.objects.filter(event=event, base_revision=event.revision, base_plan_id=event.active_plan_id,
                                                status="pending", payload=payload).first()
        created = candidate is None
        if candidate is None:
            candidate = create_candidate(event=event, actor=actor, payload=payload, base_revision=event.revision, base_plan_id=event.active_plan_id)
        if candidate.validation:
            return _reply({"error": "La propuesta requiere corregir sus restricciones.", "validation": candidate.validation}, 409)
        return _reply({**_metadata(event), "candidate_id": str(candidate.pk), "approve_url": reverse("events:approve", args=[event.pk, candidate.pk]), "candidate_url": reverse("events:detail", args=[event.pk]) + "#candidate", "created": created})
    except PermissionDenied:
        transaction.set_rollback(True)
        return _reply({"error": "Se requiere una cuenta humana organizadora vigente."}, 403)
    except (ValidationError, ValueError, TypeError, OverflowError, RecursionError) as error:
        transaction.set_rollback(True)
        return _reply({"error": " ".join(error.messages) if isinstance(error, ValidationError) else "La solicitud no tiene un formato válido."}, 400)
