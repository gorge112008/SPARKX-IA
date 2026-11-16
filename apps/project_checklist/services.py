"""Optimistic, owner-scoped updates. No AI calls or financial side effects."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .catalog import ITEMS
from .access import checklist_available_to
from .models import ChecklistProgress


class StaleProgress(Exception):
    """A newer manual declaration must not be overwritten."""


def _existing_update(*, row, status, expected_version, confirmed_checks=None):
    confirmed_checks = [] if confirmed_checks is None else confirmed_checks
    # Accept an exact replay of the most recent effect without another write.
    if row.status == status and row.confirmed_checks == confirmed_checks and expected_version in (row.version, row.version - 1):
        return row, False
    if row.version != expected_version:
        raise StaleProgress
    changed = ChecklistProgress.objects.filter(pk=row.pk, owner=row.owner, version=expected_version).update(
        status=status, confirmed_checks=confirmed_checks, version=F("version") + 1, updated_at=timezone.now(),
    )
    if not changed:
        current = ChecklistProgress.objects.get(pk=row.pk, owner=row.owner)
        if current.status == status and current.confirmed_checks == confirmed_checks and current.version == expected_version + 1:
            return current, False
        raise StaleProgress
    row.refresh_from_db()
    return row, True


def update_progress(*, owner, item_key, status, expected_version, confirmations=None):
    if not checklist_available_to(owner):
        raise PermissionDenied("Este checklist temporal es privado para Jorge.")
    item = ITEMS.get(item_key)
    if item is None or status not in ChecklistProgress.Status.values:
        raise ValidationError("Punto o estado desconocido.")
    if status == ChecklistProgress.Status.NOT_APPLICABLE and not item.optional:
        raise ValidationError("Este punto no admite No aplica.")
    if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 0:
        raise ValidationError("La versión no es válida.")
    confirmations = [] if confirmations is None else confirmations
    allowed = [check.key for check in item.confirmations]
    if (not isinstance(confirmations, (list, tuple))
            or any(not isinstance(value, str) for value in confirmations)
            or len(confirmations) != len(set(confirmations))
            or set(confirmations) - set(allowed)):
        raise ValidationError("Las confirmaciones no son válidas.")
    confirmed_checks = [key for key in allowed if key in confirmations]
    if status == ChecklistProgress.Status.COMPLETED and len(confirmed_checks) != len(allowed):
        raise ValidationError("Completa las confirmaciones personales antes de marcar este punto.")
    with transaction.atomic():
        row = ChecklistProgress.objects.filter(owner=owner, item_key=item_key).first()
        if row is not None:
            return _existing_update(row=row, status=status, expected_version=expected_version, confirmed_checks=confirmed_checks)
        if expected_version != 0:
            raise StaleProgress
        if status == ChecklistProgress.Status.NOT_STARTED and not confirmed_checks:
            return None, False
        row, created = ChecklistProgress.objects.get_or_create(
            owner=owner, item_key=item_key, defaults={"status": status, "version": 1, "confirmed_checks": confirmed_checks},
        )
        if created:
            return row, True
        return _existing_update(row=row, status=status, expected_version=expected_version, confirmed_checks=confirmed_checks)
