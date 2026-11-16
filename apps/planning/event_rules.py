"""Canonical event limits and current, owner-scoped speaker reservations."""
from copy import deepcopy
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import unicodedata

from .domain import validate_plan


def _name(value):
    return unicodedata.normalize("NFC", " ".join(value.split())).casefold()


def context_constraints(event):
    from .constraints import normalize_constraints
    from apps.directory.models import Person
    from apps.events.models import Event

    configured = normalize_constraints(getattr(event, "planning_constraints", {}))
    if not configured:
        return {}
    result = deepcopy(configured)
    if event.starts_at:
        start = max(datetime.fromisoformat(result["window"]["start"]), event.starts_at)
        result["window"]["start"] = start.isoformat()
        duration = event.interview_answers.get("duration_minutes", {})
        if duration.get("status") == "confirmed" and len(getattr(event, "scheduled_dates", [])) <= 1:
            end = event.starts_at + timedelta(minutes=int(duration["value"]))
            result["window"]["end"] = min(datetime.fromisoformat(result["window"]["end"]), end).isoformat()
        result = normalize_constraints(result)
    references = getattr(event, "planning_people", [])
    if not isinstance(references, list) or len(references) > 3:
        raise ValueError("Revisa los expositores de las restricciones.")
    people = {str(person.pk): person for person in Person.objects.filter(
        owner_id=event.owner_id, pk__in=[item["id"] for item in references], is_active=True,
        category=Person.Category.SPEAKER,
    )}
    names = set()
    for reference in references:
        person = people.get(reference["id"])
        if person is None or person.version != reference["version"] or person.full_name != reference["name"]:
            raise ValueError("El directorio de expositores cambió. Revisa y guarda de nuevo las restricciones.")
        names.add(_name(person.full_name))
    if names != {_name(item["name"]) for item in result["speakers"]}:
        raise ValueError("Las restricciones no coinciden con los expositores seleccionados.")
    speakers = {_name(item["name"]): item for item in result["speakers"]}
    resources = {_name(item["name"]): item for item in result["resources"]}
    window_start = datetime.fromisoformat(result["window"]["start"])
    window_end = datetime.fromisoformat(result["window"]["end"])
    other_events = Event.objects.filter(owner_id=event.owner_id, active_plan__isnull=False).exclude(pk=event.pk).select_related("active_plan")
    if other_events.count() > 100:
        raise ValueError("La comprobación de esta demo admite hasta cien eventos con agenda. Revisa la disponibilidad manualmente.")
    for other in other_events:
        for session in other.active_plan.payload.get("sessions", []):
            speaker = speakers.get(_name(session.get("speaker", "")))
            resource = resources.get(_name(session.get("resource", "")))
            if speaker is None and resource is None:
                continue
            try:
                start = datetime.fromisoformat(session["start"].replace("Z", "+00:00"))
                end = start + timedelta(minutes=session["duration_minutes"])
                if start < window_end and end > window_start:
                    for entity in (speaker, resource):
                        if entity is not None:
                            entity["busy"].append({"start": start.isoformat(), "end": end.isoformat()})
            except (TypeError, ValueError, KeyError, OverflowError):
                raise ValueError("Una agenda aprobada necesita revisión antes de comprobar disponibilidad.") from None
    return normalize_constraints(result)


def validate_event_plan(event, payload):
    """Validate domain, confirmed event time and optional explicit constraints."""
    errors = validate_plan(payload)
    if errors:
        return errors
    starts_at = event.starts_at
    duration = getattr(event, "interview_answers", {}).get("duration_minutes", {})
    deadline = None
    selected_days = set(getattr(event, "scheduled_dates", []))
    daily_spans = {}
    if starts_at and duration.get("status") == "confirmed" and len(selected_days) <= 1:
        try:
            deadline = starts_at + timedelta(minutes=int(duration["value"]))
        except (KeyError, ValueError, TypeError, OverflowError):
            errors.append("Revisa la duración confirmada de la entrevista.")
    for index, session in enumerate(payload["sessions"], 1):
        start = datetime.fromisoformat(session["start"].replace("Z", "+00:00"))
        end = start + timedelta(minutes=session["duration_minutes"])
        if starts_at and start < starts_at:
            errors.append(f"La sesión {index} empieza antes del inicio de la ficha.")
        if deadline and end > deadline:
            errors.append(f"La sesión {index} excede la duración confirmada del evento.")
        if selected_days:
            zone = ZoneInfo(event.timezone)
            first_day = start.astimezone(zone).date()
            # Ending exactly at midnight occupies only the preceding day.
            last_day = (end - timedelta(microseconds=1)).astimezone(zone).date()
            day = first_day
            while day <= last_day:
                if day.isoformat() not in selected_days:
                    errors.append(f"La sesión {index} ocupa un día que no seleccionaste para el evento.")
                    break
                lower = max(start.timestamp(), datetime.combine(day, time.min, tzinfo=zone).timestamp())
                upper = min(end.timestamp(), datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).timestamp())
                old_lower, old_upper = daily_spans.get(day, (lower, upper))
                daily_spans[day] = (min(old_lower, lower), max(old_upper, upper))
                day += timedelta(days=1)
    if len(selected_days) > 1 and duration.get("status") == "confirmed":
        try:
            total_seconds = sum(upper - lower for lower, upper in daily_spans.values())
            if total_seconds > int(duration["value"]) * 60:
                errors.append("Las jornadas suman más minutos que la duración total confirmada del evento, incluidos sus descansos.")
        except (KeyError, ValueError, TypeError):
            errors.append("Revisa la duración total confirmada del evento.")
    if getattr(event, "planning_constraints", {}):
        from .constraints import validate_event_plan as validate_constraints
        try:
            errors.extend(validate_constraints(payload, context_constraints(event)))
        except ValueError as error:
            errors.append(str(error))
    return errors
