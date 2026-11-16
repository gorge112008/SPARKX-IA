"""Private, revisioned drafts for the human-guided event creation interview."""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0005_knowledge_memory"),
        ("events", "0006_event_planning_constraints_event_planning_people"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventCreationDraft",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("status", models.CharField(max_length=12, default="collecting", choices=[("collecting", "Completando datos"), ("review", "Listo para revisar"), ("created", "Evento creado"), ("cancelled", "Cancelado")])),
                ("data", models.JSONField(default=dict)),
                ("step", models.CharField(max_length=32, default="title")),
                ("revision", models.PositiveIntegerField(default=1)),
                ("expires_at", models.DateTimeField()),
                ("last_request_id", models.UUIDField(null=True, blank=True)),
                ("last_request_hash", models.CharField(max_length=64, blank=True)),
                ("last_response", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_creation_drafts", to=settings.AUTH_USER_MODEL)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="creation_draft", to="events.event")),
            ],
            options={
                "indexes": [models.Index(fields=["owner", "updated_at"], name="creation_owner_updated")],
                "constraints": [
                    models.UniqueConstraint(fields=["owner"], condition=models.Q(status__in=["collecting", "review"]), name="creation_one_active_owner"),
                    models.CheckConstraint(condition=models.Q(status__in=["collecting", "review", "created", "cancelled"]), name="creation_known_status"),
                    models.CheckConstraint(condition=models.Q(revision__gte=1), name="creation_positive_revision"),
                    models.CheckConstraint(condition=~models.Q(status="created") | models.Q(event__isnull=False), name="creation_completed_has_event"),
                ],
            },
        ),
    ]
