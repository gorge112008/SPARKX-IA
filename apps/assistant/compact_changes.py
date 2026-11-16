"""One closed, human-requested agenda change; no free-text export or approval.

Only durations and semantic roles leave the server. Names, dates, identifiers,
edited titles, task declarations and evidence remain local to the event.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import re
import unicodedata

from django.core.exceptions import ValidationError

CHANGE_KIND = "more_case_time"


def _error(message="La agenda necesita un caso y una sesión de preguntas separados antes de pedir este cambio."):
    raise ValidationError(message, code="compact_change_invalid")


def _role(title):
    if not isinstance(title, str):
        _error()
    words = set(re.findall(r"[a-z]+", "".join(character for character in unicodedata.normalize("NFKD", title.lower())
        if not unicodedata.combining(character))))
    case = bool(words & {"caso", "casos", "practico", "practica", "aplicado", "aplicada", "ejercicio", "ejercicios"})
    questions = bool(words & {"pregunta", "preguntas", "consulta", "consultas", "duda", "dudas"})
    if case and questions:
        _error()
    return "case" if case else "questions" if questions else "content"


def _agenda(rows, *, title_key, minute_key):
    if not isinstance(rows, list) or not 2 <= len(rows) <= 6:
        _error()
    result = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get(minute_key)) is not int or not 1 <= row[minute_key] <= 90:
            _error()
        result.append({"min": row[minute_key], "role": _role(row.get(title_key))})
    if sum(row["min"] for row in result) != 90 or any(sum(row["role"] == role for row in result) != 1 for role in ("case", "questions")):
        _error()
    return result


def project_change(event, kind):
    """Read-only projection of the current approved plan, with no private text."""
    if kind != CHANGE_KIND or not isinstance(kind, str):
        _error("Elige el cambio acotado de ampliar el caso práctico.")
    if not event.active_plan_id:
        _error("Aprueba una agenda antes de solicitar un cambio a la IA.")
    rows = _agenda(event.active_plan.payload.get("sessions"), title_key="title", minute_key="duration_minutes")
    case = next(row for row in rows if row["role"] == "case")
    # The donor sessions must retain at least one minute and questions ten.
    minimum_other = sum(10 if row["role"] == "questions" else 1 for row in rows if row["role"] != "case")
    if case["min"] + 5 + minimum_other > 90:
        _error("No quedan cinco minutos redistribuibles conservando preguntas y las demás sesiones.")
    return {"kind": CHANGE_KIND, "base_agenda": rows}


def validate_change_response(event, context, output):
    """Reject drift and non-compliant deltas before a candidate can be created."""
    change = context.get("change")
    if not change:
        return
    if change != project_change(event, change.get("kind")):
        _error("El plan base del cambio ya no coincide con la agenda vigente.")
    if output.get("state") != "proposal":
        _error("Este cambio debe devolver una propuesta, sin nuevas preguntas.")
    after = _agenda(output.get("agenda"), title_key="topic", minute_key="min")
    before = change["base_agenda"]
    if [row["role"] for row in after] != [row["role"] for row in before]:
        _error("El cambio debe conservar la estructura del programa aprobado.")
    old_case = next(row["min"] for row in before if row["role"] == "case")
    new_case = next(row["min"] for row in after if row["role"] == "case")
    new_questions = next(row["min"] for row in after if row["role"] == "questions")
    if new_case < old_case + 5 or new_questions < 10:
        _error("La propuesta debe ampliar el caso al menos cinco minutos y reservar diez minutos para preguntas.")


def preserved_preparation(event):
    """A timing change does not create authority to rewrite preparation tasks."""
    if not event.active_plan_id:
        _error("El plan base ya no está disponible.")
    payload = event.active_plan.payload
    return deepcopy(payload.get("tasks", [])), deepcopy(payload.get("risks", []))


def require_current_schedule(event, speaker, resource):
    """Timing-only changes cannot silently apply an unapproved date or speaker."""
    current = event.starts_at
    for session in event.active_plan.payload["sessions"]:
        try:
            start = datetime.fromisoformat(session["start"])
        except (KeyError, TypeError, ValueError):
            _error("Revisa el inicio y las asignaciones del plan antes de pedir este cambio.")
        if start != current or session.get("speaker") != speaker or session.get("resource") != resource:
            _error("Aprueba primero los cambios de fecha o expositor antes de redistribuir la agenda.")
        current += timedelta(minutes=session["duration_minutes"])
