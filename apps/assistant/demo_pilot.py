"""Read-only, owner-scoped data for narrating the existing synthetic pilot."""

from uuid import UUID
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.events.interview import normalize_interview_answers
from apps.events.models import Event

from .local_commands import human_organizer


PILOT_EVENT_ID = UUID("bcf52dbd-206b-4d22-a294-8c487c770c56")


def _response(payload, *, status=200):
    response = JsonResponse(payload, status=status)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@login_required
@require_GET
def demo_pilot(request):
    """Never create a draft or event; an unavailable pilot reveals no foreign data."""
    try:
        actor = human_organizer(request.user)
    except PermissionDenied:
        return _response({"available": False}, status=403)

    event = Event.objects.select_related("organization").filter(
        pk=PILOT_EVENT_ID, owner_id=actor.pk, is_synthetic=True,
    ).first()
    if event is None:
        return _response({"available": False})

    try:
        local_start = event.starts_at.astimezone(ZoneInfo(event.timezone)) if event.starts_at else None
        answers = normalize_interview_answers(event.interview_answers)
    except (ValueError, TypeError, KeyError):
        return _response({"available": False})

    organization = event.organization
    if organization is not None and organization.owner_id != actor.pk:
        organization = None
    return _response({
        "available": True,
        "event_id": str(event.pk),
        "event_url": reverse("events:detail", args=[event.pk]),
        "fields": {
            "title": event.title,
            "organization_id": str(organization.pk) if organization else None,
            "organization_name": organization.name if organization else "",
            "brief": event.brief,
            "date": local_start.date().isoformat() if local_start else None,
            "scheduled_dates": event.scheduled_dates,
            "time": local_start.strftime("%H:%M") if local_start else "",
            "timezone": event.timezone,
            "capacity": event.capacity,
            "is_synthetic": True,
            "interview_answers": answers,
        },
    })
