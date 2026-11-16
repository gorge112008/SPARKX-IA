from django.urls import path

from . import views

app_name = "event_registration"

urlpatterns = [
    path("events/<uuid:event_id>/registration/", views.manage, name="manage"),
    path("events/<uuid:event_id>/registration/state/", views.change_state, name="change_state"),
    path("r/<str:token>/", views.public_registration, name="public"),
    path("r/<str:token>/received/", views.received, name="received"),
]
