"""One explicitly named account owns the optional personal project tool."""
from django.conf import settings


def checklist_available_to(user):
    from apps.assistant.execution import in_agent_execution
    if in_agent_execution():
        return False
    return bool(
        getattr(settings, "SPARKX_CHECKLIST_ENABLED", False)
        and user and user.is_authenticated and user.is_active
        and (user.is_staff or user.is_superuser)
        and user.get_username() == getattr(settings, "SPARKX_CHECKLIST_OWNER_USERNAME", "adminjorge")
    )
