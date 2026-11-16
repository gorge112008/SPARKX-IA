from django.urls import path

from . import views
from . import control_views

app_name = "ai_management"
urlpatterns = [
    path("control/", control_views.control, name="control"),
    path("control/credentials/save/", control_views.credential_save, name="credential_save"),
    path("control/credentials/remove/", control_views.credential_remove, name="credential_remove"),
    path("control/agent/", control_views.agent_save, name="agent_save"),
    path("control/pool/", control_views.pool_entry_save, name="pool_entry_save"),
    path("", views.index, name="index"),
    path("providers/", views.providers, name="providers"),
    path("profiles/new/", views.profile_edit, name="profile_create"),
    path("profiles/<int:profile_id>/", views.profile_edit, name="profile_edit"),
    path("budget/", views.budget, name="budget"),
    path("calculator/", views.calculator, name="calculator"),
    path("compare/", views.compare, name="compare"),
    path("usage/", views.usage, name="usage"),
    path("usage/<int:usage_id>/reconcile/", views.reconcile, name="reconcile"),
]
