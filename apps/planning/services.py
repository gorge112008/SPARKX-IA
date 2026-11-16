"""Atomic plan commands with event-first lock ordering.

PostgreSQL is required for row-lock concurrency guarantees. SQLite remains
useful for single-user development, not proof of concurrent correctness.
"""

from copy import deepcopy
import json
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from apps.events.models import Event
from apps.events.services import require_event_owner
from .event_rules import validate_event_plan
from .models import PlanCandidate, PlanRevision
from .task_progress import carry_task_progress

MAX_PAYLOAD_BYTES = 512000


class StalePlanError(ValidationError):
    def __init__(self):
        super().__init__("El evento o su plan vigente cambió. Genera una propuesta con los datos actuales.", code="stale_plan")


def _same_plan_id(expected, actual):
    if expected is None or actual is None:
        return expected is None and actual is None
    try:
        return uuid.UUID(str(expected)) == uuid.UUID(str(actual))
    except (ValueError, TypeError, AttributeError):
        return False


def _check_snapshot(event, base_revision, base_plan_id):
    if type(base_revision) is not int or base_revision != event.revision or not _same_plan_id(base_plan_id, event.active_plan_id):
        raise StalePlanError()


def _json_payload(payload):
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValidationError("La propuesta supera el tamaño máximo permitido.")
        return json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValidationError("La propuesta debe contener únicamente datos JSON válidos.") from exc


@transaction.atomic
def create_candidate(*, event, actor, payload, base_revision, base_plan_id=None):
    """Persist even invalid proposals for review; they cannot be approved."""
    current = Event.objects.select_for_update().get(pk=event.pk)
    require_event_owner(current, actor)
    _check_snapshot(current, base_revision, base_plan_id)
    content = _json_payload(payload)
    validation = validate_event_plan(current, content)
    return PlanCandidate.objects.create(
        event=current,
        created_by=actor,
        payload=content,
        base_revision=base_revision,
        base_plan_id=current.active_plan_id,
        validation=validation,
    )


def _lock_candidate(candidate_id, actor):
    # First lookup is read-only. Ownership cannot change through our services;
    # only the event is locked first, followed by the exact candidate.
    event_id = PlanCandidate.objects.values_list("event_id", flat=True).get(pk=candidate_id)
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    candidate = PlanCandidate.objects.select_for_update().get(pk=candidate_id, event_id=event.pk)
    return event, candidate


@transaction.atomic
def approve_candidate(*, candidate_id, actor):
    event, candidate = _lock_candidate(candidate_id, actor)
    from django.contrib.auth import get_user_model
    current_actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    require_event_owner(event, current_actor)
    if candidate.status == PlanCandidate.Status.APPROVED:
        # A retry returns its historical effect and must never reactivate it.
        revision = PlanRevision.objects.filter(candidate=candidate).first()
        if revision is None:
            raise ValidationError("La aprobación no tiene una revisión asociada; requiere revisión técnica.")
        return revision
    if candidate.status != PlanCandidate.Status.PENDING:
        raise ValidationError("La propuesta ya fue descartada y no puede aprobarse.")
    _check_snapshot(event, candidate.base_revision, candidate.base_plan_id)
    errors = validate_event_plan(event, candidate.payload)
    if errors:
        raise ValidationError(errors)
    latest = PlanRevision.objects.filter(event=event).aggregate(latest=Max("version"))["latest"] or 0
    revision = PlanRevision.objects.create(
        event=event,
        version=latest + 1,
        payload=deepcopy(candidate.payload),
        candidate=candidate,
        approved_by=actor,
    )
    carry_task_progress(event.active_plan, revision)
    candidate.status = PlanCandidate.Status.APPROVED
    candidate.save(update_fields=["status"])
    event.active_plan = revision
    event.revision += 1
    event.save(update_fields=["active_plan", "revision", "updated_at"])
    return revision


@transaction.atomic
def reject_candidate(*, candidate_id, actor):
    _event, candidate = _lock_candidate(candidate_id, actor)
    if candidate.status == PlanCandidate.Status.APPROVED:
        raise ValidationError("Una propuesta aprobada conserva su historial y no puede descartarse.")
    if candidate.status != PlanCandidate.Status.REJECTED:
        candidate.status = PlanCandidate.Status.REJECTED
        candidate.save(update_fields=["status"])
    return candidate
