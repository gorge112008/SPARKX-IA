"""Read-only calendar projection of authorized events and approved plans.

Dates remain in each event's own IANA time zone. A proposal awaiting approval
never supplies agenda entries, and deriving a date from a plan does not confirm
an otherwise undated event. The HTTP endpoint supplies authorized projections.
"""

import calendar as month_calendar
import re
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from .catalog import (
    MAX_YEAR, MIN_YEAR, day_sessions, filter_entries, filter_query,
    parse_filters, project_event,
)
MONTH_NAMES = (
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
WEEKDAYS = (
    {"short": "Lun", "name": "Lunes"},
    {"short": "Mar", "name": "Martes"},
    {"short": "Mié", "name": "Miércoles"},
    {"short": "Jue", "name": "Jueves"},
    {"short": "Vie", "name": "Viernes"},
    {"short": "Sáb", "name": "Sábado"},
    {"short": "Dom", "name": "Domingo"},
)


def _selection(params, today):
    """Validate bounded, unambiguous query parameters before date arithmetic."""
    month_value = params.get("month")
    day_value = params.get("day")
    selected_day = None
    if day_value is not None:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day_value):
            raise ValueError("El día debe tener formato AAAA-MM-DD.")
        try:
            selected_day = date.fromisoformat(day_value)
        except ValueError as error:
            raise ValueError("Selecciona un día válido del calendario.") from error
        if not MIN_YEAR <= selected_day.year <= MAX_YEAR:
            raise ValueError(f"El calendario admite años entre {MIN_YEAR} y {MAX_YEAR}.")
    if month_value is not None:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month_value):
            raise ValueError("El mes debe tener formato AAAA-MM.")
        try:
            month = date.fromisoformat(month_value + "-01")
        except ValueError as error:
            raise ValueError("Selecciona un mes válido del calendario.") from error
        if not MIN_YEAR <= month.year <= MAX_YEAR:
            raise ValueError(f"El calendario admite años entre {MIN_YEAR} y {MAX_YEAR}.")
    else:
        month = (selected_day or today).replace(day=1)
    if selected_day is None:
        selected_day = today if (today.year, today.month) == (month.year, month.month) else month
    if (selected_day.year, selected_day.month) != (month.year, month.month):
        raise ValueError("El día seleccionado debe pertenecer al mes mostrado.")
    return month, selected_day


def _url(day, filters=None):
    if not MIN_YEAR <= day.year <= MAX_YEAR:
        return None
    return reverse("events:calendar") + "?" + filter_query(
        filters or {}, month=day.strftime("%Y-%m"), day=day.isoformat(),
    )


def build_calendar_context(*, params, events=(), entries=None, today=None):
    """Use the catalog's complete authorized projections, never a tool/page slice."""
    today = today or timezone.localdate()
    month, selected_day = _selection(params, today)
    filters = parse_filters(params)
    entries = filter_entries(
        [project_event(event) for event in events] if entries is None else entries,
        filters,
    )
    for entry in entries:
        entry["calendar_url"] = _url(entry["date"], filters) if entry["date"] else None
    month_events = [entry for entry in entries if any((day.year, day.month) == (month.year, month.month) for day in entry.get("dates", [entry["date"]]) if day is not None)]
    day_events = []
    for entry in entries:
        sessions = day_sessions(entry["sessions"], selected_day)
        if selected_day in entry.get("dates", [entry["date"]]) or sessions:
            day_events.append({**entry, "sessions": sessions})
    by_day = {}
    for entry in entries:
        for day in entry.get("dates", [entry["date"]]):
            if day is not None:
                by_day.setdefault(day, []).append(entry)
    weeks = []
    for week in month_calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
        weeks.append([{
            "date": day,
            "iso": day.isoformat(),
            "number": day.day,
            "in_month": day.month == month.month,
            "is_today": day == today,
            "is_selected": day == selected_day,
            "url": _url(day, filters),
            "events": by_day.get(day, []),
        } for day in week])
    previous = month - timedelta(days=1)
    following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    undated = [entry for entry in entries if entry["date"] is None]
    return {
        "month": month,
        "month_key": month.strftime("%Y-%m"),
        "month_label": f"{MONTH_NAMES[month.month]} {month.year}",
        "today": today,
        "selected_day": selected_day,
        "selected_day_label": f"{WEEKDAYS[selected_day.weekday()]['name']}, {selected_day.day} de {MONTH_NAMES[selected_day.month].lower()} de {selected_day.year}",
        "previous_url": _url(previous.replace(day=1), filters),
        "next_url": _url(following, filters),
        "today_url": _url(today, filters),
        "weekdays": WEEKDAYS,
        "weeks": weeks,
        "month_events": month_events,
        "day_events": day_events,
        "undated_events": undated,
        "event_count": len(entries),
        "scheduled_count": len(month_events),
        "approved_count": sum(entry["has_plan"] for entry in month_events),
        "undated_count": len(undated),
        "filter_values": filters,
    }
