from django.db import migrations, models


def seed_pilot_mutex(apps, schema_editor):
    apps.get_model("ai_management", "OpenAIPilotLock").objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("ai_management", "0002_remove_aiprofile_ai_profile_known_provider_and_more")]

    operations = [
        migrations.CreateModel(
            name="OpenAIPilotLock",
            fields=[("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False))],
            options={"constraints": [models.CheckConstraint(condition=models.Q(pk=1), name="openai_pilot_singleton")]},
        ),
        migrations.RunPython(seed_pilot_mutex, migrations.RunPython.noop),
    ]
