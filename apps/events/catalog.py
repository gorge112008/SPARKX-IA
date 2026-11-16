"""Authorized, read-only event lookup shared by HTTP and local agent tools.

Dates are civil dates in each event's own zone. A range includes the event's
displayed date or an approved session occupying that range. Contact employers,
pending candidates and historical approved plans never supply matches.
"""

import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.urls import reverse
from django.utils import timezone

from apps.accounts.access import can_organize, visible_events
from apps.directory.normalization import search_key

MIN_YEAR = 1900
MAX_YEAR = 2100
FILTER_NAMES = ("q", "organization", "from", "to", "plan")


def _parameter(params, name):
    if hasattr(params, "getlist") and len(params.getlist(name)) > 1:
        raise ValueError("Cada filtro debe aparecer una sola vez.")
    value = params.get(name, "")
    if not isinstance(value, str):
        raise ValueError("Los filtros deben contener texto válido.")
    return value.strip()


def _date(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Las fechas deben tener formato AAAA-MM-DD.")
    try:
        result = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Selecciona una fecha válida.") from error
    if not MIN_YEAR <= result.year <= MAX_YEAR:
        raise ValueError(f"Las fechas admiten años entre {MIN_YEAR} y {MAX_YEAR}.")
    return result


def parse_filters(params):
    """Normalize only this catalog's filters, preserving UI month/day controls."""
    values = {name: _parameter(params, name) for name in FILTER_NAMES}
    values["q"] = " ".join(values["q"].split())
    if len(values["q"]) > 200:
        raise ValueError("La búsqueda admite hasta 200 caracteres.")
    if values["organization"]:
        try:
            values["organization"] = str(UUID(values["organization"]))
        except (ValueError, AttributeError) as error:
            raise ValueError("Selecciona una empresa válida.") from error
    first = _date(values["from"]) if values["from"] else None
    last = _date(values["to"]) if values["to"] else None
    if first and last and first > last:
        raise ValueError("La fecha inicial no puede ser posterior a la final.")
    if values["plan"] not in {"", "approved", "pending"}:
        raise ValueError("Selecciona un estado de plan válido.")
    return values


def filter_query(values, **extra):
    """Encode validated filters and explicit navigation controls without loss."""
    return urlencode({**{key: values[key] for key in FILTER_NAMES if values.get(key)}, **extra})


def event_sessions(event, zone):
    if not event.active_plan_id or event.active_plan.event_id != event.pk:
        return []
    payload = event.active_plan.payload
    raw_sessions = payload.get("sessions", []) if isinstance(payload, dict) else []
    if not isinstance(raw_sessions, list):
        return []
    result = []
    for session in raw_sessions[:200]:
        if not isinstance(session, dict):
            continue
        duration = session.get("duration_minutes")
        raw_start = session.get("start")
        if type(duration) is not int or not 1 <= duration <= 1440 or not isinstance(raw_start, str) or len(raw_start) > 64:
            continue
        try:
            parsed = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                continue
            start = parsed.astimezone(zone)
            end = (parsed.astimezone(UTC) + timedelta(minutes=duration)).astimezone(zone)
        except (ValueError, TypeError, OverflowError):
            continue
        time_label = f"{start:%H:%M}–{end:%H:%M}"
        if end.date() != start.date():
            time_label += f" · hasta {end:%d/%m}"
        result.append({
            "id": session.get("id", ""), "title": session.get("title", "Sesión"),
            "start": start, "end": end, "time_label": time_label,
            "speaker": session.get("speaker", ""), "resource": session.get("resource", ""),
            "duration_minutes": duration,
        })
    return sorted(result, key=lambda item: (item["start"], str(item["id"])))


def _organization(event):
    if not getattr(event, "organization_id", None):
        return None
    organization = event.organization
    # A corrupt relation must never expose another owner's company, including
    # through search, counts, selectors, tool results or a harmless-looking label.
    if organization is None or organization.owner_id != event.owner_id:
        return None
    return organization


def project_event(event):
    try:
        zone = ZoneInfo(event.timezone)
        timezone_warning = False
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = ZoneInfo("UTC")
        timezone_warning = True
    sessions = event_sessions(event, zone)
    starts_at = event.starts_at
    if starts_at is not None:
        starts_at = starts_at.astimezone(zone) if timezone.is_aware(starts_at) else None
    date_source = "event" if starts_at is not None else "plan" if sessions else None
    displayed_start = starts_at or (sessions[0]["start"] if sessions else None)
    from .schedule_dates import normalize_scheduled_dates
    try:
        selected_dates = [date.fromisoformat(value) for value in normalize_scheduled_dates(getattr(event, "scheduled_dates", []))]
    except ValueError:
        selected_dates = []
    if selected_dates:
        date_source = "event"
    has_plan = bool(event.active_plan_id and event.active_plan.event_id == event.pk)
    return {
        "event": event, "url": reverse("events:detail", kwargs={"event_id": event.pk}),
        "date": selected_dates[0] if selected_dates else displayed_start.date() if displayed_start else None,
        "dates": selected_dates or ([displayed_start.date()] if displayed_start else []),
        "starts_at": displayed_start,
        "start_time": displayed_start.strftime("%H:%M") if displayed_start else "Por definir",
        "timezone": zone.key, "timezone_warning": timezone_warning,
        "has_plan": has_plan,
        "plan_version": event.active_plan.version if has_plan else None,
        "date_source": date_source, "sessions": sessions,
        "organization": _organization(event),
        "is_synthetic": bool(getattr(event, "is_synthetic", False)),
    }


def _session_last_day(session):
    last = session["end"].date()
    if session["end"].time().replace(tzinfo=None) == datetime.min.time():
        last -= timedelta(days=1)
    return last


def day_sessions(sessions, selected_day):
    result = []
    for session in sessions:
        start_day = session["start"].date()
        last_day = _session_last_day(session)
        if start_day <= selected_day <= last_day:
            result.append({
                **session,
                "continues_from_previous": start_day < selected_day,
                "continues_to_next": last_day > selected_day,
            })
    return result


def _in_range(entry, first, last):
    if not first and not last:
        return True
    if any((not first or first <= value) and (not last or value <= last) for value in entry.get("dates", [entry["date"]]) if value is not None):
        return True
    return any(
        (not first or first <= _session_last_day(session))
        and (not last or session["start"].date() <= last)
        for session in entry["sessions"]
    )


def filter_entries(entries, values):
    """Filter complete projections before sorting, counting or truncating."""
    query = search_key(values["q"])
    first = _date(values["from"]) if values["from"] else None
    last = _date(values["to"]) if values["to"] else None
    result = []
    for entry in entries:
        organization = entry["organization"]
        if values["organization"] and (organization is None or str(organization.pk) != values["organization"]):
            continue
        if query:
            haystack = search_key(" ".join((
                entry["event"].title, getattr(entry["event"], "brief", ""),
                organization.name if organization else "",
            )))
            if query not in haystack:
                continue
        if values["plan"] and entry["has_plan"] != (values["plan"] == "approved"):
            continue
        if _in_range(entry, first, last):
            result.append(entry)
    return sorted(result, key=lambda item: (
        item["date"] or date.max, item["start_time"],
        search_key(item["event"].title), str(item["event"].pk),
    ))


def find_events(*, actor, params, limit=None):
    """Return authorized projections and selectors; optional limit is applied last.

    ``limit=None`` provides the complete result for UI pagination/calendar;
    local tools can pass 10 (maximum 100). This function never queues AI work.
    """
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 100):
        raise ValueError("El límite debe ser un entero entre 1 y 100.")
    values = parse_filters(params)
    entries = [project_event(event) for event in visible_events(actor).select_related("active_plan", "organization")]
    organizations = {entry["organization"].pk: entry["organization"] for entry in entries if entry["organization"]}
    if can_organize(actor):
        from apps.directory.models import Organization
        organizations.update({item.pk: item for item in Organization.objects.filter(owner_id=actor.pk, is_active=True)})
    filtered = filter_entries(entries, values)
    total = len(filtered)
    return {
        "entries": filtered if limit is None else filtered[:limit],
        "organization_options": sorted(organizations.values(), key=lambda item: (search_key(item.name), str(item.pk))),
        "filter_values": values, "total": total,
        "has_more": limit is not None and total > limit,
        "has_filters": any(values.values()),
    }
