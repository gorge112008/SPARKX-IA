from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0006_eventcreationdraft"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GicaProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("personality", models.CharField(choices=[("friendly", "Cercano y claro"), ("professional", "Profesional"), ("direct", "Directo")], default="friendly", max_length=16)),
                ("appearance", models.CharField(choices=[("ocean", "Azul océano"), ("slate", "Grafito"), ("forest", "Verde bosque")], default="ocean", max_length=12)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="gica_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=models.Q(("personality__in", ["friendly", "professional", "direct"])), name="gica_profile_known_personality"),
                models.CheckConstraint(condition=models.Q(("appearance__in", ["ocean", "slate", "forest"])), name="gica_profile_known_appearance"),
            ]},
        ),
    ]
