"""Private declarative progress, separate from event tasks and AI accounting."""
from django.conf import settings
from django.db import models

from .catalog import ITEMS, OPTIONAL_KEYS


class ChecklistProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "No iniciado"
        IN_PROGRESS = "in_progress", "En proceso"
        COMPLETED = "completed", "Completado"
        NOT_APPLICABLE = "not_applicable", "No aplica"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="project_checklist_progress")
    item_key = models.CharField(max_length=48, choices=[(key, item.title) for key, item in ITEMS.items()])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_STARTED)
    confirmed_checks = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("item_key",)
        constraints = [
            models.UniqueConstraint(fields=("owner", "item_key"), name="checklist_owner_item_unique"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="checklist_positive_version"),
            models.CheckConstraint(condition=models.Q(item_key__in=tuple(ITEMS)), name="checklist_known_item"),
            models.CheckConstraint(condition=models.Q(status__in=("not_started", "in_progress", "completed", "not_applicable")), name="checklist_known_status"),
            models.CheckConstraint(condition=~models.Q(status="not_applicable") | models.Q(item_key__in=OPTIONAL_KEYS), name="checklist_optional_na_only"),
        ]
