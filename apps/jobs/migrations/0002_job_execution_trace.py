from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0001_initial")]
    operations = [migrations.AddField(
        model_name="job", name="execution_trace",
        field=models.JSONField(default=list, blank=True, editable=False),
    )]
