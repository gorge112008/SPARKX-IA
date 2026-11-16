"""Synthetic routing and quota tests: no provider or live database access."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from tools.opencode.catalog import policy_fingerprint

from apps.assistant.execution import agent_execution
from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.services import enqueue, run_one
from apps.ai_management.agent_access import agent_preview_snapshot, update_agent_grant, validate_agent_snapshot
from apps.ai_management.catalog import CATALOG
from apps.ai_management.free_pool import (choose_pool_snapshot, configure_entry, ensure_pool_capacity,
                        pool_summary, record_quota_failure)
from apps.ai_management.models import AIAccount, AIProfile, AIUsage, AgentGrant, AgentPoolEntry, FreeGatewayState
from apps.ai_management.services import authorize_snapshot, current_month, mark_dispatched


class FreePoolTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="pool-human", is_superuser=True)
        self.owner = get_user_model().objects.create_user(username="pool-organizer")
        self.primary = AIProfile.objects.create(owner=self.owner, name="Synthetic reviewed primary",
            provider="openai", model="gpt-5.4-mini", mode="paid", input_rate=Decimal(".75"),
            cached_rate=Decimal(".075"), output_rate=Decimal("4.5"))
        self.account = AIAccount.objects.create(owner=self.owner, active_profile=self.primary,
            paid_enabled=True, monthly_budget_usd=Decimal("1"), monthly_token_limit=1000000)
        self.event = Event.objects.create(owner=self.owner, title="Synthetic pool event", is_synthetic=True)
        self.grant = update_agent_grant(actor=self.admin, account=self.account, expected_version=0,
            name="Romeo-1", enabled=True, budget_usd=1, primary_profile=self.primary, free_pool_enabled=True)
        ready = patch("apps.assistant.provider.profile_ready", return_value=True)
        self.addCleanup(ready.stop)
        ready.start()
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No remote calls"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(self.remote.assert_not_called)

    def entry(self, preset="opencode_demo", **changes):
        self.grant.refresh_from_db()
        return configure_entry(**{"actor": self.admin, "account": self.account,
            "expected_grant_version": self.grant.version, "preset": preset, "enabled": True,
            "roles": "chat", "priority": 10, "daily_request_limit": 5, "daily_token_limit": 60000,
            "expected_policy_fingerprint": policy_fingerprint(CATALOG[preset]["model"]),
            "accept_policy": True, **changes})

    def queue(self, kind="chat", key=None):
        return enqueue(event=self.event, actor=self.owner, kind=kind, prompt="Synthetic event question",
            idempotency_key=key or str(uuid.uuid4()))

    def test_pool_disabled_by_default_and_no_silent_migration_authorization(self):
        self.assertFalse(AgentGrant._meta.get_field("free_pool_enabled").default)
        self.assertFalse(AgentGrant._meta.get_field("free_pool_for_plans").default)
        self.assertFalse(AgentPoolEntry.objects.exists())

    def test_all_twelve_reviewed_models_can_be_authorized_individually_without_calls(self):
        presets = [code for code, spec in CATALOG.items() if spec["provider"] == "opencode"]
        for preset in presets:
            self.entry(preset)
        self.assertEqual(len(presets), 12)
        self.assertEqual(AgentPoolEntry.objects.filter(enabled=True).count(), 12)
        summary = pool_summary(AgentGrant.objects.get(pk=self.grant.pk))
        self.assertEqual(len(summary["entries"]), 12)
        self.assertTrue(all(row["eligible"] for row in summary["entries"]))

    def test_exact_privacy_approval_required_and_agent_cannot_configure(self):
        with self.assertRaises(ValidationError):
            self.entry(accept_policy=False)
        self.assertFalse(AgentPoolEntry.objects.exists())
        with agent_execution(), self.assertRaises(PermissionDenied):
            self.entry()
        with self.assertRaises(PermissionDenied):
            self.entry(actor=self.owner)

    def test_cas_prevents_old_browser_overwriting_policy_or_limits(self):
        self.entry()
        with self.assertRaises(ValidationError):
            self.entry(expected_grant_version=1, roles="both")

    def test_changed_policy_between_display_and_submit_is_not_accepted(self):
        with self.assertRaises(ValidationError):
            self.entry(expected_policy_fingerprint="outdated")
        self.assertEqual(AgentPoolEntry.objects.count(), 0)

    def test_free_chat_from_start_paid_plan_and_no_duplicate_request(self):
        self.entry()
        job = self.queue()
        self.assertEqual(job.ai_usage.snapshot["agent_route"], "free_pool")
        self.assertEqual(job.ai_usage.reserved_usd, 0)
        repeated = self.queue(key=job.idempotency_key)
        self.assertEqual(job.pk, repeated.pk)
        plan = self.queue(kind="plan")
        self.assertEqual(plan.ai_usage.snapshot["provider"], "openai")
        self.assertEqual(AIUsage.objects.count(), 2)

    def test_priority_exhaustion_rotates_before_dispatch_and_released_hold_is_reusable(self):
        first = self.entry(priority=1, daily_request_limit=1)
        second = self.entry("opencode_deepseek", priority=2)
        initial = self.queue()
        next_job = self.queue()
        self.assertEqual(initial.ai_usage.snapshot["profile_id"], first.profile_id)
        self.assertEqual(next_job.ai_usage.snapshot["profile_id"], second.profile_id)
        AIUsage.objects.filter(job=initial).update(status="released")
        selected = choose_pool_snapshot(account=self.account, grant=AgentGrant.objects.get(pk=self.grant.pk), kind="chat")
        self.assertEqual(selected["profile_id"], first.profile_id)

    def test_equal_priority_distributes_independent_jobs(self):
        self.entry()
        self.entry("opencode_deepseek")
        self.assertNotEqual(self.queue().ai_usage.snapshot["model"], self.queue().ai_usage.snapshot["model"])

    def test_empty_or_exhausted_pool_never_uses_paid_automatically(self):
        with self.assertRaises(ValidationError):
            self.queue()
        self.entry(daily_request_limit=1)
        self.queue()
        with self.assertRaises(ValidationError):
            self.queue()
        self.assertEqual(AIUsage.objects.count(), 1)
        self.assertEqual(AIUsage.objects.get().reserved_usd, 0)

    def test_token_capacity_exhaustion_skips_model_and_monthly_cap_still_blocks(self):
        self.entry(daily_token_limit=2049)
        second = self.entry("opencode_deepseek")
        self.assertEqual(self.queue().ai_usage.snapshot["profile_id"], second.profile_id)
        self.account.monthly_token_limit = 1
        self.account.save()
        with self.assertRaises(ValidationError):
            self.queue()

    def test_opt_in_free_plans_and_roles_are_enforced(self):
        self.entry(roles="both")
        self.grant.refresh_from_db()
        update_agent_grant(actor=self.admin, account=self.account, expected_version=self.grant.version,
            name="Romeo-1", enabled=True, budget_usd=1, primary_profile=self.primary, free_pool_for_plans=True)
        job = self.queue(kind="plan")
        self.assertEqual(job.ai_usage.snapshot["agent_route"], "free_pool")
        self.assertEqual(job.ai_usage.snapshot["agent_task_role"], "plan")

    def test_policy_change_or_revoked_approver_blocks_queued_model(self):
        entry = self.entry()
        job = self.queue()
        AgentPoolEntry.objects.filter(pk=entry.pk).update(policy_fingerprint="invalid")
        with self.assertRaises(ValidationError):
            validate_agent_snapshot(self.account, job.ai_usage.snapshot)
        self.entry()
        get_user_model().objects.filter(pk=self.admin.pk).update(is_superuser=False)
        with self.assertRaises(ValidationError):
            self.queue()

    def test_dispatch_rechecks_quota_and_snapshot(self):
        entry = self.entry(daily_request_limit=1)
        job = self.queue()
        usage = job.ai_usage
        # The existing reservation is counted once, not twice.
        self.assertTrue(mark_dispatched(usage, uuid.uuid4()))
        snapshot = dict(usage.snapshot, max_input_tokens=1)
        with self.assertRaises(ValidationError):
            validate_agent_snapshot(self.account, snapshot)
        AgentPoolEntry.objects.filter(pk=entry.pk).update(enabled=False)
        with self.assertRaises(ValidationError):
            ensure_pool_capacity(account=self.account, grant=AgentGrant.objects.get(pk=self.grant.pk), snapshot=usage.snapshot, usage=usage)

    def test_internal_daily_capacity_reopens_but_old_uncertainty_keeps_tokens(self):
        entry = self.entry(daily_request_limit=1, daily_token_limit=30000)
        job = self.queue()
        old = timezone.now() - timedelta(days=2)
        AIUsage.objects.filter(job=job).update(created_at=old, dispatched_at=old, status="uncertain", dispatch_token=uuid.uuid4())
        summary = pool_summary(AgentGrant.objects.get(pk=self.grant.pk))["entries"][0]
        self.assertEqual(summary["requests_used"], 0)
        self.assertEqual(summary["tokens_committed"], 26048)
        with self.assertRaises(ValidationError):
            self.queue()
        AIUsage.objects.filter(job=job).update(status="settled", total_tokens=100, estimated_cost_usd=0)
        self.assertEqual(self.queue().ai_usage.snapshot["profile_id"], entry.profile_id)

    def test_unknown_429_pauses_shared_gateway_without_releasing_or_retrying(self):
        from apps.assistant.provider import FreeQuotaUnavailable
        self.entry()
        self.entry("opencode_deepseek")
        job = self.queue()
        with patch("apps.assistant.provider.answer_question", side_effect=FreeQuotaUnavailable) as call:
            result = run_one(job_id=job.pk)
        self.assertEqual(result.status, "failed")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(AIUsage.objects.get(job=job).status, "uncertain")
        self.assertTrue(FreeGatewayState.objects.get(account=self.account).cooldown_until > timezone.now())
        with self.assertRaises(ValidationError):
            self.queue()
        self.assertEqual(Job.objects.count(), 1)

    def test_cooldown_expiry_allows_new_selection_without_background_probe(self):
        self.entry()
        record_quota_failure(account_id=self.account.pk, snapshot={"provider": "opencode"})
        with self.assertRaises(ValidationError):
            agent_preview_snapshot(self.account, kind="chat")
        FreeGatewayState.objects.filter(account=self.account).update(cooldown_until=timezone.now() - timedelta(seconds=1))
        preview = agent_preview_snapshot(self.account, kind="chat")
        self.assertEqual(preview["agent_route"], "free_pool")
        self.assertEqual(Job.objects.count(), 0)

    def test_shared_cooldown_cannot_be_bypassed_by_primary_fallback_or_legacy_routes(self):
        entry = self.entry()
        job = self.queue()
        record_quota_failure(account_id=self.account.pk, snapshot=job.ai_usage.snapshot)
        # All dispatch paths, including a grant-less legacy usage, must consult
        # the same account gateway state. Existing calls still settle normally.
        with self.assertRaises(ValidationError):
            mark_dispatched(job.ai_usage, uuid.uuid4())
        for route in ("primary", "fallback_budget", "free_pool", None):
            with self.subTest(route=route), self.assertRaises(ValidationError) as error:
                authorize_snapshot(self.account, {"provider": "opencode", "agent_route": route})
            self.assertEqual(error.exception.code, "free_gateway_cooldown")

    def test_only_synthetic_owned_events_allowed(self):
        self.entry()
        self.event.is_synthetic = False
        self.event.save()
        with self.assertRaises(ValidationError):
            self.queue()
        self.assertEqual(AIUsage.objects.count(), 0)
