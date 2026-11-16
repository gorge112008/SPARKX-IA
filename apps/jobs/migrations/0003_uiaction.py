import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0002_job_execution_trace"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UIAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("request_key", models.UUIDField(editable=False)),
                ("tab_id", models.UUIDField(editable=False)),
                ("session_digest", models.CharField(editable=False, max_length=64)),
                ("action", models.CharField(choices=[("theme_light", "Tema claro"), ("theme_dark", "Tema oscuro")], max_length=16)),
                ("state", models.CharField(choices=[("pending", "Pendiente"), ("executing", "En ejecución"), ("completed", "Completada por el cliente"), ("cancelled", "Cancelada"), ("failed", "Fallida"), ("expired", "Caducada")], default="pending", max_length=12)),
                ("expires_at", models.DateTimeField(editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="romeo_ui_actions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("actor", "request_key"), name="ui_action_request_once"),
                    models.UniqueConstraint(condition=models.Q(("state__in", ["pending", "executing"])), fields=("actor", "tab_id"), name="ui_action_one_active_tab"),
                    models.CheckConstraint(condition=models.Q(("action__in", ["theme_light", "theme_dark"])), name="ui_action_known_action"),
                    models.CheckConstraint(condition=models.Q(("state__in", ["pending", "executing", "completed", "cancelled", "failed", "expired"])), name="ui_action_known_state"),
                ],
            },
        ),
    ]
