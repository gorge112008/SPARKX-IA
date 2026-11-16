"""Immutable proposal content and approved historical revisions.

State transitions belong to services. QuerySet.update and raw SQL must not be
used to rewrite immutable payloads; application callers are trusted code.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ImmutableContentMixin:
    immutable_fields = ()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            using = kwargs.get("using") or self._state.db or "default"
            previous = type(self).objects.using(using).get(pk=self.pk)
            if any(getattr(previous, name) != getattr(self, name) for name in self.immutable_fields):
                raise ValidationError("El contenido guardado es inmutable; crea una propuesta nueva.")
        return super().save(*args, **kwargs)


class PlanCandidate(ImmutableContentMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente de revisión"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Descartada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="candidates")
    payload = models.JSONField()
    base_revision = models.PositiveIntegerField()
    base_plan = models.ForeignKey("planning.PlanRevision", on_delete=models.PROTECT, null=True, blank=True, related_name="derived_candidates")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="plan_candidates")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    validation = models.JSONField(default=list)
    immutable_fields = ("event_id", "payload", "base_revision", "base_plan_id", "created_by_id", "created_at", "validation")

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(base_revision__gte=1), name="candidate_positive_revision"),
            models.CheckConstraint(condition=models.Q(status__in=["pending", "approved", "rejected"]), name="candidate_known_status"),
        ]

    def clean(self):
        super().clean()
        if self.base_plan_id and self.base_plan.event_id != self.event_id:
            raise ValidationError({"base_plan": "El plan base debe pertenecer al mismo evento."})

    def __str__(self):
        return f"{self.event_id} / {self.get_status_display()}"


class PlanRevision(ImmutableContentMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="plan_revisions")
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approved_plan_revisions")
    approved_at = models.DateTimeField(default=timezone.now, editable=False)
    candidate = models.OneToOneField(PlanCandidate, on_delete=models.PROTECT, related_name="approved_revision")
    immutable_fields = ("event_id", "version", "payload", "approved_by_id", "approved_at", "candidate_id")

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=("event", "version"), name="unique_event_plan_version"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="plan_positive_version"),
        ]

    def clean(self):
        super().clean()
        if self.candidate_id and self.candidate.event_id != self.event_id:
            raise ValidationError({"candidate": "La propuesta debe pertenecer al mismo evento."})

    def __str__(self):
        return f"{self.event_id} / v{self.version}"


class TaskProgress(models.Model):
    """Human-declared execution state, separate from approved plan content."""

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "No iniciado"
        IN_PROGRESS = "in_progress", "En proceso"
        COMPLETED = "completed", "Completado"

    plan = models.ForeignKey(PlanRevision, on_delete=models.CASCADE, related_name="task_progress")
    task_id = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_STARTED)
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_task_progress",
    )
    updated_at = models.DateTimeField(default=timezone.now, editable=False)
    note = models.TextField(max_length=1000, blank=True, default="")
    carried_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="carried_to",
        editable=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plan", "task_id"), name="unique_plan_task_progress"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="task_progress_version"),
            models.CheckConstraint(
                condition=models.Q(status__in=["not_started", "in_progress", "completed"]),
                name="task_progress_known_status",
            ),
            models.CheckConstraint(condition=~models.Q(task_id=""), name="task_progress_nonempty_id"),
        ]

    def save(self, *args, **kwargs):
        if not isinstance(self.task_id, str) or not 1 <= len(self.task_id.strip()) <= 64:
            raise ValidationError({"task_id": "La tarea debe tener un identificador válido."})
        self.task_id = self.task_id.strip()
        return super().save(*args, **kwargs)


class TaskProgressChange(models.Model):
    """Append-only manual transitions; inherited state does not invent a change."""

    progress = models.ForeignKey(TaskProgress, on_delete=models.CASCADE, related_name="changes")
    from_status = models.CharField(max_length=16, choices=TaskProgress.Status.choices)
    to_status = models.CharField(max_length=16, choices=TaskProgress.Status.choices)
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="task_progress_changes",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    note = models.TextField(max_length=1000, blank=True, default="")
    request_key = models.UUIDField()

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=("progress", "version"), name="unique_task_change_version"),
            models.UniqueConstraint(
                fields=("progress", "request_key"), name="unique_task_change_request",
            ),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="task_change_version"),
            models.CheckConstraint(
                condition=models.Q(from_status__in=["not_started", "in_progress", "completed"]),
                name="task_change_known_from",
            ),
            models.CheckConstraint(
                condition=models.Q(to_status__in=["not_started", "in_progress", "completed"]),
                name="task_change_known_to",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_status=models.F("to_status")),
                name="task_change_distinct_states",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("El historial de tareas es inmutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial de tareas no se elimina individualmente.")


class TaskPreparation(models.Model):
    """Organizer-declared evidence and responsibility, outside plan/progress."""

    class Stage(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PREPARED = "prepared", "Preparado por el organizador"
        APPROVED = "approved", "Aprobado por el organizador"
        VERIFIED = "verified", "Verificado por el organizador"

    plan = models.ForeignKey(PlanRevision, on_delete=models.CASCADE, related_name="task_preparations")
    task_id = models.CharField(max_length=64)
    responsible_person = models.ForeignKey(
        "directory.Person", on_delete=models.PROTECT, null=True, blank=True,
        related_name="task_preparations",
    )
    responsible_person_version = models.PositiveIntegerField(null=True, blank=True, editable=False)
    due_at = models.DateTimeField(null=True, blank=True)
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.PENDING)
    evidence_note = models.TextField(max_length=1000, blank=True, default="")
    evidence_url = models.URLField(max_length=1000, blank=True, default="")
    verified_progress_version = models.PositiveIntegerField(null=True, blank=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_task_preparations",
    )
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plan", "task_id"), name="unique_plan_task_preparation"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="preparation_positive_version"),
            models.CheckConstraint(condition=~models.Q(task_id=""), name="preparation_nonempty_task"),
            models.CheckConstraint(condition=models.Q(stage__in=["pending", "prepared", "approved", "verified"]), name="preparation_known_stage"),
        ]


class PreparationChange(models.Model):
    """Append-only receipt: field names, stages and digest; no evidence copies."""

    preparation = models.ForeignKey(TaskPreparation, on_delete=models.CASCADE, related_name="changes")
    from_stage = models.CharField(max_length=16, choices=TaskPreparation.Stage.choices)
    to_stage = models.CharField(max_length=16, choices=TaskPreparation.Stage.choices)
    changed_fields = models.JSONField(default=list)
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="preparation_changes")
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    request_key = models.UUIDField()
    request_digest = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=("preparation", "version"), name="unique_preparation_change_version"),
            models.UniqueConstraint(fields=("preparation", "request_key"), name="unique_preparation_change_request"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="preparation_change_positive_version"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("El historial de preparación es inmutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial de preparación no se elimina individualmente.")
