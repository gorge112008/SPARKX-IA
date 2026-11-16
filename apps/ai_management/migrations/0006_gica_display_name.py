"""Rename generated labels only; financial and authorization identity is stable."""
from django.db import migrations, models


# Frozen catalogue: no import of live services, tariffs, credentials or policies.
FREE_PROFILES = (
    ("opencode_demo", "glm-5.3-flash-free"),
    ("opencode_deepseek", "deepseek-v4.1-flash-free"),
    ("opencode_minimax", "minimax-m3.1-flash-free"),
    ("opencode_longcat", "longcat-2.5-free"),
    ("opencode_beam", "beam-free"),
    ("opencode_mimo", "mimo-v2.6-flash-free"),
    ("opencode_nemotron", "nemotron-3.5-lightning-free"),
    ("opencode_pickle", "big-pickle"),
    ("opencode_iceman", "iceman-free"),
    ("opencode_inkling", "inkling-2-small-free"),
    ("opencode_flint", "flint-40b-free"),
    ("opencode_nemotron_vl", "nemotron-3.5-super-vl-free"),
)


def rename_generated_names(apps, schema_editor):
    # QuerySet.update intentionally does not bump version/updated_at, invalidate
    # an in-flight snapshot or call an account/grant provisioning service.
    Grant = apps.get_model("ai_management", "AgentGrant")
    Profile = apps.get_model("ai_management", "AIProfile")
    alias = schema_editor.connection.alias
    Grant.objects.using(alias).filter(code="romeo-1", name="Romeo-1").update(name="Gica-1")
    Profile.objects.using(alias).filter(name="Romeo-1 · GPT-5.4 mini", provider="openai",
        model="gpt-5.4-mini", mode="paid").update(name="Gica-1 · GPT-5.4 mini")
    for preset, model in FREE_PROFILES:
        for role in ("grupo", "alternativa"):
            Profile.objects.using(alias).filter(name=f"Romeo-1 · {role} · {preset}", provider="opencode",
                model=model, mode="free").update(name=f"Gica-1 · {role} · {preset}")


class Migration(migrations.Migration):
    dependencies = [("ai_management", "0005_agentgrant_free_pool_enabled_and_more")]
    operations = [
        migrations.AlterField(model_name="agentgrant", name="name",
            field=models.CharField(default="Gica-1", max_length=80)),
        # Cosmetic rollback must not rename labels chosen after this migration.
        migrations.RunPython(rename_generated_names, migrations.RunPython.noop),
    ]
