"""A display-name change cannot recreate the account or reset its ledger."""
from datetime import timedelta
from decimal import Decimal
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.assistant.models import Message
from apps.events.models import Event
from apps.jobs.models import Job
from .agent_access import agent_grant_summary
from .control_forms import AgentAccessForm, PoolEntryForm
from .models import AIAccount, AIProfile, AIUsage, AgentGrant, AgentPoolEntry, FreeGatewayState, OpenAIPilotLock


class AgentIdentityTests(TestCase):
    def profile(self, owner, name, *, provider="openai", model="gpt-5.4-mini", mode="paid"):
        return AIProfile.objects.create(owner=owner, name=name, provider=provider, model=model,
            mode=mode, version=13, max_input_tokens=12345, max_output_tokens=2048,
            input_rate=Decimal(".75") if mode=="paid" else 0,
            cached_rate=Decimal(".075") if mode=="paid" else 0,
            output_rate=Decimal("4.5") if mode=="paid" else 0)

    def test_new_default_is_public_gica_while_internal_code_and_form_authority_stay_stable(self):
        self.assertEqual(AgentGrant._meta.get_field("name").default, "Gica-1")
        self.assertEqual(AgentGrant._meta.get_field("code").default, "romeo-1")
        self.assertEqual(AgentAccessForm.base_fields["enabled"].label, "Gica-1 habilitado")
        self.assertEqual(PoolEntryForm.base_fields["enabled"].label, "Habilitar este modelo para Gica-1")

    def test_cosmetic_migration_preserves_finances_identity_authorization_and_history(self):
        owner=get_user_model().objects.create_user(username="gica-rename-admin",is_staff=True,is_superuser=True)
        primary=self.profile(owner,"Romeo-1 · GPT-5.4 mini")
        free=self.profile(owner,"Romeo-1 · grupo · opencode_demo",provider="opencode",model="glm-5.3-flash-free",mode="free")
        fallback=self.profile(owner,"Romeo-1 · alternativa · opencode_minimax",provider="opencode",model="minimax-m3.1-flash-free",mode="free")
        custom=self.profile(owner,"Romeo-1 de Jorge")
        wrong_model=self.profile(owner,"Romeo-1 · grupo · opencode_demo",provider="opencode",model="custom-model",mode="free")
        account=AIAccount.objects.create(owner=owner,active_profile=primary,paid_enabled=True,
            monthly_budget_usd=Decimal(".650000"),monthly_token_limit=73456,version=8)
        grant=AgentGrant.objects.create(account=account,code="romeo-1",name="Romeo-1",enabled=True,
            primary_profile=primary,fallback_profile=fallback,configured_by=owner,budget_usd=Decimal(".650000"),
            version=9,free_pool_enabled=True,free_pool_for_plans=True,
            fallback_policy_fingerprint="f"*64,fallback_policy_approved_by=owner,fallback_policy_approved_at=timezone.now())
        entry=AgentPoolEntry.objects.create(grant=grant,profile=free,roles="both",enabled=True,priority=17,version=5,
            policy_fingerprint="a"*64,approved_by=owner,approved_at=timezone.now(),daily_request_limit=7,daily_token_limit=55000)
        FreeGatewayState.objects.create(account=account,cooldown_until=timezone.now()+timedelta(minutes=8),last_error_code="HTTP429")
        event=Event.objects.create(owner=owner,title="Demo Romeo-1: historia",brief="Hablar con Julio Romeo",is_synthetic=True)
        job=Job.objects.create(event=event,actor=owner,kind="chat",base_revision=1,
            prompt="Hola Romeo: busca a Julio Romeo",request_hash="a"*64,idempotency_key="rename-history")
        AIUsage.objects.create(job=job,account=account,month=timezone.localdate().replace(day=1),
            snapshot={"agent_code":"romeo-1","agent_name":"Romeo-1","agent_budget_usd":"0.650000","profile_version":13,
                      "provider":"openai","model":"gpt-5.4-mini"},
            reserved_input_tokens=700,reserved_output_tokens=250,reserved_usd=Decimal(".123456"),status="reserved")
        Message.objects.create(event=event,role="user",content="Hola Romeo, busca a Julio Romeo")
        other=get_user_model().objects.create_user(username="gica-custom-code")
        other_profile=self.profile(other,"Perfil personalizado")
        other_account=AIAccount.objects.create(owner=other,active_profile=other_profile)
        custom_grant=AgentGrant.objects.create(account=other_account,code="personal-agent",name="Romeo-1",
            primary_profile=other_profile,configured_by=owner,budget_usd=Decimal(".100000"))
        tracked=(AIAccount,AIProfile,AgentGrant,AIUsage,AgentPoolEntry,FreeGatewayState,Job,Message,Event,OpenAIPilotLock)
        before={model.__name__:list(model.objects.order_by("pk").values()) for model in tracked}
        budget_before=agent_grant_summary(grant)
        migration=import_module("apps.ai_management.migrations.0006_gica_display_name")
        schema_editor=SimpleNamespace(connection=connection)
        with patch("apps.assistant.provider._opener.open",side_effect=AssertionError("No provider")), \
             patch("subprocess.Popen",side_effect=AssertionError("No commands")):
            migration.rename_generated_names(apps,schema_editor)
        expected={AIProfile.__name__:{primary.pk:"Gica-1 · GPT-5.4 mini",free.pk:"Gica-1 · grupo · opencode_demo",
                                      fallback.pk:"Gica-1 · alternativa · opencode_minimax"},
                  AgentGrant.__name__:{grant.pk:"Gica-1"}}
        for model in tracked:
            wanted=before[model.__name__]
            for row in wanted:
                if row["id"] in expected.get(model.__name__,{}):row["name"]=expected[model.__name__][row["id"]]
            self.assertEqual(list(model.objects.order_by("pk").values()),wanted,model.__name__)
        grant.refresh_from_db()
        self.assertEqual(agent_grant_summary(grant),budget_before)
        self.assertEqual(grant.code,"romeo-1")
        custom.refresh_from_db();wrong_model.refresh_from_db();custom_grant.refresh_from_db();entry.refresh_from_db()
        self.assertEqual(custom.name,"Romeo-1 de Jorge")
        self.assertEqual(wrong_model.name,"Romeo-1 · grupo · opencode_demo")
        self.assertEqual(custom_grant.name,"Romeo-1")
        self.assertEqual((entry.version,grant.version,account.version),(5,9,8))
        after={model.__name__:list(model.objects.order_by("pk").values()) for model in tracked}
        migration.rename_generated_names(apps,schema_editor)
        self.assertEqual({model.__name__:list(model.objects.order_by("pk").values()) for model in tracked},after)

    def test_legacy_bootstrap_command_reuses_profile_identity_without_network_or_duplicate(self):
        owner=get_user_model().objects.create_user(username="gica-bootstrap-admin",is_staff=True,is_superuser=True)
        primary=self.profile(owner,"Romeo-1 · GPT-5.4 mini")
        output=StringIO()
        with patch("apps.assistant.provider._opener.open",side_effect=AssertionError("No provider")), \
             patch("apps.assistant.free_harness.run_free_harness",side_effect=AssertionError("No provider")):
            call_command("prepare_romeo",username=owner.username,stdout=output)
        self.assertEqual(AIProfile.objects.filter(owner=owner).count(),1)
        account=AIAccount.objects.get(owner=owner)
        self.assertEqual(account.active_profile_id,primary.pk)
        self.assertEqual(account.agent_grant.name,"Gica-1")
        self.assertEqual(account.agent_grant.code,"romeo-1")
        primary.refresh_from_db();self.assertEqual(primary.name,"Gica-1 · GPT-5.4 mini")
        self.assertIn("Gica-1 preparado",output.getvalue())
        self.assertFalse(Job.objects.exists());self.assertFalse(AIUsage.objects.exists())
