"""Publication is explicit; registration data never creates a directory contact."""
import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .normalization import registration_values


def public_token():
    # 32 random bytes = 256 bits. Never derive the public link from an event ID.
    return secrets.token_urlsafe(32)


class RegistrationPage(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Abiertas"
        CLOSED = "closed", "Cerradas"

    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="registration_page")
    public_token = models.CharField(max_length=43, unique=True, default=public_token, editable=False)
    state = models.CharField(max_length=8, choices=State.choices, default=State.CLOSED)
    version = models.PositiveIntegerField(default=1, editable=False)
    published_plan = models.ForeignKey("planning.PlanRevision", on_delete=models.PROTECT, related_name="registration_publications")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="registration_publications")
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(state__in=["open", "closed"]), name="registration_page_known_state"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="registration_page_positive_version"),
        ]

    def clean(self):
        super().clean()
        if self.published_plan_id and self.published_plan.event_id != self.event_id:
            raise ValidationError({"published_plan": "El plan aprobado debe pertenecer al evento."})


class Registration(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Activa"
        CANCELLED = "cancelled", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="registrations")
    full_name = models.CharField(max_length=120)
    email = models.EmailField(max_length=254)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("event", "email"), name="registration_unique_event_email"),
            models.CheckConstraint(condition=models.Q(status__in=["active", "cancelled"]), name="registration_known_status"),
        ]
        indexes = [models.Index(fields=("event", "status"), name="registration_active_scope")]

    def clean(self):
        super().clean()
        self.full_name, self.email = registration_values(self.full_name, self.email)


class RegistrationSubmission(models.Model):
    """A consumed command key, without a name, email, IP or inferred identity."""
    page = models.ForeignKey(RegistrationPage, on_delete=models.CASCADE, related_name="submissions")
    request_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("page", "request_key"), name="registration_submission_unique")]
