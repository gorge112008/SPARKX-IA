"""Enforce password onboarding, session epochs and read-only reviewer scope."""
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import PortalAccount


class PortalAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = PortalAccount.objects.filter(user_id=request.user.pk).first()
            request.portal_profile = profile
            request.portal_role = (
                PortalAccount.Role.ADMIN if request.user.is_staff or request.user.is_superuser
                else profile.role if profile else PortalAccount.Role.ORGANIZER
            )
            if profile:
                current = request.session.get("portal_auth_version")
                if (current is None and profile.session_version > 1) or (current is not None and current != profile.session_version):
                    logout(request)
                    return redirect("login")
                if current is None:
                    request.session["portal_auth_version"] = profile.session_version
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        match = request.resolver_match
        if not match:
            return None
        from apps.assistant.execution import in_agent_execution
        if in_agent_execution() and (match.app_name in {"admin", "accounts", "ai_management", "project_checklist"}
                or match.url_name == "local_shutdown"):
            raise PermissionDenied("La ejecución del agente no puede acceder a módulos administrativos.")
        if match.url_name in {"login", "logout", "password_change", "password_change_done", "health"}:
            return None
        profile = getattr(request, "portal_profile", None)
        if profile and profile.must_change_password:
            return redirect("password_change")
        if request.portal_role == PortalAccount.Role.REVIEWER:
            if match.app_name == "events" and match.url_name in {"index", "calendar", "detail", "romeo_status"} and request.method in {"GET", "HEAD"}:
                return None
            raise PermissionDenied("Tu rol Revisor permite consultar únicamente los eventos asignados.")
        return None
