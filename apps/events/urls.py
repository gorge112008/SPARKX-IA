from django.urls import path

from . import views
from .journey_views import journey_demo
from . import constraint_views
from .schedule_views import schedule_editor
from apps.planning.preparation_views import preparation
from apps.jobs.live_status import view as romeo_status
from apps.jobs import ui_actions

app_name = "events"

urlpatterns = [
    path("", views.index, name="index"),
    path("romeo/status/", romeo_status, name="romeo_status"),
    path("romeo/interpret/", ui_actions.interpret, name="romeo_interpret"),
    path("romeo/actions/", ui_actions.create, name="romeo_action_create"),
    path("romeo/actions/<uuid:action_id>/start/", ui_actions.start, name="romeo_action_start"),
    path("romeo/actions/<uuid:action_id>/finish/", ui_actions.finish, name="romeo_action_finish"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("events/new/", views.create, name="create"),
    path("events/<uuid:event_id>/", views.detail, name="detail"),
    path("events/<uuid:event_id>/demo/", journey_demo, name="journey_demo"),
    path("events/<uuid:event_id>/edit/", views.edit, name="edit"),
    path("events/<uuid:event_id>/schedule/", schedule_editor, name="schedule_editor"),
    path("events/<uuid:event_id>/constraints/", constraint_views.configure, name="constraints"),
    path("events/<uuid:event_id>/constraints/repair/", constraint_views.repair, name="repair"),
    path("events/<uuid:event_id>/preparation/", preparation, name="preparation"),
    path("events/<uuid:event_id>/interview/", views.interview, name="interview"),
    path("events/<uuid:event_id>/tasks/status/", views.task_progress, name="task_progress"),
    path("events/<uuid:event_id>/generate/", views.generate, name="generate"),
    path("events/<uuid:event_id>/chat/", views.chat, name="chat"),
    path("events/<uuid:event_id>/candidates/<uuid:candidate_id>/approve/", views.approve, name="approve"),
    path("events/<uuid:event_id>/candidates/<uuid:candidate_id>/reject/", views.reject, name="reject"),
    path("events/<uuid:event_id>/jobs/<uuid:job_id>/", views.job, name="job"),
    path("events/<uuid:event_id>/jobs/<uuid:job_id>/cancel/", views.cancel, name="cancel"),
]
