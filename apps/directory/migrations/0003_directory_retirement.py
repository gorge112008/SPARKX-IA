from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("directory", "0002_alternate_names")]
    operations = [
        migrations.AddField(model_name="organization", name="archived_at", field=models.DateTimeField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name="person", name="archived_at", field=models.DateTimeField(blank=True, editable=False, null=True)),
        migrations.RemoveConstraint(model_name="organization", name="directory_org_owner_name"),
        migrations.AddConstraint(model_name="organization", constraint=models.UniqueConstraint(fields=("owner", "name_key"), condition=models.Q(archived_at__isnull=True), name="directory_org_owner_name")),
        migrations.RemoveConstraint(model_name="person", name="directory_person_owner_email"),
        migrations.AddConstraint(model_name="person", constraint=models.UniqueConstraint(fields=("owner", "email_key"), condition=~models.Q(email_key="") & models.Q(archived_at__isnull=True), name="directory_person_owner_email")),
    ]
