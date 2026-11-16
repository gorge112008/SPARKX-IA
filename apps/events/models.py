"""Event ownership and the pointer to its currently approved plan."""

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .interview import normalize_interview_answers


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValidationError("Selecciona una zona horaria IANA válida.") from exc


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_events")
    title = models.CharField(max_length=200)
    brief = models.TextField(max_length=12000)
    interview_answers = models.JSONField(default=dict, blank=True)
    planning_constraints = models.JSONField(default=dict, blank=True)
    planning_people = models.JSONField(default=list, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    scheduled_dates = models.JSONField(default=list, blank=True)
    timezone = models.CharField(max_length=64, default="America/Lima", validators=[validate_timezone])
    capacity = models.PositiveIntegerField(default=100)
    organization = models.ForeignKey("directory.Organization", on_delete=models.PROTECT, null=True, blank=True, related_name="events")
    is_synthetic = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    revision = models.PositiveIntegerField(default=1, editable=False)
    review_access_version = models.PositiveIntegerField(default=1, editable=False)
    active_plan = models.ForeignKey("planning.PlanRevision", on_delete=models.PROTECT, null=True, blank=True, related_name="active_for_events", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(capacity__gte=1), name="event_positive_capacity"),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="event_positive_revision"),
            models.CheckConstraint(condition=models.Q(review_access_version__gte=1), name="event_positive_review_access_version"),
        ]

    def clean(self):
        super().clean()
        from .schedule_dates import normalize_scheduled_dates
        try:
            self.scheduled_dates = normalize_scheduled_dates(self.scheduled_dates)
        except ValueError as error:
            raise ValidationError({"scheduled_dates": str(error)}) from error
        if self.scheduled_dates and self.starts_at:
            try:
                selected_zone = ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError, TypeError):
                selected_zone = None  # The field validator reports the invalid zone.
            if selected_zone and self.starts_at.astimezone(selected_zone).date().isoformat() != self.scheduled_dates[0]:
                raise ValidationError({"scheduled_dates": "El inicio debe corresponder al primer día seleccionado."})
        from apps.planning.constraints import normalize_constraints
        try:
            normalize_constraints(self.planning_constraints)
            if not isinstance(self.planning_people, list) or len(self.planning_people) > 3:
                raise ValueError
            for item in self.planning_people:
                if not isinstance(item, dict) or set(item) != {"id", "name", "version"}:
                    raise ValueError
                uuid.UUID(item["id"])
                if type(item["version"]) is not int or item["version"] < 1 or not isinstance(item["name"], str) or not 1 <= len(item["name"]) <= 160:
                    raise ValueError
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError({"planning_constraints": "Revisa las restricciones y las referencias de sus expositores."}) from error
        if self.organization_id and self.organization.owner_id != self.owner_id:
            raise ValidationError({"organization": "Selecciona una institución de tu espacio."})
        try:
            normalize_interview_answers(self.interview_answers)
        except ValueError as exc:
            raise ValidationError({"interview_answers": str(exc)}) from exc
        if self.active_plan_id and self.active_plan.event_id != self.pk:
            raise ValidationError({"active_plan": "El plan debe pertenecer a este evento."})

    def __str__(self):
        return self.title

    @property
    def scheduled_dates_display(self):
        from datetime import date
        return [date.fromisoformat(value) for value in self.scheduled_dates]
