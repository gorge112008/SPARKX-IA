from django.urls import path

from . import views
from . import knowledge_views
from . import event_creation_views
from . import profile_views
from . import demo_pilot
from . import pilot_workflow
from . import compact_views

app_name = "assistant"
urlpatterns = [
    path("profile/", profile_views.profile, name="profile"),
    path("event-creation/", event_creation_views.turn, name="event_creation"),
    path("demo-pilot/", demo_pilot.demo_pilot, name="demo_pilot"),
    path("pilot-control/", pilot_workflow.pilot_control, name="pilot_control"),
    path("pilot-ai/", compact_views.pilot_ai, name="pilot_ai"),
    path("knowledge/", knowledge_views.knowledge, name="knowledge"),
    path("knowledge/query/", knowledge_views.query, name="knowledge_query"),
    path("knowledge/<uuid:pk>/change/", knowledge_views.knowledge_change, name="knowledge_change"),
    path("knowledge/aliases/<uuid:pk>/change/", knowledge_views.alias_change, name="alias_change"),
    path("knowledge/history/clear/", knowledge_views.clear_lookup_history, name="lookup_history_clear"),
    path("guide/", views.guide, name="guide"),
    path("patterns/", views.patterns, name="patterns"),
    path("patterns/save/", views.pattern_save, name="pattern_save"),
    path("patterns/<int:pk>/delete/", views.pattern_delete, name="pattern_delete"),
    path("interactions/", views.interaction_log, name="interaction_log"),
    path("memory/", views.memory, name="memory"),
    path("memory/<uuid:pk>/review/", views.interaction_review, name="interaction_review"),
    path("memory/<uuid:pk>/delete/", views.interaction_delete, name="interaction_delete"),
    path("memory/clear/", views.interaction_clear, name="interaction_clear"),
]
