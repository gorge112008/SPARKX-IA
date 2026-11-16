"""Bounded presentation helpers; persisted plan payloads remain untouched."""

from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import template
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..domain import MAX_DEPENDENCIES, MAX_SESSIONS, MAX_TASKS

register = template.Library()


@register.filter
def event_datetime(value, zone_name):
    """Return an aware event-local datetime, or None for an invalid input.

    A naive timestamp has no unambiguous instant and is deliberately not
    interpreted in the server's timezone. No value is stored or mutated.
    """
    try:
        parsed = parse_datetime(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or timezone.is_naive(parsed):
            return None
        if not isinstance(zone_name, str):
            return None
        return timezone.localtime(parsed, ZoneInfo(zone_name))
    except (ValueError, TypeError, OverflowError, ZoneInfoNotFoundError):
        return None


def _text(value):
    """Keep ordinary text, without carrying HTML-safe string subclasses."""
    return value[:] if isinstance(value, str) else ""


def _records(payload, key, limit):
    if not isinstance(payload, dict):
        return []
    values = payload.get(key)
    if not isinstance(values, list):
        return []
    return [value for value in values[:limit] if isinstance(value, dict)]


@register.filter
def agenda_rows(payload, zone_name):
    """Present every valid session in order, with an elapsed-time end instant.

    Adding the duration in UTC matters during DST changes: an hour-long
    session remains an hour long even when the local clock skips or repeats.
    Invalid candidates may still be displayed for review, so malformed fields
    have empty/unknown values instead of fabricated dates or durations.
    """
    rows = []
    for session in _records(payload, "sessions", MAX_SESSIONS):
        row = {key: _text(session.get(key))
               for key in ("id", "title", "start", "speaker", "resource")}
        duration = session.get("duration_minutes")
        duration = duration if type(duration) is int and 1 <= duration <= 1440 else None
        local_start = event_datetime(row["start"], zone_name)
        local_end = None
        if local_start is not None and duration is not None:
            try:
                end = local_start.astimezone(dt_timezone.utc) + timedelta(minutes=duration)
                local_end = event_datetime(end, zone_name)
            except (ValueError, OverflowError):
                pass
        row.update(
            duration_minutes=duration,
            local_start=local_start,
            local_end=local_end,
            crosses_day=bool(local_start and local_end and local_start.date() != local_end.date()),
        )
        rows.append(row)
    return rows


@register.filter
def preparation_rows(payload):
    """Resolve task dependencies into display titles without changing the graph.

    Unknown IDs stay visible for review. Strings remain escaped by the Django
    template engine; this helper never returns HTML or marks content as safe.
    """
    tasks = _records(payload, "tasks", MAX_TASKS)
    titles = {}
    for task in tasks:
        identifier = _text(task.get("id")).strip()
        title = _text(task.get("title"))
        if identifier and title.strip():
            titles.setdefault(identifier, title)
    rows = []
    for task in tasks:
        row = {key: _text(task.get(key)) for key in ("id", "title", "purpose", "status")}
        dependencies = task.get("depends_on")
        row["depends_on_titles"] = [
            titles.get(dependency.strip(), _text(dependency))
            for dependency in dependencies[:MAX_DEPENDENCIES]
            if isinstance(dependency, str)
        ] if isinstance(dependencies, list) else []
        rows.append(row)
    return rows
