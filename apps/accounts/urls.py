from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("users/", views.users, name="users"),
    path("users/create/", views.create_user, name="create_user"),
    path("users/<int:user_id>/", views.update_user, name="update_user"),
    path("events/<uuid:event_id>/reviewers/", views.event_reviewers, name="event_reviewers"),
]
