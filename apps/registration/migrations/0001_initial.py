import apps.registration.models
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("events", "0005_event_is_synthetic_event_organization"),
        ("planning", "0002_task_progress"),
    ]
    operations = [
        migrations.CreateModel(
            name="RegistrationPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_token", models.CharField(default=apps.registration.models.public_token, editable=False, max_length=43, unique=True)),
                ("state", models.CharField(choices=[("open", "Abiertas"), ("closed", "Cerradas")], default="closed", max_length=8)),
                ("version", models.PositiveIntegerField(default=1, editable=False)),
                ("opened_at", models.DateTimeField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="registration_page", to="events.event")),
                ("published_plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registration_publications", to="planning.planrevision")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registration_publications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=models.Q(("state__in", ["open", "closed"])), name="registration_page_known_state"),
                models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="registration_page_positive_version"),
            ]},
        ),
        migrations.CreateModel(
            name="Registration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("full_name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254)),
                ("status", models.CharField(choices=[("active", "Activa"), ("cancelled", "Cancelada")], default="active", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="registrations", to="events.event")),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [models.Index(fields=["event", "status"], name="registration_active_scope")],
                "constraints": [
                    models.UniqueConstraint(fields=("event", "email"), name="registration_unique_event_email"),
                    models.CheckConstraint(condition=models.Q(("status__in", ["active", "cancelled"])), name="registration_known_status"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RegistrationSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_key", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("page", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="registration.registrationpage")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("page", "request_key"), name="registration_submission_unique")]},
        ),
    ]
