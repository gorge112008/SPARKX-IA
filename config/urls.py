from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView
from apps.accounts.views import PortalLoginView, PortalPasswordChangeView
from .local_views import shutdown


def health(request):
    return JsonResponse({"service": "sparkx", "status": "ok"})


urlpatterns = [
    path("health/", health, name="health"),
    path("local/shutdown/", shutdown, name="local_shutdown"),
    path("accounts/login/", PortalLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password/", PortalPasswordChangeView.as_view(), name="password_change"),
    path("accounts/password/done/", RedirectView.as_view(pattern_name="events:index"), name="password_change_done"),
    path("", include("apps.accounts.urls")),
    path("directory/", include("apps.directory.urls")),
    path("", include("apps.registration.urls")),
    path("admin/", admin.site.urls),
    path("ai/", include("apps.ai_management.urls")),
    path("assistant/", include("apps.assistant.urls")),
    path("project-checklist/", include("apps.project_checklist.urls")),
    path("", include("apps.events.urls")),
]
