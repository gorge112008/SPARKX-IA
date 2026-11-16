"""Portal roles remain independent from Django's technical staff privileges."""
from django.conf import settings
from django.db import models


class PortalAccount(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        ORGANIZER = "organizer", "Organizador"
        REVIEWER = "reviewer", "Revisor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portal_account")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.ORGANIZER)
    version = models.PositiveIntegerField(default=1)
    session_version = models.PositiveIntegerField(default=1)
    access_version = models.PositiveIntegerField(default=1)
    must_change_password = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=["admin", "organizer", "reviewer"]), name="portal_account_known_role"),
            models.CheckConstraint(condition=models.Q(version__gte=1, session_version__gte=1, access_version__gte=1), name="portal_account_positive_versions"),
        ]


class AdminRosterLock(models.Model):
    """One migration-created row serializes portal account and role changes."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="admin_roster_singleton")]


class LoginAttemptWindow(models.Model):
    """Only a keyed digest is persisted; no address or login identifier."""
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)


class EventReviewAssignment(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="review_assignments")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_review_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="review_assignments_granted")
    reviewer_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("reviewer_id",)
        constraints = [
            models.UniqueConstraint(fields=("event", "reviewer"), name="event_reviewer_unique"),
            models.CheckConstraint(condition=models.Q(reviewer_version__gte=1), name="review_assignment_positive_version"),
        ]
