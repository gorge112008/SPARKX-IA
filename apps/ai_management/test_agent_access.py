"""Synthetic, no-network grant/routing tests; no real credentials or spending."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from apps.assistant.execution import (agent_execution, deny_agent_admin, in_agent_execution,
                                      require_human_superadmin)
from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.services import enqueue, run_one
from .agent_access import (agent_grant_summary, agent_preview_snapshot, chosen_snapshot,
                           update_agent_grant, validate_agent_snapshot)
from .model_policy import validate_job_consent
from .models import AIAccount, AIProfile, AIUsage, AgentGrant, OpenAIPilotLock
from .services import (authorize_snapshot, current_month, mark_dispatched, profile_snapshot,
                        reconcile_usage, reserve_job_locked)
from tools.opencode.catalog import policy_fingerprint


class AgentGrantTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="human-superadmin", is_staff=True, is_superuser=True)
        self.owner = get_user_model().objects.create_user(username="synthetic-organizer")
        self.staff = get_user_model().objects.create_user(username="ordinary-staff", is_staff=True)
        self.other = get_user_model().objects.create_user(username="other-owner")
        self.primary = AIProfile.objects.create(owner=self.owner, name="Reviewed text fixture", provider="openai",
            model="gpt-5.4-mini", mode="paid", input_rate=Decimal("0.75"), cached_rate=Decimal("0.075"),
            output_rate=Decimal("4.50"), max_input_tokens=24000, max_output_tokens=2500)
        self.fallback = AIProfile.objects.create(owner=self.owner, name="Reviewed free fixture", provider="opencode",
            model="glm-5.3-flash-free", mode="free", free_tier_confirmed=True,
            max_input_tokens=24000, max_output_tokens=2048)
        self.foreign = AIProfile.objects.create(owner=self.other, name="Foreign free fixture", provider="opencode",
            model="glm-5.3-flash-free", mode="free", free_tier_confirmed=True,
            max_input_tokens=24000, max_output_tokens=2048)
        self.account = AIAccount.objects.create(owner=self.owner, active_profile=self.primary, paid_enabled=True,
            monthly_budget_usd=Decimal("10"), monthly_token_limit=10000000)
        self.event = Event.objects.create(owner=self.owner, title="Synthetic thesis event",
            brief="Fictional speakers and participants only.", is_synthetic=True)
        OpenAIPilotLock.objects.get_or_create(pk=1)
        self.ready = patch("apps.assistant.provider.profile_ready", return_value=True)
        self.ready.start(); self.addCleanup(self.ready.stop)

    def grant(self, **changes):
        return update_agent_grant(**{"actor": self.admin, "account": self.account,
            "expected_version": 0, "name": "Romeo-1", "enabled": True,
            "budget_usd": Decimal("1"), "primary_profile": self.primary,
            "expected_fallback_policy_fingerprint": policy_fingerprint(self.fallback.model),
            "fallback_profile": self.fallback, "accept_fallback_policy": True, **changes})

    def choose(self, **changes):
        return chosen_snapshot(**{"account": self.account, "event": self.event, "actor": self.owner,
            "kind": "chat", "key": "synthetic-" + str(uuid.uuid4()), "token": None, **changes})

    def reserve(self):
        key = str(uuid.uuid4())
        with transaction.atomic():
            snapshot = self.choose(key=key)
            job = Job.objects.create(event=self.event, actor=self.owner, kind="chat", prompt="Synthetic test only",
                base_revision=self.event.revision, idempotency_key=key, request_hash="0" * 64)
            return reserve_job_locked(job=job, account=self.account, snapshot=snapshot)

    def history(self, *, account=None, event=None, owner=None, reserve="0.98", cost="0.98", status="settled", month=None):
        job = Job.objects.create(event=event or self.event, actor=owner or self.owner, kind="chat",
            prompt="Explicit synthetic accounting fixture", base_revision=1,
            idempotency_key=str(uuid.uuid4()), request_hash="0" * 64, status="failed")
        return AIUsage.objects.create(job=job, account=account or self.account, month=month or current_month(),
            snapshot={"provider": "openai", "model": "gpt-5.4-mini"}, reserved_input_tokens=24000,
            reserved_output_tokens=2500, reserved_usd=Decimal(reserve), estimated_cost_usd=None if cost is None else Decimal(cost),
            status=status, dispatch_token=uuid.uuid4())

    def test_human_superadmin_creates_single_disabled_by_default_assignment_model(self):
        grant = self.grant(enabled=False)
        self.assertEqual(grant.account.agent_grant.pk, grant.pk)
        self.assertEqual(grant.code, "romeo-1")
        self.assertEqual(grant.configured_by_id, self.admin.pk)
        self.assertEqual(grant.fallback_policy_approved_by_id, self.admin.pk)
        self.assertEqual(grant.version, 1)
        self.assertFalse(grant.enabled)

    def test_regular_staff_and_owner_cannot_configure_or_approve_fallback(self):
        for actor in (self.owner, self.staff):
            with self.subTest(actor=actor.pk), self.assertRaises(PermissionDenied):
                self.grant(actor=actor)
        self.assertFalse(AgentGrant.objects.exists())

    def test_stale_superadmin_object_cannot_restore_revoked_privilege(self):
        get_user_model().objects.filter(pk=self.admin.pk).update(is_superuser=False)
        self.assertTrue(self.admin.is_superuser)
        with self.assertRaises(PermissionDenied): self.grant()

    def test_stale_superadmin_object_cannot_restore_deactivated_user(self):
        get_user_model().objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied): self.grant()

    def test_agent_context_blocks_admin_even_with_real_superadmin_and_restores(self):
        self.assertFalse(in_agent_execution())
        with agent_execution():
            with self.assertRaises(PermissionDenied): self.grant()
            with agent_execution("nested-agent"):
                with self.assertRaises(PermissionDenied): require_human_superadmin(self.admin)
            self.assertTrue(in_agent_execution())
        self.assertFalse(in_agent_execution())
        self.assertEqual(require_human_superadmin(self.admin).pk, self.admin.pk)

    def test_concurrent_execution_context_does_not_leak_to_human_thread(self):
        barrier = Barrier(2)
        def simulated_agent():
            with agent_execution():
                barrier.wait(timeout=5)
                try: deny_agent_admin()
                except PermissionDenied: return "denied"
                return "unexpected"
        def simulated_human():
            barrier.wait(timeout=5)
            deny_agent_admin()
            return in_agent_execution()
        with ThreadPoolExecutor(max_workers=2) as pool:
            agent = pool.submit(simulated_agent); human = pool.submit(simulated_human)
            self.assertEqual(agent.result(timeout=10), "denied")
            self.assertFalse(human.result(timeout=10))

    def test_budget_cannot_exceed_server_pilot_or_be_nonfinite_negative(self):
        for budget in ("1.000001", "-0.01", "NaN", "Infinity", "0.0000001"):
            with self.subTest(budget=budget), self.assertRaises(ValidationError) as caught:
                self.grant(budget_usd=budget)
            self.assertEqual(caught.exception.code, "agent_budget_invalid")
        self.assertFalse(AgentGrant.objects.exists())

    def test_foreign_primary_and_fallback_profiles_are_rejected(self):
        for field in ("primary_profile", "fallback_profile"):
            with self.subTest(field=field), self.assertRaises(ValidationError): self.grant(**{field: self.foreign})

    def test_only_reviewed_confirmed_opencode_may_be_fallback(self):
        for changes in ({"provider": "groq", "model": "openai/gpt-oss-20b"},
                        {"model": "unreviewed-free"}, {"free_tier_confirmed": False}):
            with self.subTest(changes=changes), transaction.atomic():
                AIProfile.objects.filter(pk=self.fallback.pk).update(**changes)
                with self.assertRaises(ValidationError): self.grant()
                transaction.set_rollback(True)

    def test_primary_cannot_expand_paid_authorization_beyond_openai(self):
        for provider, model in (("groq", "openai/gpt-oss-20b"), ("gemini", "gemini-3.5-flash-lite")):
            with self.subTest(provider=provider), transaction.atomic():
                AIProfile.objects.filter(pk=self.primary.pk).update(provider=provider, model=model,
                    input_rate=0, cached_rate=0, output_rate=0)
                with self.assertRaises(ValidationError) as caught: self.grant()
                self.assertEqual(caught.exception.code, "agent_primary_invalid")
                transaction.set_rollback(True)

    def test_primary_free_local_must_use_reviewed_catalog_model(self):
        AIProfile.objects.filter(pk=self.primary.pk).update(provider="groq", model="unreviewed-free-model",
            mode="free", free_tier_confirmed=True, input_rate=0, cached_rate=0, output_rate=0)
        with self.assertRaises(ValidationError) as caught: self.grant()
        self.assertEqual(caught.exception.code, "agent_primary_invalid")

    def test_reviewed_free_primary_needs_no_paid_permission_or_fallback(self):
        self.account.paid_enabled = False; self.account.monthly_budget_usd = Decimal("0"); self.account.save()
        grant = self.grant(primary_profile=self.fallback, fallback_profile=None, budget_usd="0")
        usage = self.reserve()
        self.assertEqual(usage.snapshot["agent_grant_id"], grant.pk)
        self.assertEqual(usage.snapshot["agent_route"], "primary")
        self.assertEqual(usage.reserved_usd, Decimal("0"))

    def test_fallback_requires_explicit_superadmin_policy_acceptance(self):
        with self.assertRaises(ValidationError) as caught: self.grant(accept_fallback_policy=False)
        self.assertEqual(caught.exception.code, "agent_fallback_policy")
        self.assertFalse(AgentGrant.objects.exists())

    def test_update_uses_expected_version_and_preserves_unchanged_policy_approval(self):
        first = self.grant()
        changed = self.grant(expected_version=first.version, name="Romeo for synthetic events", accept_fallback_policy=False)
        self.assertEqual(changed.version, 2)
        self.assertEqual(changed.fallback_policy_approved_at, first.fallback_policy_approved_at)
        with self.assertRaises(ValidationError) as caught: self.grant(expected_version=first.version)
        self.assertEqual(caught.exception.code, "agent_grant_stale")

    def test_without_grant_legacy_profile_snapshot_path_is_unchanged(self):
        snapshot = self.choose()
        self.assertEqual(snapshot["model"], "gpt-5.4-mini")
        self.assertNotIn("agent_grant_id", snapshot)

    def test_primary_reservation_binds_grant_and_does_not_use_active_other_profile(self):
        grant = self.grant()
        self.account.active_profile = self.fallback; self.account.save()
        usage = self.reserve()
        self.assertEqual(usage.snapshot["agent_grant_id"], grant.pk)
        self.assertEqual(usage.snapshot["agent_route"], "primary")
        self.assertEqual(usage.snapshot["model"], "gpt-5.4-mini")
        self.assertEqual(usage.reserved_usd, Decimal("0.029250"))
        self.assertEqual(usage.snapshot["credential_owner_id"], self.owner.pk)
        self.assertEqual(agent_grant_summary(grant)["reserved_usd"], Decimal("0.029250"))

    def test_agent_budget_shortfall_selects_one_zero_cost_model_before_reservation(self):
        self.grant(budget_usd="0.01")
        usage = self.reserve()
        self.assertEqual(usage.snapshot["agent_route"], "fallback_budget")
        self.assertEqual(usage.snapshot["agent_budget_reason"], "agent_budget")
        self.assertEqual(usage.snapshot["model"], "glm-5.3-flash-free")
        self.assertEqual(usage.reserved_usd, Decimal("0"))
        self.assertEqual(AIUsage.objects.count(), 1)

    def test_monthly_budget_shortfall_selects_free_model(self):
        self.grant()
        self.account.monthly_budget_usd = Decimal("0.01"); self.account.save()
        usage = self.reserve()
        self.assertEqual(usage.snapshot["agent_budget_reason"], "monthly_budget")
        self.assertEqual(usage.reserved_usd, Decimal("0"))

    def test_zero_monthly_budget_allows_only_authorized_free_budget_fallback(self):
        self.grant()
        self.account.monthly_budget_usd = Decimal("0"); self.account.save()
        usage = self.reserve()
        self.assertEqual(usage.snapshot["agent_route"], "fallback_budget")
        self.assertEqual(usage.reserved_usd, Decimal("0"))

    def test_global_other_account_budget_shortfall_selects_free_without_resetting_cap(self):
        self.grant()
        other_account = AIAccount.objects.create(owner=self.other)
        other_event = Event.objects.create(owner=self.other, title="Other synthetic owner", brief="Fictional", is_synthetic=True)
        self.history(account=other_account, event=other_event, owner=self.other, reserve="0.99", cost="0.99")
        usage = self.reserve()
        self.assertEqual(usage.snapshot["agent_budget_reason"], "openai_pilot_budget")
        self.assertEqual(usage.reserved_usd, Decimal("0"))

    def test_lifetime_includes_legacy_older_month_and_unknown_holds(self):
        self.history(reserve="0.2", cost="0.1", month=date(2025, 1, 1))
        self.history(status="uncertain", reserve="0.89", cost=None, month=date(2025, 2, 1))
        grant = self.grant()
        summary = agent_grant_summary(grant)
        self.assertEqual(summary["spent_usd"], Decimal("0.1"))
        self.assertEqual(summary["reserved_usd"], Decimal("0.89"))
        self.assertEqual(summary["uncertain_count"], 1)
        self.assertEqual(self.reserve().snapshot["agent_budget_reason"], "agent_budget")

    def test_policy_sensitive_fallback_gets_exact_bound_receipt_not_general_consent(self):
        self.fallback.model = "big-pickle"; self.fallback.version += 1; self.fallback.save()
        grant = self.grant(budget_usd="0")
        usage = self.reserve()
        validate_job_consent(usage.snapshot, event=self.event, actor=self.owner,
            kind="chat", request_key=usage.job.idempotency_key)
        self.assertEqual(usage.snapshot["model_policy_consent"]["fingerprint"], grant.fallback_policy_fingerprint)
        with self.assertRaises(ValidationError):
            validate_job_consent(usage.snapshot, event=self.event, actor=self.other,
                kind="chat", request_key=usage.job.idempotency_key)

    def test_changed_fallback_privacy_requires_new_admin_acceptance(self):
        self.grant(budget_usd="0")
        with patch("apps.ai_management.agent_access.policy_fingerprint", return_value="f" * 64):
            with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "agent_fallback_policy")
        self.assertFalse(AIUsage.objects.exists())

    def test_non_synthetic_or_other_owner_event_cannot_use_grant(self):
        self.grant(budget_usd="0")
        self.event.is_synthetic = False
        with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "synthetic_required")
        self.event.is_synthetic = True
        with self.assertRaises(PermissionDenied): self.choose(actor=self.other)

    def test_missing_budget_fallback_rejects_without_reservation(self):
        self.grant(budget_usd="0", fallback_profile=None)
        with self.assertRaises(ValidationError) as caught: self.reserve()
        self.assertEqual(caught.exception.code, "agent_budget")
        self.assertFalse(AIUsage.objects.exists())

    def test_disabled_paid_permission_is_not_a_fallback_trigger(self):
        self.grant(budget_usd="0")
        self.account.paid_enabled = False; self.account.save()
        with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "paid_disabled")

    def test_token_limit_shortfall_is_not_a_fallback_trigger(self):
        self.grant(budget_usd="0")
        self.account.monthly_token_limit = 100; self.account.save()
        with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "monthly_tokens")

    def test_provider_unavailable_does_not_try_free_model(self):
        self.grant()
        with patch("apps.assistant.provider.profile_ready", return_value=False) as ready:
            with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "ai_not_configured")
        self.assertEqual(ready.call_count, 1)
        self.assertEqual(ready.call_args.args[0]["model"], "gpt-5.4-mini")

    def test_observed_usage_breach_never_selects_another_model(self):
        self.grant(budget_usd="0")
        self.history(reserve="0.01", cost="0.02")
        with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "usage_limit_breach")

    def test_global_other_account_usage_breach_never_selects_free_model(self):
        self.grant(budget_usd="0")
        other_account = AIAccount.objects.create(owner=self.other)
        other_event = Event.objects.create(owner=self.other, title="Other synthetic owner", brief="Fictional", is_synthetic=True)
        self.history(account=other_account, event=other_event, owner=self.other, reserve="0.01", cost="0.02")
        with self.assertRaises(ValidationError) as caught: self.choose()
        self.assertEqual(caught.exception.code, "openai_pilot_usage_breach")

    def test_grant_update_or_revocation_stops_queued_primary_before_dispatch(self):
        grant = self.grant()
        usage = self.reserve()
        self.grant(expected_version=grant.version, enabled=False)
        with self.assertRaises(ValidationError) as caught: mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "agent_disabled")
        usage.refresh_from_db()
        self.assertIsNone(usage.dispatch_token)

    def test_grant_can_be_disabled_after_fallback_profile_or_policy_is_revoked(self):
        grant = self.grant()
        AIProfile.objects.filter(pk=self.fallback.pk).update(enabled=False)
        with patch("apps.ai_management.agent_access.policy_fingerprint", return_value="f" * 64):
            disabled = self.grant(expected_version=grant.version, enabled=False, accept_fallback_policy=False)
        self.assertFalse(disabled.enabled)

    def test_reservation_rechecks_real_event_even_when_chooser_received_stale_object(self):
        self.grant(budget_usd="0")
        snapshot = self.choose()
        Event.objects.filter(pk=self.event.pk).update(is_synthetic=False)
        job = Job.objects.create(event=self.event, actor=self.owner, kind="chat", prompt="Synthetic unit test",
            base_revision=1, idempotency_key=str(uuid.uuid4()), request_hash="0" * 64)
        with self.assertRaises(ValidationError) as caught:
            reserve_job_locked(job=job, account=self.account, snapshot=snapshot)
        self.assertEqual(caught.exception.code, "synthetic_required")
        self.assertFalse(AIUsage.objects.exists())

    def test_version_change_stops_queued_fallback_without_rerouting(self):
        grant = self.grant(budget_usd="0")
        usage = self.reserve()
        self.grant(expected_version=grant.version, name="Changed grant", budget_usd="1")
        with self.assertRaises(ValidationError) as caught: mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "agent_grant_invalid")
        usage.refresh_from_db(); self.assertIsNone(usage.dispatch_token)

    def test_dispatch_rechecks_event_synthetic_declaration_for_free_route(self):
        self.grant(budget_usd="0")
        usage = self.reserve()
        Event.objects.filter(pk=self.event.pk).update(is_synthetic=False)
        with self.assertRaises(ValidationError) as caught: mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "synthetic_required")

    def test_new_grant_revokes_unbound_legacy_queued_snapshot(self):
        legacy = profile_snapshot(self.primary)
        self.grant()
        with self.assertRaises(ValidationError): authorize_snapshot(self.account, legacy)

    def test_grant_snapshot_cannot_be_replayed_to_other_account(self):
        self.grant()
        snapshot = self.choose()
        foreign_account = AIAccount.objects.create(owner=self.other)
        with self.assertRaises(ValidationError): validate_agent_snapshot(foreign_account, snapshot)

    def test_preview_returns_budget_eligible_model_and_does_not_reserve_or_call(self):
        self.grant(budget_usd="0")
        before = (Job.objects.count(), AIUsage.objects.count())
        with patch("apps.assistant.provider.profile_ready") as ready:
            preview = agent_preview_snapshot(self.account)
        ready.assert_not_called()
        self.assertEqual(preview["agent_route"], "fallback_budget")
        self.assertEqual(before, (Job.objects.count(), AIUsage.objects.count()))

    def test_staff_cannot_reconcile_and_agent_cannot_reconcile_even_as_superadmin(self):
        self.history(status="uncertain", cost=None)
        usage = AIUsage.objects.get()
        with self.assertRaises(PermissionDenied):
            reconcile_usage(usage_id=usage.pk, actor=self.staff, input_tokens=10, output_tokens=5, note="Synthetic checked receipt")
        with agent_execution(), self.assertRaises(PermissionDenied):
            reconcile_usage(usage_id=usage.pk, actor=self.admin, input_tokens=10, output_tokens=5, note="Synthetic checked receipt")

    def queue_real(self):
        return enqueue(event=self.event, actor=self.owner, kind="chat", prompt="Review this synthetic event",
            idempotency_key=str(uuid.uuid4()))

    def test_real_enqueue_uses_grant_and_idempotent_replay_does_not_reroute(self):
        self.grant(budget_usd="0")
        job = self.queue_real()
        repeated = enqueue(event=self.event, actor=self.owner, kind="chat", prompt="Review this synthetic event",
            idempotency_key=job.idempotency_key)
        self.assertEqual(repeated.pk, job.pk)
        self.assertEqual(job.ai_usage.snapshot["agent_route"], "fallback_budget")
        self.assertEqual(AIUsage.objects.count(), 1)

    def test_mocked_primary_timeout_keeps_hold_without_trying_fallback(self):
        self.grant()
        job = self.queue_real()
        with (patch("apps.assistant.provider.answer_question", side_effect=TimeoutError) as called,
              patch("apps.assistant.provider.pop_usage", return_value={})):
            result = run_one(job_id=job.pk)
            self.assertIsNone(run_one(job_id=job.pk))
        self.assertEqual(called.call_count, 1)
        self.assertEqual(result.status, "failed")
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.snapshot["agent_route"], "primary")
        self.assertEqual(usage.status, "uncertain")
        self.assertIsNone(usage.input_tokens)
        self.assertEqual(AIUsage.objects.count(), 1)

    def test_mocked_free_429_does_not_retry_or_choose_another_free_model(self):
        from apps.assistant.provider import FreeQuotaUnavailable
        self.grant(budget_usd="0")
        job = self.queue_real()
        with (patch("apps.assistant.provider.answer_question", side_effect=FreeQuotaUnavailable) as called,
              patch("apps.assistant.provider.pop_usage", return_value={})):
            result = run_one(job_id=job.pk)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(result.status, "failed")
        self.assertIn("429", result.error)
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.snapshot["model"], "glm-5.3-flash-free")
        self.assertEqual(usage.status, "uncertain")
        self.assertIsNone(usage.total_tokens)
        self.assertEqual(Job.objects.count(), 1)

    def test_mocked_provider_cannot_call_admin_from_its_agent_execution(self):
        self.grant()
        job = self.queue_real()
        def simulated_provider(**kwargs):
            self.assertTrue(in_agent_execution())
            with self.assertRaises(PermissionDenied):
                self.grant(expected_version=1, budget_usd="1")
            return "Fictional event response for review."
        with (patch("apps.assistant.provider.answer_question", side_effect=simulated_provider) as called,
              patch("apps.assistant.provider.pop_usage", return_value={"input_tokens": 100, "output_tokens": 20})):
            result = run_one(job_id=job.pk)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(result.status, "succeeded")
        self.assertFalse(in_agent_execution())
        self.assertEqual(AgentGrant.objects.get().version, 1)

    def test_budget_reduction_after_enqueue_stops_primary_without_late_fallback(self):
        self.grant()
        job = self.queue_real()
        self.account.monthly_budget_usd = Decimal("0"); self.account.save()
        with patch("apps.assistant.provider.answer_question") as called:
            result = run_one(job_id=job.pk)
        called.assert_not_called()
        self.assertEqual(result.status, "failed")
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status, "released")
        self.assertIsNone(usage.dispatch_token)
        self.assertEqual(usage.snapshot["agent_route"], "primary")


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class PostgreSQLAgentGrantConcurrencyTests(TransactionTestCase):
    """Separate connections are necessary; SQLite does not validate these locks."""

    def test_two_events_cannot_reserve_the_same_agents_last_budget_twice(self):
        admin = get_user_model().objects.create_user(username="grant-race-admin", is_superuser=True)
        owner = get_user_model().objects.create_user(username="grant-race-owner")
        profile = AIProfile.objects.create(owner=owner, name="Synthetic race model", provider="openai", model="gpt-5.4-mini",
            mode="paid", input_rate=Decimal("0.75"), cached_rate=Decimal("0.075"), output_rate=Decimal("4.50"),
            max_input_tokens=24000, max_output_tokens=2500)
        account = AIAccount.objects.create(owner=owner, active_profile=profile, paid_enabled=True,
            monthly_budget_usd=Decimal("1"), monthly_token_limit=10000000)
        OpenAIPilotLock.objects.get_or_create(pk=1)
        grant = update_agent_grant(actor=admin, account=account, expected_version=0, name="Romeo-1", enabled=True,
            budget_usd=Decimal("0.04"), primary_profile=profile)
        events = [Event.objects.create(owner=owner, title="Synthetic race " + str(index), brief="Fictional only", is_synthetic=True)
                  for index in range(2)]
        barrier = Barrier(2)
        def submit(event_id):
            try:
                current_owner = get_user_model().objects.get(pk=owner.pk)
                event = Event.objects.get(pk=event_id)
                barrier.wait(timeout=10)
                try:
                    enqueue(event=event, actor=current_owner, kind="chat", prompt="Synthetic budget race",
                        idempotency_key=str(event_id))
                    return "reserved"
                except ValidationError as error:
                    return error.code
            finally:
                connections.close_all()
        with patch("apps.assistant.provider.profile_ready", return_value=True), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [event.pk for event in events]))
        self.assertCountEqual(results, ["reserved", "agent_budget"])
        self.assertEqual(agent_grant_summary(grant)["reserved_usd"], Decimal("0.029250"))
        self.assertEqual(AIUsage.objects.count(), 1)
