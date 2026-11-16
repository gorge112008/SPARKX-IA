from django.urls import path

from . import views

app_name = "project_checklist"
urlpatterns = [
    path("", views.index, name="index"),
    path("check/", views.check, name="check"),
    path("<slug:item_key>/", views.update, name="update"),
]
