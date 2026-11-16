"""Durable application jobs; queue state never authorizes a plan approval."""

import uuid

from django.conf import settings
from django.db import models


class Job(models.Model):
    class Kind(models.TextChoices):
        PLAN = "plan", "Propuesta de plan"
        CHAT = "chat", "Consulta al agente"

    class Status(models.TextChoices):
        QUEUED = "queued", "En cola"
        RUNNING = "running", "En ejecución"
        SUCCEEDED = "succeeded", "Finalizado"
        FAILED = "failed", "Fallido"
        CANCELLED = "cancelled", "Cancelado"
        STALE = "stale", "Obsoleto"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.PROTECT, related_name="jobs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ai_jobs")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    prompt = models.TextField(max_length=6000)
    base_revision = models.PositiveIntegerField()
    base_plan_id = models.UUIDField(null=True, blank=True)
    request_hash = models.CharField(max_length=64, editable=False)
    idempotency_key = models.CharField(max_length=128)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    attempt = models.PositiveSmallIntegerField(default=0)
    claim_token = models.UUIDField(null=True, blank=True, editable=False)
    lease_until = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)
    execution_trace = models.JSONField(default=list, blank=True, editable=False)
    error = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=["status", "created_at"], name="job_queue_idx"),
            models.Index(fields=["actor", "created_at"], name="job_actor_day_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["event", "actor", "idempotency_key"], name="job_idempotency_scope"),
            models.CheckConstraint(condition=models.Q(base_revision__gte=1), name="job_positive_revision"),
            models.CheckConstraint(
                condition=(
                    models.Q(status="running", claim_token__isnull=False, lease_until__isnull=False)
                    | (~models.Q(status="running") & models.Q(claim_token__isnull=True, lease_until__isnull=True))
                ),
                name="job_running_has_lease",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.get_status_display()}"


class UIAction(models.Model):
    """Short-lived browser intentions; completion is a client declaration."""

    class Action(models.TextChoices):
        THEME_LIGHT = "theme_light", "Tema claro"
        THEME_DARK = "theme_dark", "Tema oscuro"
        CALENDAR_OPEN = "calendar_open", "Abrir calendario"
        DIRECTORY_OPEN = "directory_open", "Abrir directorio"
        PEOPLE_SEARCH = "people_search", "Buscar personas"
        EVENTS_OPEN = "events_open", "Abrir eventos"

    class State(models.TextChoices):
        PENDING = "pending", "Pendiente"
        EXECUTING = "executing", "En ejecución"
        COMPLETED = "completed", "Completada por el cliente"
        CANCELLED = "cancelled", "Cancelada"
        FAILED = "failed", "Fallida"
        EXPIRED = "expired", "Caducada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="romeo_ui_actions")
    request_key = models.UUIDField(editable=False)
    tab_id = models.UUIDField(editable=False)
    session_digest = models.CharField(max_length=64, editable=False)
    action = models.CharField(max_length=16, choices=Action.choices)
    query = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    expires_at = models.DateTimeField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["actor", "request_key"], name="ui_action_request_once"),
            models.UniqueConstraint(
                fields=["actor", "tab_id"], condition=models.Q(state__in=["pending", "executing"]),
                name="ui_action_one_active_tab",
            ),
            models.CheckConstraint(condition=models.Q(action__in=["theme_light", "theme_dark", "calendar_open", "directory_open", "people_search", "events_open"]), name="ui_action_known_action"),
            models.CheckConstraint(
                condition=(models.Q(action="people_search") & ~models.Q(query=""))
                | (~models.Q(action="people_search") & models.Q(query="")),
                name="ui_action_query_scope",
            ),
            models.CheckConstraint(condition=models.Q(state__in=["pending", "executing", "completed", "cancelled", "failed", "expired"]), name="ui_action_known_state"),
        ]
