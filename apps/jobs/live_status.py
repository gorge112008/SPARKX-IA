"""Read-only, owner-scoped operational status for the global agent indicator."""

from datetime import datetime, timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.accounts.access import can_organize
from apps.ai_management.agent_identity import AGENT_DISPLAY_NAME
from apps.assistant.models import Message
from apps.events.models import Event
from .models import Job
from .trace import STAGES


RECENT_TERMINAL_AGE = timedelta(minutes=15)
ACTIVE_STATUSES = (Job.Status.QUEUED, Job.Status.RUNNING)
TERMINAL_STATUSES = tuple(status for status in Job.Status.values if status not in ACTIVE_STATUSES)


def _current_actor(actor):
    if not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied
    current = get_user_model().objects.only("id", "is_active", "is_staff", "is_superuser").filter(
        pk=actor.pk, is_active=True,
    ).first()
    if current is None or not can_organize(current):
        raise PermissionDenied
    return current


def _event_preference(event_id, actor):
    if event_id is None:
        return None
    try:
        event_id = event_id if isinstance(event_id, UUID) else UUID(event_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Referencia de evento inválida.") from exc
    if not Event.objects.filter(pk=event_id, owner_id=actor.pk).exists():
        # Deliberately do not distinguish a foreign event from an unknown one.
        raise PermissionDenied
    return event_id


def _stage(job):
    entries = job.execution_trace if isinstance(job.execution_trace, list) else []
    for entry in reversed(entries[:12]):
        if not isinstance(entry, dict):
            continue
        stage = entry.get("stage")
        if not isinstance(stage, str) or stage not in STAGES:
            continue
        try:
            observed = datetime.fromisoformat(entry["at"])
            if timezone.is_naive(observed):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        return stage, STAGES[stage][0]
    return "", job.get_status_display()


def _row(job):
    stage, label = _stage(job)
    return {
        "id": str(job.pk),
        "event_id": str(job.event_id),
        "event_title": job.event.title[:100],
        "event_url": reverse("events:detail", args=[job.event_id]),
        "kind": job.kind,
        "status": job.status,
        "stage": stage,
        "stage_label": label,
        "updated_at": job.updated_at.isoformat(),
    }


def _local_result(actor, preferred, now):
    replies = Message.objects.filter(
        event__owner_id=actor.pk, role=Message.Role.ASSISTANT, job__isnull=True,
        request_key__startswith="local:", created_at__gte=now - RECENT_TERMINAL_AGE,
    )
    if preferred is not None:
        replies = replies.filter(event_id=preferred)
    return replies.select_related("event").only(
        "id", "event_id", "event__id", "event__title", "created_at",
    ).order_by("-created_at", "-id").first()


def build_live_status(actor, event_id=None):
    """Observe at most two own jobs without creating accounts or dispatching work.

    The optional event only changes ordering. Every query still requires both
    current event ownership and the requesting actor's identity.
    """
    current = _current_actor(actor)
    preferred = _event_preference(event_id, current)
    now = timezone.now()
    own = Job.objects.filter(event__owner_id=current.pk, actor_id=current.pk).select_related("event").only(
        "id", "event_id", "event__id", "event__title", "kind", "status", "execution_trace", "updated_at",
    )
    active = own.filter(status__in=ACTIVE_STATUSES).annotate(
        event_rank=Case(When(event_id=preferred, then=Value(0)), default=Value(1), output_field=IntegerField()),
        status_rank=Case(When(status=Job.Status.RUNNING, then=Value(0)), default=Value(1), output_field=IntegerField()),
    ).order_by("event_rank", "status_rank", "created_at", "id")
    jobs = list(active[:2])
    local = None
    if not jobs:
        jobs = list(own.filter(
            status__in=TERMINAL_STATUSES, updated_at__gte=now - RECENT_TERMINAL_AGE,
        ).order_by("-updated_at", "-id")[:1])
        reply = _local_result(current, preferred, now)
        if reply is not None and (not jobs or reply.created_at > jobs[0].updated_at):
            local = {
                "id": str(reply.pk), "event_id": str(reply.event_id),
                "event_title": reply.event.title[:100],
                "event_url": reverse("events:detail", args=[reply.event_id]),
                "created_at": reply.created_at.isoformat(),
            }
            jobs = []
    result = {
        "agent": AGENT_DISPLAY_NAME,
        "state": "local_completed" if local else jobs[0].status if jobs else "idle",
        "jobs": [_row(job) for job in jobs],
        "observed_at": now.isoformat(),
    }
    if local is not None:
        result["local_result"] = local
    return result


@never_cache
@login_required
@require_GET
def view(request):
    try:
        payload = build_live_status(request.user, request.GET.get("event_id"))
    except PermissionDenied:
        return JsonResponse({"error": "Acceso no permitido."}, status=403)
    except ValidationError:
        return JsonResponse({"error": "Referencia de evento inválida."}, status=400)
    return JsonResponse(payload)
