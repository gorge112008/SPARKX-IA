from django.urls import path

from . import views
from .tool_views import tool_query

app_name = "directory"

urlpatterns = [
    path("", views.index, name="index"),
    path("tools/", tool_query, name="tools"),
    path("people/new/", views.person_create, name="person_create"),
    path("people/<uuid:person_id>/edit/", views.person_edit, name="person_edit"),
    path("organizations/new/", views.organization_create, name="organization_create"),
    path("organizations/<uuid:organization_id>/edit/", views.organization_edit, name="organization_edit"),
    path("events/<uuid:event_id>/", views.roster, name="roster"),
]
