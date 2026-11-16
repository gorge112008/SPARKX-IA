"""An explicitly manual, fictional event for rehearsing the complete workflow.

Only proposals are prepared here. Approval, task state changes and real-world
operations always remain separate, explicit actions by the organizer.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.planning.domain import validate_plan
from apps.planning.models import PlanCandidate
from apps.planning.services import _check_snapshot, create_candidate

from .interview import normalize_interview_answers
from .models import Event
from .services import create_event, require_event_owner


JOURNEY_EVENT_ID = UUID("88d44566-fc5c-5cce-9695-13eb7c027786")
JOURNEY_TITLE = "Demo · Taller de IA responsable para equipos"
JOURNEY_TIMEZONE = "America/Lima"
JOURNEY_START = datetime(2026, 11, 20, 18, 0, tzinfo=ZoneInfo(JOURNEY_TIMEZONE))
JOURNEY_CAPACITY = 30
JOURNEY_NOTICE = (
    "Demostración manual con datos ficticios; sin generación de IA ni ejecución real."
)
JOURNEY_BRIEF = f"""{JOURNEY_NOTICE}

ESCENARIO FICTICIO PARA ENSAYAR ARQUIGICA
Un equipo de ejemplo quiere preparar un taller introductorio de uso responsable
de IA para 30 participantes ficticios, el 20/11/2026 a las 18:00, America/Lima.
Se propone una sala de práctica ficticia y una facilitación de ejemplo; no hay
personas, espacios, reservas ni inscripciones reales asociados a estos datos.

SUPUESTOS DEL EJERCICIO
Objetivo: que el público identifique riesgos de privacidad y contraste una respuesta
de IA mediante un ejercicio con información sintética, sin datos personales.
Público: equipos de trabajo con conocimientos digitales básicos. Modalidad presencial
hipotética. Duración base: 90 minutos, de 18:00 a 19:30. Aforo supuesto: 30 personas.
Los materiales, responsables y la disponibilidad de la sala requieren confirmación
en un evento real. El ejercicio no consume API, no ejecuta una IA ni envía mensajes.

RECORRIDO GUIADO
Revisar la ficha y los supuestos; revisar y aprobar la propuesta base si se desea;
seguir sus tareas mediante acciones manuales; comparar después una ampliación de
15 minutos y comprobar que un solapamiento se rechaza antes de crear la propuesta.
La carga no aprueba planes ni acredita tareas, asistencia o resultados obtenidos.
"""


def _task(identifier, title, purpose, dependencies=()):
    return {
        "id": identifier,
        "title": title,
        "depends_on": list(dependencies),
        "status": "pending",
        "purpose": purpose,
    }


def journey_baseline_payload():
    """Return a fresh, valid baseline; all people and resources are fictional."""
    blocks = (
        ("bienvenida", "Bienvenida y objetivo del ejercicio", 10),
        ("fundamentos", "Fundamentos de IA responsable y privacidad", 20),
        ("practica", "Práctica con información sintética", 40),
        ("preguntas", "Preguntas, contraste de respuestas y cierre", 20),
    )
    sessions = []
    start = JOURNEY_START
    for identifier, title, duration in blocks:
        sessions.append({
            "id": identifier,
            "title": title,
            "start": start.isoformat(),
            "duration_minutes": duration,
            "speaker": "Facilitación de ejemplo (ficticia)",
            "resource": "Sala de práctica de ejemplo (ficticia)",
        })
        start += timedelta(minutes=duration)
    return {
        "title": JOURNEY_TITLE,
        "summary": (
            f"{JOURNEY_NOTICE} Propuesta base de 90 minutos, el 20/11/2026 "
            "de 18:00 a 19:30 en America/Lima, para un aforo supuesto de 30 personas. "
            "Las cuatro sesiones y seis tareas permiten ensayar revisión, aprobación "
            "y seguimiento; no representan una organización o celebración real."
        ),
        "sessions": sessions,
        "tasks": [
            _task(
                "definir-alcance", "Revisar objetivo, público y supuestos",
                "Ejercicio ficticio: revisar el alcance y los supuestos antes de preparar el taller.",
            ),
            _task(
                "confirmar-recursos", "Revisar sala y recursos del ejercicio",
                "Ejercicio ficticio: revisar disponibilidad hipotética, aforo y accesibilidad; no reserva una sala.",
                ("definir-alcance",),
            ),
            _task(
                "preparar-material", "Preparar material con datos sintéticos",
                "Ejercicio ficticio: preparar una ficha breve y ejemplos sin datos personales ni secretos.",
                ("definir-alcance",),
            ),
            _task(
                "revisar-privacidad", "Revisar privacidad y uso responsable",
                "Ejercicio ficticio: comprobar que el material no contiene datos identificables y propone contrastar respuestas.",
                ("preparar-material",),
            ),
            _task(
                "ensayar", "Ensayar agenda y práctica",
                "Ejercicio ficticio: recorrer los tiempos y revisar el material; una marca manual no acredita un ensayo real.",
                ("confirmar-recursos", "revisar-privacidad"),
            ),
            _task(
                "preparar-cierre", "Preparar preguntas y cierre",
                "Ejercicio ficticio: preparar preguntas de reflexión y un formato de cierre sin inventar respuestas del público.",
                ("ensayar",),
            ),
        ],
        "risks": [
            "Todos los datos son ficticios y los recursos son supuestos; no hay reservas ni asistentes reales.",
            "El horario base termina a las 19:30; cualquier ampliación requiere revisión y aprobación humana.",
            "La práctica usa información sintética; este escenario no genera respuestas con una API de IA.",
            "Marcar una tarea en esta demo ensaya el seguimiento y no demuestra trabajo realizado fuera de ArquiGica.",
        ],
    }


def journey_change_payload():
    """Extend practice by 15 minutes and move questions; keep task IDs stable."""
    payload = deepcopy(journey_baseline_payload())
    payload["summary"] = (
        f"{JOURNEY_NOTICE} Alternativa manual de 105 minutos: ampliar la práctica "
        "de 40 a 55 minutos, conservar el inicio a las 18:00 y mover preguntas "
        "de 19:10 a 19:25. El cierre pasa de 19:30 a 19:45. "
        "Las cuatro primeras tareas no cambian y pueden conservar sus registros según la revisión base; "
        "el ensayo y su cierre dependiente requieren una nueva revisión y vuelven a pendientes. "
        "No modifica el plan vigente hasta que el organizador revise y apruebe la propuesta."
    )
    for session in payload["sessions"]:
        if session["id"] == "practica":
            session["duration_minutes"] += 15
        elif session["id"] == "preguntas":
            session["start"] = (
                datetime.fromisoformat(session["start"]) + timedelta(minutes=15)
            ).isoformat()
    for task in payload["tasks"]:
        if task["id"] == "ensayar":
            task["purpose"] = (
                "Ejercicio ficticio: repetir el ensayo con la práctica de 55 minutos, "
                "105 minutos totales y cierre a las 19:45; revisar también las preguntas. "
                "El ensayo anterior no acredita la preparación del horario ampliado."
            )
    payload["risks"].append(
        "Alternativa ficticia: confirmar que facilitación y sala admitirían el cierre a las 19:45 antes de aprobar."
    )
    return payload


def journey_conflict_payload():
    """Return a deliberately invalid overlap for the real constraint checker."""
    payload = deepcopy(journey_change_payload())
    payload["summary"] = (
        f"{JOURNEY_NOTICE} Escenario inválido para probar la validación: la práctica "
        "se amplía a 55 minutos pero preguntas permanece a las 19:10. "
        "Las dos sesiones se solapan 15 minutos con la misma facilitación y sala ficticias."
    )
    for session in payload["sessions"]:
        if session["id"] == "preguntas":
            session["start"] = next(
                entry["start"] for entry in journey_baseline_payload()["sessions"]
                if entry["id"] == "preguntas"
            )
    return payload


def _journey_interview_answers():
    values = {
        "objective": "Escenario ficticio: identificar riesgos de privacidad y contrastar respuestas con datos sintéticos.",
        "audience": "Escenario ficticio: equipos de trabajo con conocimientos digitales básicos; aforo supuesto de 30 personas.",
        "modality": "Escenario ficticio: presencial; no hay convocatoria ni participación real.",
        "duration_minutes": "90",
        "location": "Sala de práctica de ejemplo (ficticia), sin reserva ni dirección real.",
        "resources": "Facilitación, sala y material sintético de ejemplo; todos son supuestos del ejercicio.",
        "constraints": "Escenario ficticio: inicio a las 18:00, 90 minutos de base, sin datos personales, API ni operaciones externas.",
    }
    return normalize_interview_answers({
        key: {"status": "assumed", "value": value} for key, value in values.items()
    })


@dataclass(frozen=True)
class JourneyDemoSeedResult:
    event: Event
    created: bool


@transaction.atomic
def seed_journey_demo(*, actor):
    """Seed once without approval; retries preserve every subsequent user edit."""
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False):
        raise PermissionDenied("La demo requiere un propietario autenticado y activo.")
    existing = Event.objects.select_for_update().filter(pk=JOURNEY_EVENT_ID).first()
    if existing is not None:
        require_event_owner(existing, actor)
        return JourneyDemoSeedResult(existing, False)

    errors = validate_plan(journey_baseline_payload()) + validate_plan(journey_change_payload())
    if errors:
        raise ValidationError(errors)
    try:
        # The fixed primary key also guards concurrent first loads. A savepoint
        # lets a losing loader reread and authorize the committed owner safely.
        with transaction.atomic():
            event = create_event(
                actor=actor, event_id=JOURNEY_EVENT_ID, title=JOURNEY_TITLE,
                brief=JOURNEY_BRIEF, starts_at=JOURNEY_START,
                timezone=JOURNEY_TIMEZONE, capacity=JOURNEY_CAPACITY,
            )
            event.interview_answers = _journey_interview_answers()
            event.full_clean()
            event.save(update_fields=["interview_answers", "updated_at"])
            create_candidate(
                event=event, actor=actor, payload=journey_baseline_payload(),
                base_revision=event.revision, base_plan_id=None,
            )
    except IntegrityError:
        existing = Event.objects.select_for_update().filter(pk=JOURNEY_EVENT_ID).first()
        if existing is None:
            raise
        require_event_owner(existing, actor)
        return JourneyDemoSeedResult(existing, False)
    return JourneyDemoSeedResult(event, True)


def _require_demo_identity(event_id):
    try:
        identity = UUID(str(event_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermissionDenied("Este recorrido solo está disponible en su evento de demostración.") from exc
    if identity != JOURNEY_EVENT_ID:
        raise PermissionDenied("Este recorrido solo está disponible en su evento de demostración.")


def _matches_original_spec(event):
    """Fixed examples must not silently disregard the organizer's later edits."""
    return (
        event.title == JOURNEY_TITLE
        and event.brief == JOURNEY_BRIEF.strip()
        and event.starts_at == JOURNEY_START
        and event.timezone == JOURNEY_TIMEZONE
        and event.capacity == JOURNEY_CAPACITY
        and event.interview_answers == _journey_interview_answers()
    )


@transaction.atomic
def ensure_journey_proposal(*, actor, event_id, scenario, expected_revision, expected_plan_id):
    """Prepare one fixed manual proposal for a current owner-authorized snapshot.

    Invalid conflict examples are rejected without being persisted. This command
    never changes the event, approves a plan, executes a job or writes progress.
    """
    _require_demo_identity(event_id)
    # Lock only Event: active_plan is nullable, so joining it here would make
    # PostgreSQL reject FOR UPDATE on the nullable side of an outer join.
    event = Event.objects.select_for_update().get(pk=JOURNEY_EVENT_ID)
    require_event_owner(event, actor)
    _check_snapshot(event, expected_revision, expected_plan_id)
    if not _matches_original_spec(event):
        raise ValidationError(
            "Los ejemplos corresponden a la ficha original. Conservamos tus cambios; "
            "continúa con el flujo normal del evento para preparar una propuesta acorde a sus datos actuales."
        )
    if not isinstance(scenario, str) or scenario not in {"baseline", "change", "conflict"}:
        raise ValidationError("El escenario de demostración no es válido.")
    if scenario == "baseline":
        if event.active_plan_id is not None:
            raise ValidationError("La propuesta base solo se prepara antes de aprobar el primer plan.")
        payload = journey_baseline_payload()
    else:
        if event.active_plan_id is None:
            raise ValidationError("Revisa y aprueba primero la propuesta base para comparar sus cambios.")
        if scenario == "change" and event.active_plan.payload != journey_baseline_payload():
            raise ValidationError(
                "La ampliación guiada requiere el plan base original; no sustituye un plan adaptado por el organizador."
            )
        payload = journey_change_payload() if scenario == "change" else journey_conflict_payload()
    errors = validate_plan(payload)
    if errors:
        raise ValidationError(errors)
    existing = event.candidates.filter(
        payload=payload, base_revision=event.revision,
        base_plan_id=event.active_plan_id, status=PlanCandidate.Status.PENDING,
    ).first()
    if existing is not None:
        return existing
    return create_candidate(
        event=event, actor=actor, payload=payload,
        base_revision=event.revision, base_plan_id=event.active_plan_id,
    )


def get_journey_demo_context(event):
    """Describe the available fixed scenarios without changing any state."""
    if event.pk != JOURNEY_EVENT_ID:
        return None
    original_spec = _matches_original_spec(event)
    active_payload = event.active_plan.payload if event.active_plan_id else None
    pending = event.candidates.filter(
        base_revision=event.revision, base_plan_id=event.active_plan_id,
        status=PlanCandidate.Status.PENDING,
    )
    baseline_id = pending.filter(payload=journey_baseline_payload()).values_list("pk", flat=True).first()
    change_id = pending.filter(payload=journey_change_payload()).values_list("pk", flat=True).first()
    return {
        "badge": "Demo guiada · datos ficticios",
        "notice": JOURNEY_NOTICE,
        "source": "Escenario ficticio elaborado manualmente para ensayar el flujo de ArquiGica.",
        "original_spec": original_spec,
        "baseline_candidate_id": baseline_id,
        "change_candidate_id": change_id,
        "can_prepare_baseline": original_spec and event.active_plan_id is None,
        "can_prepare_change": original_spec and active_payload == journey_baseline_payload(),
        "can_check_conflict": original_spec and event.active_plan_id is not None,
        "is_baseline_active": active_payload == journey_baseline_payload(),
        "is_change_active": active_payload == journey_change_payload(),
    }
