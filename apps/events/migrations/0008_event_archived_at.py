from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0007_event_scheduled_dates")]
    operations = [migrations.AddField(model_name="event", name="archived_at",
        field=models.DateTimeField(blank=True, editable=False, null=True))]
