import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="CommandPattern",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("phrase", models.CharField(max_length=300)),
                ("normalized_phrase", models.CharField(editable=False, max_length=300)),
                (
                    "intent",
                    models.CharField(
                        choices=[
                            ("theme_light", "Modo claro"),
                            ("theme_dark", "Modo oscuro"),
                            ("calendar_open", "Abrir calendario"),
                            ("directory_open", "Abrir directorio"),
                            ("people_search", "Buscar una persona"),
                            ("events_open", "Abrir eventos"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reviewed_at", models.DateTimeField()),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="command_patterns",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-reviewed_at", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("owner", "normalized_phrase"), name="command_pattern_owner_phrase"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(intent__in=[
                            "theme_light", "theme_dark", "calendar_open", "directory_open",
                            "people_search", "events_open",
                        ]),
                        name="command_pattern_six_intents",
                    ),
                ],
            },
        ),
    ]
