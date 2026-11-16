from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0006_event_planning_constraints_event_planning_people")]
    operations = [migrations.AddField(model_name="event", name="scheduled_dates", field=models.JSONField(blank=True, default=list))]
