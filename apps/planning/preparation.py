"""Human preparation commands. Event -> User -> contact/progress/preparation.

The organizer declares evidence; no URL is fetched and no task is completed here.
Historical verification remains stored, but is effective only while its exact
plan, responsible-contact version and completed-progress version are current.
PostgreSQL is required to establish concurrent lock guarantees.
"""
from datetime import datetime
import json
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.directory.models import Person
from apps.events.models import Event
from apps.events.services import require_event_owner
from .models import PreparationChange, TaskPreparation, TaskProgress
from .task_progress import TaskPlanConflict, _task_definitions, _uuid

_UNLOADED = object()


class PreparationConflict(ValidationError):
    def __init__(self):
        super().__init__("La preparación cambió. Recarga y revisa antes de guardar.", code="stale_preparation")


def _evidence(note, url):
    if not isinstance(note, str) or len(note) > 1000:
        raise ValidationError("La nota de evidencia admite hasta 1000 caracteres.")
    if not isinstance(url, str) or len(url) > 1000:
        raise ValidationError("El enlace de evidencia admite hasta 1000 caracteres.")
    note, url = note.strip(), url.strip()
    if url:
        URLValidator(schemes=["https"])(url)
        parsed = urlsplit(url)
        if parsed.username or parsed.password or any(ord(char) < 32 for char in url):
            raise ValidationError("El enlace HTTPS no puede contener credenciales ni caracteres de control.")
    return note, url


def preparation_state(record, event, *, progress=_UNLOADED, responsible_person=_UNLOADED):
    """Read-only effective state; never silently rewrite a historical assertion."""
    if record is None:
        return {"valid": True, "stage": "pending", "label": "Pendiente", "reason": ""}
    reason = ""
    if record.plan_id != event.active_plan_id:
        reason = "El registro pertenece a un plan anterior."
    elif record.stage != TaskPreparation.Stage.PENDING:
        person = (Person.objects.filter(pk=record.responsible_person_id).first()
                  if responsible_person is _UNLOADED else responsible_person)
        if not person or not person.is_active or person.owner_id != event.owner_id:
            reason = "El responsable ya no está disponible en el directorio del organizador."
        elif person.version != record.responsible_person_version:
            reason = "Cambió la ficha del responsable; revisa la evidencia y su asignación."
        elif not (record.evidence_note or record.evidence_url):
            reason = "Falta la evidencia declarada por el organizador."
        elif record.stage == TaskPreparation.Stage.VERIFIED:
            if progress is _UNLOADED:
                progress = TaskProgress.objects.filter(plan_id=record.plan_id, task_id=record.task_id).first()
            if not progress or progress.status != TaskProgress.Status.COMPLETED or progress.version != record.verified_progress_version:
                reason = "La ejecución cambió desde la verificación; revisa y verifica de nuevo."
    return {
        "valid": not reason, "stage": record.stage if not reason else "review_required",
        "label": record.get_stage_display() if not reason else "Requiere revisión del organizador",
        "reason": reason,
    }


@transaction.atomic
def update_task_preparation(*, event, actor, plan_id, task_id, stage, expected_version,
                            request_key, responsible_person_id=None, responsible_person_version=None,
                            due_at=None, evidence_note="", evidence_url=""):
    """CAS command plus durable idempotency receipt; never mutate TaskProgress."""
    current = Event.objects.select_for_update().get(pk=event.pk)
    if not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Inicia sesión para gestionar la preparación.")
    actor = get_user_model().objects.select_for_update().filter(pk=actor.pk).first()
    require_event_owner(current, actor)
    if _uuid(plan_id, "Plan") != current.active_plan_id:
        raise TaskPlanConflict()
    if type(expected_version) is not int or expected_version < 0:
        raise ValidationError("La versión de preparación debe ser un entero no negativo.")
    if not isinstance(task_id, str) or not 1 <= len(task_id.strip()) <= 64:
        raise ValidationError("La tarea debe tener un identificador válido.")
    task_id = task_id.strip()
    if task_id not in _task_definitions(current.active_plan):
        raise ValidationError("La tarea no pertenece al plan vigente.")
    if not isinstance(stage, str) or stage not in TaskPreparation.Stage.values:
        raise ValidationError("La etapa de preparación no está permitida.")
    if due_at is not None and (not isinstance(due_at, datetime) or timezone.is_naive(due_at)):
        raise ValidationError("La fecha límite debe incluir zona horaria.")
    evidence_note, evidence_url = _evidence(evidence_note, evidence_url)
    key = _uuid(request_key, "Solicitud")
    person_id = _uuid(responsible_person_id, "Responsable") if responsible_person_id else None
    if person_id and (type(responsible_person_version) is not int or responsible_person_version < 1):
        raise ValidationError("Selecciona la versión vigente del responsable.")
    if person_id is None and responsible_person_version is not None:
        raise ValidationError("No puede indicarse una versión de responsable sin persona.")
    digest = salted_hmac("sparkx.preparation.command", json.dumps({
        "plan": str(current.active_plan_id), "task": task_id, "actor": actor.pk,
        "version": expected_version, "stage": stage, "person": str(person_id) if person_id else None,
        "person_version": responsible_person_version, "due": due_at.isoformat() if due_at else None,
        "note": evidence_note, "url": evidence_url,
    }, sort_keys=True, ensure_ascii=False), algorithm="sha256").hexdigest()
    # User serialization is shared with contact edits; the selected contact and
    # progress are locked before the row whose verification references them.
    person = Person.objects.select_for_update().filter(pk=person_id, owner_id=actor.pk).first() if person_id else None
    progress = TaskProgress.objects.select_for_update().filter(plan=current.active_plan, task_id=task_id).first()
    record = TaskPreparation.objects.select_for_update().filter(plan=current.active_plan, task_id=task_id).first()
    if record:
        receipt = record.changes.filter(request_key=key).first()
        if receipt:
            if receipt.actor_id != actor.pk or not constant_time_compare(receipt.request_digest, digest):
                raise ValidationError("Esta solicitud ya se utilizó con otros datos.", code="preparation_request_conflict")
            return record  # Historical replay cannot reinstate a stage.
    if expected_version != (record.version if record else 0):
        raise PreparationConflict()
    if person_id and (person is None or not person.is_active):
        raise ValidationError("Selecciona un responsable activo de tu directorio.")
    if person and person.version != responsible_person_version:
        raise ValidationError("Cambió la ficha del responsable. Recarga y revisa su identidad.", code="stale_responsible")
    if stage != TaskPreparation.Stage.PENDING and (not person or not (evidence_note or evidence_url)):
        raise ValidationError("Para preparar, aprobar o verificar necesitas responsable y evidencia humana.")
    if stage == TaskPreparation.Stage.VERIFIED and (not progress or progress.status != TaskProgress.Status.COMPLETED):
        raise ValidationError("Solo puedes verificar una tarea cuya ejecución figure como completada.")
    if record and record.stage != TaskPreparation.Stage.PENDING and stage == TaskPreparation.Stage.PENDING and not evidence_note:
        raise ValidationError("Añade el motivo de la devolución a pendiente en la nota.")
    values = {
        "responsible_person_id": person.pk if person else None,
        "responsible_person_version": person.version if person else None,
        "due_at": due_at, "stage": stage, "evidence_note": evidence_note, "evidence_url": evidence_url,
        "verified_progress_version": progress.version if stage == TaskPreparation.Stage.VERIFIED else None,
    }
    previous_stage = record.stage if record else TaskPreparation.Stage.PENDING
    changed = sorted(field for field, value in values.items() if getattr(record, field, None) != value)
    if record and not changed:
        return record
    now = timezone.now()
    if record is None:
        record = TaskPreparation.objects.create(plan=current.active_plan, task_id=task_id,
            **values, version=1, updated_by=actor, updated_at=now)
    else:
        affected = TaskPreparation.objects.filter(pk=record.pk, version=expected_version).update(
            **values, version=F("version") + 1, updated_by=actor, updated_at=now)
        if affected != 1:
            raise PreparationConflict()
        record.refresh_from_db()
    PreparationChange.objects.create(preparation=record, from_stage=previous_stage, to_stage=stage,
        changed_fields=changed, version=record.version, actor=actor, created_at=now,
        request_key=key, request_digest=digest)
    return record


def preparation_rows(event):
    """Current-plan projection with batched contacts, progress and five receipts."""
    if event.active_plan_id is None:
        return []
    from django.db.models import Prefetch
    stored = {record.task_id: record for record in TaskPreparation.objects.filter(plan_id=event.active_plan_id)
              .select_related("responsible_person", "updated_by").prefetch_related(Prefetch(
                  "changes", queryset=PreparationChange.objects.select_related("actor").order_by("-version")[:5],
                  to_attr="recent_changes"))}
    progress = {record.task_id: record for record in TaskProgress.objects.filter(plan_id=event.active_plan_id)}
    definitions = _task_definitions(event.active_plan)
    return [{"task_id": identifier, "title": definition[0], "record": stored.get(identifier),
             "state": preparation_state(stored.get(identifier), event, progress=progress.get(identifier),
                                        responsible_person=stored[identifier].responsible_person if identifier in stored else None)}
            for identifier, definition in definitions.items()]
