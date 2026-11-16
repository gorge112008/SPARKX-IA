"""Side-effect-free role and event visibility decisions."""
from django.core.exceptions import PermissionDenied
from django.db.models import F

from .models import PortalAccount


def _active(user):
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_active", False))


def get_role(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if user.is_staff or user.is_superuser:
        return PortalAccount.Role.ADMIN
    # Query instead of trusting a related-object cache after a role change.
    return PortalAccount.objects.filter(user_id=user.pk).values_list("role", flat=True).first() or PortalAccount.Role.ORGANIZER


def is_portal_admin(user):
    return _active(user) and get_role(user) == PortalAccount.Role.ADMIN


def can_organize(user):
    return _active(user) and get_role(user) in {PortalAccount.Role.ADMIN, PortalAccount.Role.ORGANIZER}


def require_portal_admin(user):
    from apps.assistant.execution import deny_agent_admin
    deny_agent_admin()
    if not is_portal_admin(user):
        raise PermissionDenied("Sólo un administrador puede gestionar usuarios.")


def visible_events(user):
    from apps.events.models import Event
    if not _active(user):
        return Event.objects.none()
    if get_role(user) == PortalAccount.Role.REVIEWER:
        return Event.objects.filter(
            review_assignments__reviewer_id=user.pk,
            review_assignments__reviewer__is_active=True,
            review_assignments__reviewer__portal_account__role=PortalAccount.Role.REVIEWER,
            review_assignments__reviewer_version=F("review_assignments__reviewer__portal_account__access_version"),
        )
    return Event.objects.filter(owner_id=user.pk)


def can_view_event(user, event):
    if not _active(user):
        return False
    return visible_events(user).filter(pk=event.pk).exists()
