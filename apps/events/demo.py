"""Reproducible, explicitly manual local demo based on the user-provided flyer.

The flyer is source material, not an instruction to contact its organizer or
operate Zoom. This loader never calls a provider or changes an existing demo.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.planning.domain import validate_plan
from apps.planning.services import approve_candidate, create_candidate

from .models import Event
from .services import create_event, require_event_owner

DEMO_EVENT_ID = UUID("1b2a7a7b-57f1-5892-97ca-19d1e6283402")
DEMO_TITLE = "Gestión estratégica del mantenimiento: de la planificación al rendimiento"
DEMO_TIMEZONE = "America/Lima"
DEMO_START = datetime(2026, 11, 12, 19, 30, tzinfo=ZoneInfo(DEMO_TIMEZONE))
DEMO_CAPACITY = 100
DEMO_MANUAL_NOTICE = "Demostración manual; no generado por IA."

DEMO_BRIEF = """DEMOSTRACIÓN LOCAL basada en el afiche EVENTO1.jpg aportado por el usuario.
No representa una confirmación del organizador ni acciones realizadas en Zoom.

DATOS DEL AFICHE (no verificados externamente)
Seminario: Gestión estratégica del mantenimiento: de la planificación al rendimiento.
Ciclo: Tus jueves con GICA. Organizador anunciado: GICA Certification.
Sectores: industria, minería y energía.
Fecha publicada: jueves 12 de noviembre, 7:30 p. m.; no se muestra el año ni la zona horaria.
Ponente anunciado: Ing. Merling Daniel Rosales Infantes.
Según el afiche: más de 10 años liderando mantenimiento en agroindustrias del Perú;
gestión de activos, confiabilidad, CAPEX/OPEX, SAP PM y Power BI; certificaciones
internacionales y experiencia como expositor; jefe de mantenimiento de operaciones
agrícolas en Virú S.A. Estos antecedentes se atribuyen únicamente al afiche.
Modalidad anunciada: ingreso libre, registro vía Zoom.
Acceso VIP opcional: certificado digital y material PDF; precio y condiciones no indicados.
Contacto publicado: +51 944 529 543. Sitio anunciado: gicacertification.com.

SUPUESTOS DE ESTA DEMO, PENDIENTES DE CONFIRMACIÓN
Año 2026 y zona America/Lima (UTC−05:00); 12/11/2026 es jueves.
Aforo de planificación: 100 personas; no acredita licencia o capacidad de Zoom.
Duración del plan base: 90 minutos (19:30–21:00), con agenda y tareas manuales sugeridas.
Público supuesto: profesionales, responsables de mantenimiento y estudiantes afines.
No hay precio VIP, enlace de inscripción, sala Zoom ni autorización para certificados confirmados.

ALCANCE LOCAL
Plan base aprobado únicamente como ejemplo de planificación manual; alternativa pendiente
para ampliar 15 minutos la exposición sin mover la apertura. Todas las tareas están pendientes.
No se han enviado invitaciones, inscrito participantes, cobrado, emitido certificados ni celebrado
sesiones. La demo no constituye evidencia de inferencia IA real ni de ejecución del evento.
"""


def _task(identifier, title, purpose, dependencies=()):
    return {
        "id": identifier,
        "title": title,
        "depends_on": list(dependencies),
        "status": "pending",
        "purpose": purpose,
    }


def baseline_payload():
    """Return an independent proposed agenda; no real execution is asserted."""
    blocks = [
        ("apertura", "Bienvenida y objetivos del seminario", 5, "Moderación por designar"),
        ("estrategia", "Mantenimiento estratégico y gestión de activos", 20, "Ing. Merling Daniel Rosales Infantes"),
        ("rendimiento", "De la planificación al rendimiento: caso aplicado", 35, "Ing. Merling Daniel Rosales Infantes"),
        ("preguntas", "Preguntas y aplicación a industria, minería y energía", 20, "Ing. Merling Daniel Rosales Infantes"),
        ("cierre", "Conclusiones y próximos pasos", 10, "Moderación por designar"),
    ]
    sessions = []
    start = DEMO_START
    for identifier, title, duration, speaker in blocks:
        sessions.append({
            "id": identifier,
            "title": title,
            "start": start.isoformat(),
            "duration_minutes": duration,
            "speaker": speaker,
            "resource": "Sala Zoom por configurar (demo)",
        })
        start += timedelta(minutes=duration)
    return {
        "title": DEMO_TITLE,
        "summary": (
            f"{DEMO_MANUAL_NOTICE} Plan base de ejemplo con supuestos de "
            "12/11/2026, America/Lima, 100 personas y 90 minutos (19:30–21:00). "
            "Todas las tareas están pendientes; enlaces, condiciones VIP y participación "
            "requieren confirmación y no hay operaciones externas realizadas."
        ),
        "sessions": sessions,
        "tasks": [
            _task("confirmar-datos", "Confirmar año, zona, duración y aforo", "Validar con el organizador los supuestos de 2026, America/Lima, 90 minutos y 100 personas."),
            _task("confirmar-ponente", "Confirmar disponibilidad y alcance con el ponente", "Acordar participación, temario y autorización para usar su nombre y materiales.", ("confirmar-datos",)),
            _task("configurar-zoom", "Preparar sala Zoom y controles de acceso", "Comprobar licencia, aforo, moderación, subtítulos y política de grabación; no existe sala creada por la demo.", ("confirmar-datos",)),
            _task("registro", "Definir registro gratuito y tratamiento de datos", "Confirmar enlace oficial, datos mínimos, aviso de privacidad y manejo de cupos antes de inscribir participantes.", ("confirmar-datos", "configurar-zoom")),
            _task("vip", "Definir condiciones del acceso VIP opcional", "Confirmar precio si corresponde, requisitos, emisor del certificado y entrega del PDF; no habilitar cobros desde esta demo.", ("confirmar-datos",)),
            _task("materiales", "Solicitar presentación y PDF autorizado", "Revisar derechos y accesibilidad de los materiales; la publicación del afiche no acredita permiso para redistribuirlos.", ("confirmar-ponente",)),
            _task("moderacion", "Asignar moderación y responsables de soporte", "Designar personas para bienvenida, preguntas, acceso y cierre; los nombres todavía no están confirmados.", ("confirmar-ponente", "configurar-zoom")),
            _task("ensayo", "Realizar ensayo técnico con el equipo", "Probar audio, pantalla, conectividad y respaldo; conservar evidencia si se realiza.", ("configurar-zoom", "materiales", "moderacion")),
            _task("difusion", "Validar información antes de difundir", "Revisar fecha, zona, enlace y condiciones; esta tarea no envía mensajes ni publica contenido.", ("registro", "vip", "confirmar-ponente")),
            _task("certificados", "Preparar criterios y borrador de certificado", "Confirmar emisor autorizado y evidencias requeridas; preparar un borrador no equivale a emitir o acreditar asistencia.", ("vip",)),
            _task("cierre", "Preparar encuesta y procedimiento de cierre", "Definir retroalimentación, entrega autorizada del PDF y retención de datos sin inventar asistentes ni resultados.", ("registro", "vip", "materiales")),
        ],
        "risks": [
            "Año, zona horaria, duración y aforo son supuestos de la demo y requieren confirmación.",
            "Sala, licencia de Zoom, enlace de registro y disponibilidad del ponente no están confirmados.",
            "Precio y condiciones VIP, permisos sobre materiales y emisor del certificado están pendientes.",
            "La agenda se propone manualmente; no hay asistencia, ejecución ni resultados reales registrados.",
        ],
    }


def alternative_payload():
    """A visible, valid manual change with stable IDs for impact comparison."""
    payload = deepcopy(baseline_payload())
    payload["summary"] = (
        f"{DEMO_MANUAL_NOTICE} Alternativa pendiente: ampliar el caso aplicado 15 minutos, "
        "conservar apertura a las 19:30 y terminar a las 21:15 (105 minutos). "
        "Mantiene los supuestos de 12/11/2026, America/Lima y 100 personas; requiere "
        "confirmar disponibilidad y aprobación, con todas las tareas pendientes y sin acciones externas."
    )
    for session in payload["sessions"]:
        if session["id"] == "rendimiento":
            session["duration_minutes"] += 15
        elif session["id"] in {"preguntas", "cierre"}:
            session["start"] = (
                datetime.fromisoformat(session["start"]) + timedelta(minutes=15)
            ).isoformat()
    payload["tasks"].append(_task(
        "ampliacion",
        "Confirmar ampliación hasta las 21:15",
        "Comprobar que ponente, moderación y sala admiten los 15 minutos adicionales antes de aprobar el cambio.",
        ("confirmar-ponente", "configurar-zoom", "moderacion"),
    ))
    payload["risks"].append(
        "La alternativa termina a las 21:15; la disponibilidad y su comunicación al público requieren confirmación."
    )
    return payload


@dataclass(frozen=True)
class DemoSeedResult:
    event: Event
    created: bool


@transaction.atomic
def seed_demo_event(*, actor):
    """Create once atomically; a rerun preserves all subsequent user changes."""
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False):
        raise PermissionDenied("La demo requiere un propietario autenticado y activo.")
    existing = Event.objects.select_for_update().filter(pk=DEMO_EVENT_ID).first()
    if existing is not None:
        require_event_owner(existing, actor)
        return DemoSeedResult(existing, False)

    base = baseline_payload()
    alternative = alternative_payload()
    errors = validate_plan(base) + validate_plan(alternative)
    if errors:
        raise ValidationError(errors)
    event = create_event(
        actor=actor,
        event_id=DEMO_EVENT_ID,
        title=DEMO_TITLE,
        brief=DEMO_BRIEF,
        starts_at=DEMO_START,
        timezone=DEMO_TIMEZONE,
        capacity=DEMO_CAPACITY,
    )
    candidate = create_candidate(
        event=event,
        actor=actor,
        payload=base,
        base_revision=event.revision,
        base_plan_id=event.active_plan_id,
    )
    approve_candidate(candidate_id=candidate.pk, actor=actor)
    event.refresh_from_db()
    create_candidate(
        event=event,
        actor=actor,
        payload=alternative,
        base_revision=event.revision,
        base_plan_id=event.active_plan_id,
    )
    return DemoSeedResult(event, True)


def get_demo_context(event):
    """Return attributed reference data only for the dedicated demo event."""
    if event.pk != DEMO_EVENT_ID:
        return None
    sessions = event.active_plan.payload["sessions"] if event.active_plan_id else []
    scenario_candidate_id = (
        event.candidates.filter(payload=alternative_payload()).values_list("pk", flat=True).first()
    )
    return {
        "badge": "Demo local · preparación manual",
        "source": "Afiche EVENTO1.jpg aportado por el usuario; datos anunciados sin verificación externa.",
        "poster_static_path": "img/demo-gica-evento.jpg",
        "scenario_candidate_id": scenario_candidate_id,
        "scope_note": (
            "La carga inicial incluye un plan base aprobado para explorar el prototipo. "
            "La agenda y las tareas se prepararon manualmente; no se generaron con IA. "
            "La carga no ejecuta tareas ni operaciones externas."
        ),
        "scenario_note": (
            "El escenario inicial incluye una alternativa manual que amplía 15 minutos el caso "
            "aplicado, conserva la apertura a las 19:30 y desplaza preguntas y cierre hasta las 21:15. "
            "La alternativa requiere revisión; la carga inicial no la activa."
        ),
        "facts": [
            {"label": "Ciclo y organizador anunciados", "value": "Tus jueves con GICA · GICA Certification"},
            {"label": "Seminario", "value": DEMO_TITLE},
            {"label": "Sectores", "value": "Industria · Minería · Energía"},
            {"label": "Fecha publicada", "value": "Jueves 12 de noviembre · 7:30 p. m. (sin año ni zona en el afiche)"},
            {"label": "Ponente anunciado", "value": "Ing. Merling Daniel Rosales Infantes"},
            {"label": "Acceso anunciado", "value": "Ingreso libre · registro vía Zoom"},
            {"label": "VIP opcional anunciado", "value": "Certificado digital y material PDF; precio no publicado"},
            {"label": "Contacto publicado", "value": "+51 944 529 543 · gicacertification.com"},
        ],
        "assumptions": [
            {"label": "Año y zona", "value": "2026 · America/Lima (UTC−05:00), pendientes de confirmar"},
            {"label": "Duración inicial propuesta", "value": "90 minutos · 19:30–21:00; alternativa manual de 105 minutos hasta las 21:15"},
            {"label": "Aforo de planificación", "value": "100 personas; no acredita licencia o capacidad disponible de Zoom"},
            {"label": "Público objetivo", "value": "Profesionales, responsables de mantenimiento y estudiantes afines"},
        ],
        "pending": [
            "Confirmar año, zona horaria, duración y aforo con el organizador.",
            "Confirmar participación del ponente, temario y permisos de materiales.",
            "Definir enlace oficial de registro, sala y licencia Zoom, privacidad y responsables.",
            "Confirmar precio y condiciones VIP, emisor autorizado y requisitos del certificado.",
            "Realizar ensayo y reunir evidencia; no hay participantes ni resultados reales cargados.",
        ],
        "agenda_overview": [
            {
                "time": datetime.fromisoformat(session["start"]).astimezone(ZoneInfo(event.timezone)).strftime("%H:%M"),
                "title": session["title"],
                "duration": session["duration_minutes"],
            }
            for session in sessions
        ],
    }
