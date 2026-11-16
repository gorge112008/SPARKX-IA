"""Visibility for optional internal project tools; views enforce access separately."""
from apps.project_checklist.access import checklist_available_to
from apps.accounts.access import get_role
from apps.assistant.profile_settings import profile_for
from .local_runtime import local_shutdown_available


def project_tools(request):
    user = getattr(request, "user", None)
    role = getattr(request, "portal_role", None) or get_role(user)
    active = bool(user and user.is_authenticated and user.is_active)
    return {
        "project_checklist_visible": checklist_available_to(user),
        "portal_users_visible": active and role == "admin",
        "portal_can_organize": active and role in {"admin", "organizer"},
        "portal_role": role if active else "",
        "portal_is_reviewer": role == "reviewer",
        "local_shutdown_visible": local_shutdown_available(request),
        "gica_profile": profile_for(user) if active and role in {"admin", "organizer"} else {},
    }
