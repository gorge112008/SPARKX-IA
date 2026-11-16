from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0003_uiaction")]

    operations = [
        migrations.RemoveConstraint(model_name="uiaction", name="ui_action_known_action"),
        migrations.AddField(
            model_name="uiaction", name="query",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AlterField(
            model_name="uiaction", name="action",
            field=models.CharField(choices=[
                ("theme_light", "Tema claro"), ("theme_dark", "Tema oscuro"),
                ("calendar_open", "Abrir calendario"), ("directory_open", "Abrir directorio"),
                ("people_search", "Buscar personas"), ("events_open", "Abrir eventos"),
            ], max_length=16),
        ),
        migrations.AddConstraint(
            model_name="uiaction", constraint=models.CheckConstraint(
                condition=models.Q(action__in=["theme_light", "theme_dark", "calendar_open", "directory_open", "people_search", "events_open"]),
                name="ui_action_known_action",
            ),
        ),
        migrations.AddConstraint(
            model_name="uiaction", constraint=models.CheckConstraint(
                condition=(models.Q(action="people_search") & ~models.Q(query=""))
                | (~models.Q(action="people_search") & models.Q(query="")),
                name="ui_action_query_scope",
            ),
        ),
    ]
