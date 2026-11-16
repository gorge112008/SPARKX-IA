"""Versioned manual task commands and conservative carry between approved plans.

Lock ordering is Event first, then TaskProgress. Every writer and plan approval
uses that same event lock; PostgreSQL is required to validate concurrent use.
An operational completion is a human declaration, never an LLM verification.
"""

from collections import defaultdict, deque
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.events.models import Event
from apps.events.services import require_event_owner

from .domain import MAX_DEPENDENCIES, MAX_TASKS
from .models import TaskProgress, TaskProgressChange


class TaskProgressConflict(ValidationError):
    def __init__(self):
        super().__init__(
            "La tarea cambió desde que la abriste. Revisa su estado actual antes de guardar.",
            code="stale_task",
        )


class TaskPlanConflict(ValidationError):
    def __init__(self):
        super().__init__(
            "El plan vigente cambió. Revisa las tareas de la versión actual.",
            code="stale_task_plan",
        )


def _uuid(value, label):
    try:
        if not isinstance(value, (str, uuid.UUID)):
            raise ValueError
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(f"{label}: identificador inválido.") from exc


def _task_definitions(plan):
    """Canonical local identities and signatures; no writes or new task authority."""
    tasks = plan.payload.get("tasks") if isinstance(plan.payload, dict) else None
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise ValidationError("El plan no contiene una lista válida de tareas.")
    definitions = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ValidationError("El plan contiene una tarea inválida.")
        identifier = task.get("id")
        dependencies = task.get("depends_on")
        if (not isinstance(identifier, str) or not 1 <= len(identifier.strip()) <= 64
                or not isinstance(task.get("title"), str)
                or not isinstance(task.get("purpose"), str)
                or not isinstance(dependencies, list) or len(dependencies) > MAX_DEPENDENCIES
                or any(not isinstance(item, str) for item in dependencies)):
            raise ValidationError("El plan contiene una definición de tarea inválida.")
        identifier = identifier.strip()
        if identifier in definitions:
            raise ValidationError("El plan contiene identificadores de tarea duplicados.")
        definitions[identifier] = (
            task["title"], task["purpose"], frozenset(item.strip() for item in dependencies),
        )
    return definitions


@transaction.atomic
def update_task_progress(
    *, event, actor, plan_id, task_id, status, expected_version, request_key, note="",
) -> TaskProgress | None:
    """Apply one authorized transition and its receipt together, or return a no-op.

    A replay returns the current record without reinstating its historical
    status. Dependencies are informative here: no cascading state changes.
    """
    current = Event.objects.select_for_update().get(pk=event.pk)
    require_event_owner(current, actor)
    if _uuid(plan_id, "Plan") != current.active_plan_id:
        raise TaskPlanConflict()
    if type(expected_version) is not int or expected_version < 0:
        raise ValidationError("La versión de tarea debe ser un entero no negativo.")
    if not isinstance(task_id, str) or not 1 <= len(task_id.strip()) <= 64:
        raise ValidationError("El identificador de tarea es inválido.")
    task_id = task_id.strip()
    if not isinstance(status, str) or status not in TaskProgress.Status.values:
        raise ValidationError("El estado de tarea no está permitido.")
    if not isinstance(note, str) or len(note) > 1000:
        raise ValidationError("La nota debe contener como máximo 1000 caracteres.")
    note = note.strip()
    request_key = _uuid(request_key, "Solicitud")
    plan = current.active_plan
    if task_id not in _task_definitions(plan):
        raise ValidationError("La tarea no pertenece al plan vigente.")
    progress = TaskProgress.objects.select_for_update().filter(plan=plan, task_id=task_id).first()
    if progress is not None:
        receipt = progress.changes.filter(request_key=request_key).first()
        if receipt is not None:
            if (receipt.to_status != status or receipt.note != note
                    or receipt.version != expected_version + 1 or receipt.actor_id != actor.pk):
                raise ValidationError(
                    "Esta solicitud ya se utilizó con otros datos.", code="task_request_conflict",
                )
            return progress
    actual_version = progress.version if progress is not None else 0
    if expected_version != actual_version:
        raise TaskProgressConflict()
    previous_status = progress.status if progress is not None else TaskProgress.Status.NOT_STARTED
    if status == previous_status:
        return progress
    if (TaskProgress.Status.COMPLETED in (previous_status, status)) and not note:
        raise ValidationError(
            "Añade una nota para completar o reabrir la tarea.", code="note_required",
        )
    now = timezone.now()
    if progress is None:
        progress = TaskProgress.objects.create(
            plan=plan, task_id=task_id, status=status, version=1,
            updated_by=actor, updated_at=now, note=note,
        )
    else:
        changed = TaskProgress.objects.filter(pk=progress.pk, version=expected_version).update(
            status=status, version=F("version") + 1, updated_by=actor, updated_at=now, note=note,
        )
        if changed != 1:
            raise TaskProgressConflict()
        progress.refresh_from_db()
    TaskProgressChange.objects.create(
        progress=progress, from_status=previous_status, to_status=status, version=progress.version,
        actor=actor, created_at=now, note=note, request_key=request_key,
    )
    return progress


def carry_task_progress(previous_plan, new_plan):
    """Carry only unchanged tasks whose complete ancestor chain is unchanged.

    Called inside approval's transaction while its Event row remains locked.
    No status is inferred from a historical plan other than the immediate base;
    no manual transition or new actor/date is fabricated for inherited state.
    """
    if previous_plan is None:
        return []
    if previous_plan.pk == new_plan.pk or previous_plan.event_id != new_plan.event_id:
        raise ValidationError("La herencia requiere dos versiones del mismo evento.")
    # Approval adds one event revision. Any larger gap includes a material
    # EventSpec edit, so equal task text alone cannot preserve its completion.
    if new_plan.candidate.base_revision != previous_plan.candidate.base_revision + 1:
        return []
    before, after = _task_definitions(previous_plan), _task_definitions(new_plan)
    eligible = {identifier for identifier in before.keys() & after.keys()
                if before[identifier] == after[identifier]}
    children = defaultdict(set)
    for identifier, (_, _, dependencies) in after.items():
        for dependency in dependencies:
            children[dependency].add(identifier)
    invalid = deque((before.keys() | after.keys()) - eligible)
    while invalid:
        for child in children[invalid.popleft()]:
            if child in eligible:
                eligible.remove(child)
                invalid.append(child)
    records = TaskProgress.objects.select_for_update().filter(
        plan=previous_plan, task_id__in=eligible,
    )
    carried = [TaskProgress(
        plan=new_plan, task_id=record.task_id, status=record.status, version=1,
        updated_by_id=record.updated_by_id, updated_at=record.updated_at, note=record.note,
        carried_from=record,
    ) for record in records]
    return TaskProgress.objects.bulk_create(carried)
