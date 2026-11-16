"""Budget behavior with fake adapters, real ledger writes and no network calls."""

from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from apps.events.models import Event
from apps.events.services import update_event
from apps.jobs.models import Job
from apps.jobs.services import _fail, _prepare, cancel, claim_next, enqueue, process_claim, run_one
from apps.ai_management.catalog import catalog_entry
from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.ai_management.services import account_summary, current_month, estimate_cost, get_account, profile_snapshot, reconcile_usage
from apps.ai_management.testing import configure_test_account


@override_settings(OPENAI_API_KEY="test-not-a-real-key", GROQ_API_KEY="test-not-a-real-key", AI_DAILY_JOB_LIMIT=100, AI_MAX_PENDING_PER_EVENT=50)
class BudgetTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="budget-owner", is_staff=True, is_superuser=True)
        self.other = get_user_model().objects.create_user(username="budget-other", is_staff=True)
        self.event = Event.objects.create(owner=self.owner, title="Evento", brief="Prueba de presupuesto", is_synthetic=True)
        self.account = configure_test_account(self.owner)
        self.profile = self.account.active_profile

    def enqueue(self, **extra):
        values = {"event": self.event, "actor": self.owner, "kind": Job.Kind.CHAT,
                  "prompt": "Revisa los datos del evento", "idempotency_key": str(uuid.uuid4())}
        return enqueue(**{**values, **extra})

    def execute(self, observed=None, *, side_effect=None):
        with patch("apps.assistant.provider.answer_question", return_value="Revisa el horario.", side_effect=side_effect) as call:
            with patch("apps.assistant.provider.pop_usage", return_value=observed or {}):
                result = run_one()
        return result, call

    def uncertain(self):
        job = self.enqueue()
        self.execute()
        return AIUsage.objects.get(job=job)

    def reconcile(self, usage, **extra):
        return reconcile_usage(**{"usage_id": usage.pk, "actor": self.owner,
                                   "input_tokens": 100, "output_tokens": 20,
                                   "note": "Comprobado en el registro del proveedor.", **extra})

    def test_default_account_does_not_enable_paid_or_choose_a_provider(self):
        account = get_account(self.other)
        self.assertFalse(account.paid_enabled)
        self.assertEqual(account.monthly_budget_usd, 0)
        self.assertEqual(account.monthly_token_limit, 200000)
        self.assertIsNone(account.active_profile_id)

    def test_no_active_profile_rejects_before_creating_job(self):
        self.account.active_profile = None
        self.account.save()
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "ai_not_configured")
        self.assertFalse(Job.objects.exists())

    def test_other_owners_profile_cannot_spend(self):
        foreign = configure_test_account(self.other).active_profile
        self.account.active_profile = foreign
        self.account.save()
        with self.assertRaises(ValidationError):
            self.enqueue()
        self.assertFalse(AIUsage.objects.exists())

    def test_paid_requires_explicit_permission_and_positive_budget(self):
        for paid, budget in ((False, "10"), (True, "0")):
            self.account.paid_enabled = paid
            self.account.monthly_budget_usd = Decimal(budget)
            self.account.save()
            with self.subTest(paid=paid), self.assertRaises(ValidationError) as caught:
                self.enqueue()
            self.assertEqual(caught.exception.code, "paid_disabled")
        self.assertFalse(Job.objects.exists())

    def test_missing_key_does_not_fallback_or_reserve(self):
        with override_settings(OPENAI_API_KEY="", GROQ_API_KEY="available-free-key"):
            with self.assertRaises(ValidationError):
                self.enqueue()
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_free_requires_confirmation_and_zero_rates(self):
        self.profile.provider, self.profile.model, self.profile.mode = "groq", "openai/gpt-oss-20b", "free"
        self.profile.input_rate = self.profile.cached_rate = self.profile.output_rate = Decimal("0")
        self.profile.save()
        with self.assertRaises(ValidationError):
            self.enqueue()
        self.profile.free_tier_confirmed = True
        self.profile.save()
        self.account.paid_enabled, self.account.monthly_budget_usd = False, Decimal("0")
        self.account.save()
        usage = AIUsage.objects.get(job=self.enqueue())
        self.assertEqual(usage.reserved_usd, 0)
        self.assertEqual(usage.reserved_input_tokens + usage.reserved_output_tokens, 26500)
        self.profile.output_rate = Decimal("1")
        self.profile.save()
        with self.assertRaises(ValidationError):
            self.enqueue()

    def test_enqueue_reserves_maximum_not_fake_usage(self):
        usage = AIUsage.objects.get(job=self.enqueue())
        self.assertEqual(usage.reserved_usd, Decimal("0.029000"))
        self.assertEqual(usage.status, "reserved")
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.estimated_cost_usd)
        summary = account_summary(self.account)
        self.assertEqual(summary["reserved_tokens"], 26500)
        self.assertEqual(summary["used_tokens"], 0)
        self.assertEqual(summary["available_usd"], Decimal("9.971000"))

    def test_maximum_input_rate_is_reserved_even_if_cached_rate_is_higher(self):
        self.profile.cached_rate = Decimal("3")
        self.profile.save()
        usage = AIUsage.objects.get(job=self.enqueue())
        self.assertEqual(usage.reserved_usd, Decimal("0.077000"))

    def test_mini_reserves_full_standard_tariff_without_assuming_incentive_or_cache(self):
        entry = catalog_entry("openai_54_mini")
        for name in ("model", "input_rate", "cached_rate", "output_rate", "verified_on"):
            setattr(self.profile, name, entry[name])
        self.profile.save()
        self.account.monthly_budget_usd = Decimal("0.029249")
        self.account.save()
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "monthly_budget")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.account.monthly_budget_usd = Decimal("0.029250")
        self.account.save()
        usage = AIUsage.objects.get(job=self.enqueue())
        self.assertEqual(usage.reserved_usd, Decimal("0.029250"))
        self.assertEqual(usage.snapshot["cache_policy"], "provider")
        self.assertEqual(account_summary(self.account)["available_usd"], 0)
        self.assertIsNone(usage.estimated_cost_usd)

    def test_mini_keeps_paid_consent_gate_even_with_claimed_free_tier_confirmation(self):
        self.profile.model = "gpt-5.4-mini"
        self.profile.output_rate = Decimal("4.50")
        self.profile.free_tier_confirmed = True
        self.profile.save()
        self.account.paid_enabled = False
        self.account.save()
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "paid_disabled")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_insufficient_money_rolls_back_job_and_reservation(self):
        self.account.monthly_budget_usd = Decimal("0.028999")
        self.account.save()
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "monthly_budget")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_insufficient_tokens_across_events_cannot_bypass_reservations(self):
        self.account.monthly_token_limit = 26500
        self.account.save()
        self.enqueue()
        event = Event.objects.create(owner=self.owner, title="Segundo", brief="Misma cuenta", is_synthetic=True)
        with self.assertRaises(ValidationError) as caught:
            self.enqueue(event=event)
        self.assertEqual(caught.exception.code, "monthly_tokens")
        self.assertEqual(AIUsage.objects.count(), 1)

    def test_idempotent_replay_does_not_reserve_again_after_limits_change(self):
        job = self.enqueue(idempotency_key="one-effect")
        self.account.monthly_budget_usd = 0
        self.account.paid_enabled = False
        self.account.save()
        repeated = self.enqueue(idempotency_key="one-effect")
        self.assertEqual(repeated.pk, job.pk)
        self.assertEqual(AIUsage.objects.count(), 1)

    def test_reservation_month_is_lima_and_undispatched_work_expires_at_rollover(self):
        # November 1 UTC is still October 31 in Lima.
        instant = datetime(2026, 11, 1, 2, tzinfo=datetime_timezone.utc)
        with patch("apps.ai_management.services.timezone.now", return_value=instant):
            job = self.enqueue()
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(str(usage.month), "2026-10-01")
        self.assertEqual(str(current_month(instant)), "2026-10-01")
        november = datetime(2026, 11, 1, 5, 1, tzinfo=datetime_timezone.utc)
        with patch("apps.ai_management.services.timezone.now", return_value=november):
            result, call = self.execute({"input_tokens": 20, "output_tokens": 5, "total_tokens": 25})
        call.assert_not_called()
        usage.refresh_from_db()
        self.assertEqual(str(usage.month), "2026-10-01")
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertIn("Cambió el mes", result.error)
        self.assertEqual(usage.status, AIUsage.Status.RELEASED)
        self.assertIsNone(usage.dispatch_token)
        self.assertIsNone(usage.total_tokens)
        self.assertEqual(account_summary(self.account, usage.month)["used_tokens"], 0)

    def test_new_month_exhausted_budget_cannot_be_bypassed_by_old_reservation(self):
        october = datetime(2026, 11, 1, 4, 59, tzinfo=datetime_timezone.utc)
        november = datetime(2026, 11, 1, 5, 1, tzinfo=datetime_timezone.utc)
        with patch("apps.ai_management.services.timezone.now", return_value=october):
            old_job = self.enqueue()
        # Exhaust the new month's budget with another completed request. Leave
        # the old queued request intact to exercise the boundary guard.
        self.account.monthly_budget_usd = Decimal("0.029000")
        self.account.save()
        with patch("apps.ai_management.services.timezone.now", return_value=november):
            new_job = self.enqueue()
            Job.objects.filter(pk=old_job.pk).update(created_at=november + timedelta(seconds=1))
            new_result, new_call = self.execute({"input_tokens": 24000, "output_tokens": 2500, "total_tokens": 26500})
            self.assertEqual(new_result.pk, new_job.pk)
            self.assertEqual(new_call.call_count, 1)
            self.assertEqual(account_summary(self.account)["available_usd"], 0)
            old_result, old_call = self.execute()
        old_call.assert_not_called()
        self.assertEqual(old_result.pk, old_job.pk)
        self.assertEqual(old_result.status, Job.Status.FAILED)
        self.assertEqual(AIUsage.objects.get(job=old_job).status, AIUsage.Status.RELEASED)

    def test_late_usage_for_a_call_already_dispatched_retains_original_month(self):
        october = datetime(2026, 11, 1, 4, 59, 30, tzinfo=datetime_timezone.utc)
        november = datetime(2026, 11, 1, 5, 0, 1, tzinfo=datetime_timezone.utc)
        with patch("apps.ai_management.services.timezone.now", return_value=october):
            job = self.enqueue()
            claim = claim_next()
            self.assertIsNotNone(_prepare(claim.pk, claim.claim_token))
        with patch("apps.ai_management.services.timezone.now", return_value=november):
            _fail(job.pk, claim.claim_token, {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25})
            self.assertEqual(account_summary(self.account)["used_tokens"], 0)
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(str(usage.month), "2026-10-01")
        self.assertEqual(usage.status, AIUsage.Status.SETTLED)
        self.assertEqual(usage.total_tokens, 25)
        self.assertEqual(account_summary(self.account, usage.month)["used_tokens"], 25)

    def test_success_settles_observed_usage_and_releases_surplus(self):
        job = self.enqueue()
        result, _call = self.execute({"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500,
                                      "cached_input_tokens": 200, "reasoning_tokens": 50, "secret_metadata": "discard"})
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(result.status, Job.Status.SUCCEEDED)
        self.assertEqual(usage.status, "settled")
        self.assertEqual(usage.accounting_source, "provider")
        self.assertEqual(usage.estimated_cost_usd, Decimal("0.001820"))
        self.assertEqual(usage.cached_tokens, 200)
        self.assertEqual(usage.reasoning_tokens, 50)
        self.assertNotIn("secret_metadata", result.result["usage"])
        summary = account_summary(self.account)
        self.assertEqual(summary["reserved_tokens"], 0)
        self.assertEqual(summary["used_tokens"], 1500)
        self.assertEqual(summary["spent_usd"], Decimal("0.001820"))

    def test_actual_zero_usage_is_distinct_from_unknown(self):
        job = self.enqueue()
        self.execute({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status, "settled")
        self.assertEqual(usage.total_tokens, 0)
        self.assertEqual(usage.estimated_cost_usd, 0)

    def test_success_without_usage_retains_reservation_and_null_tokens(self):
        usage = self.uncertain()
        self.assertEqual(usage.status, "uncertain")
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.output_tokens)
        self.assertIsNone(usage.estimated_cost_usd)
        self.assertEqual(account_summary(self.account)["reserved_usd"], Decimal("0.029000"))

    def test_partial_and_inconsistent_usage_do_not_release_reservation(self):
        for observed in ({"input_tokens": 100}, {"input_tokens": 10, "output_tokens": 5, "total_tokens": 99},
                         {"input_tokens": 10, "output_tokens": 5, "cached_input_tokens": 11}):
            job = self.enqueue()
            self.execute(observed)
            usage = AIUsage.objects.get(job=job)
            self.assertEqual(usage.status, "uncertain")
            self.assertIsNone(usage.estimated_cost_usd)

    def test_combined_provider_tokens_above_postgresql_integer_remain_uncertain(self):
        for observed in ({"input_tokens": 2_000_000_000, "output_tokens": 2_000_000_000, "total_tokens": 4_000_000_000},
                         {"input_tokens": 2_000_000_000, "output_tokens": 2_000_000_000},
                         {"input_tokens": 10, "output_tokens": 5, "total_tokens": 4_000_000_000}):
            # Independent malformed receipt cases: an overrun must block later
            # jobs globally, so roll back each case rather than bypassing it.
            with self.subTest(observed=observed), transaction.atomic():
                job = self.enqueue()
                self.execute(observed)
                usage = AIUsage.objects.get(job=job)
                self.assertEqual(usage.status, AIUsage.Status.UNCERTAIN)
                self.assertEqual(usage.input_tokens, observed["input_tokens"])
                self.assertEqual(usage.output_tokens, observed["output_tokens"])
                self.assertIsNone(usage.total_tokens)
                self.assertIsNone(usage.estimated_cost_usd)
                self.assertEqual(usage.reserved_usd, Decimal("0.029000"))
                transaction.set_rollback(True)

    def test_cancel_before_dispatch_releases_reservation(self):
        job = self.enqueue()
        cancel(job_id=job.pk, actor=self.owner)
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status, "released")
        self.assertIsNone(usage.dispatch_token)
        self.assertEqual(account_summary(self.account)["reserved_tokens"], 0)

    def test_cancel_during_call_preserves_late_observed_cost(self):
        job = self.enqueue()
        def cancel_in_call(**kwargs):
            cancel(job_id=job.pk, actor=self.owner)
            pending = AIUsage.objects.get(job=job)
            self.assertEqual(pending.status, "uncertain")
            return "Resultado que no se publica."
        result, _call = self.execute({"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}, side_effect=cancel_in_call)
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(result.status, Job.Status.CANCELLED)
        self.assertEqual(usage.status, "settled")
        self.assertEqual(usage.estimated_cost_usd, Decimal("0.000140"))
        self.assertFalse(hasattr(result, "assistant_message"))

    def test_timeout_after_dispatch_is_uncertain_and_never_retried(self):
        job = self.enqueue()
        result, call = self.execute(side_effect=TimeoutError("not stored"))
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertEqual(usage.status, "uncertain")
        self.assertIsNone(run_one())
        self.assertEqual(call.call_count, 1)

    def test_expiry_before_dispatch_releases_but_after_dispatch_observed_cost_remains(self):
        first = self.enqueue()
        claim = claim_next()
        Job.objects.filter(pk=first.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(claim_next())
        self.assertEqual(AIUsage.objects.get(job=first).status, "released")
        second = self.enqueue()
        def expire_during_call(**kwargs):
            Job.objects.filter(pk=second.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
            return "Respuesta tardía."
        result, _call = self.execute({"input_tokens": 100, "output_tokens": 20}, side_effect=expire_during_call)
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertEqual(AIUsage.objects.get(job=second).status, "settled")

    def test_stale_before_call_releases_and_stale_after_call_still_accounts(self):
        first = self.enqueue()
        update_event(event_id=self.event.pk, actor=self.owner, title="Nueva ficha")
        _result, call = self.execute()
        call.assert_not_called()
        self.assertEqual(AIUsage.objects.get(job=first).status, "released")
        second = self.enqueue()
        def change_during_call(**kwargs):
            update_event(event_id=self.event.pk, actor=self.owner, title="Cambió otra vez")
            return "Respuesta obsoleta."
        result, _call = self.execute({"input_tokens": 100, "output_tokens": 20}, side_effect=change_during_call)
        self.assertEqual(result.status, Job.Status.STALE)
        self.assertEqual(AIUsage.objects.get(job=second).status, "settled")

    def test_preflight_failure_releases_without_calling_provider(self):
        job = self.enqueue()
        with patch("apps.assistant.provider.ensure_input_fits", side_effect=ValidationError("Too large")):
            _result, call = self.execute()
        call.assert_not_called()
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status, "released")
        self.assertIsNone(usage.dispatch_token)

    def test_editing_or_disabling_profile_revokes_queued_dispatch(self):
        job = self.enqueue()
        snapshot = AIUsage.objects.get(job=job).snapshot
        self.profile.version += 1
        self.profile.input_rate = Decimal("9")
        self.profile.save()
        _result, call = self.execute()
        call.assert_not_called()
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status, "released")
        self.assertEqual(usage.snapshot, snapshot)

    def test_disabling_paid_or_reducing_limits_revokes_queued_dispatch(self):
        job = self.enqueue()
        self.account.monthly_token_limit = 1
        self.account.save()
        _result, call = self.execute()
        call.assert_not_called()
        self.assertEqual(AIUsage.objects.get(job=job).status, "released")

    def test_revoking_paid_permission_or_profile_stops_queued_calls(self):
        first = self.enqueue()
        self.account.paid_enabled = False
        self.account.save()
        _result, call = self.execute()
        call.assert_not_called()
        self.assertEqual(AIUsage.objects.get(job=first).status, "released")
        self.account.paid_enabled = True
        self.account.save()
        second = self.enqueue()
        self.profile.enabled = False
        self.profile.save()
        _result, call = self.execute()
        call.assert_not_called()
        self.assertEqual(AIUsage.objects.get(job=second).status, "released")

    def test_switching_selected_profile_preserves_an_unchanged_queued_snapshot(self):
        job = self.enqueue()
        alternate = AIProfile.objects.create(
            owner=self.owner, name="Otro perfil", provider="groq", model="openai/gpt-oss-20b",
            mode="free", free_tier_confirmed=True,
        )
        self.account.active_profile = alternate
        self.account.save()
        def observe_profile(**kwargs):
            from apps.assistant import provider
            self.assertEqual(provider._configuration()["provider"], "openai")
            return "Respuesta del perfil reservado."
        result, call = self.execute({"input_tokens": 100, "output_tokens": 20}, side_effect=observe_profile)
        self.assertEqual(result.status, Job.Status.SUCCEEDED)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(AIUsage.objects.get(job=job).snapshot["provider"], "openai")

    def test_expired_dispatched_crash_preserves_hold_when_swept_by_worker(self):
        job = self.enqueue()
        claim = claim_next()
        self.assertIsNotNone(_prepare(claim.pk, claim.claim_token))
        Job.objects.filter(pk=job.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(claim_next())
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status, "uncertain")
        self.assertIsNone(usage.estimated_cost_usd)
        self.assertEqual(account_summary(self.account)["reserved_usd"], Decimal("0.029000"))

    def test_invalid_result_and_provider_failure_still_settle_observed_usage(self):
        first = self.enqueue()
        with patch("apps.assistant.provider.answer_question", return_value={"wrong": "type"}):
            with patch("apps.assistant.provider.pop_usage", return_value={"input_tokens": 10, "output_tokens": 2}):
                result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertEqual(AIUsage.objects.get(job=first).status, "settled")
        second = self.enqueue()
        result, _call = self.execute({"input_tokens": 15, "output_tokens": 0}, side_effect=RuntimeError("Do not store"))
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertEqual(AIUsage.objects.get(job=second).total_tokens, 15)

    def test_reentrant_process_of_dispatched_claim_cannot_issue_second_call(self):
        job = self.enqueue()
        claim = claim_next()
        def second_worker(**kwargs):
            duplicate = process_claim(claim)
            self.assertEqual(duplicate.status, Job.Status.RUNNING)
            return "Respuesta única."
        with patch("apps.assistant.provider.answer_question", side_effect=second_worker) as call:
            with patch("apps.assistant.provider.pop_usage", return_value={"input_tokens": 10, "output_tokens": 2}):
                process_claim(claim)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(AIUsage.objects.get(job=job).total_tokens, 12)

    def test_price_snapshot_survives_profile_change_during_call(self):
        job = self.enqueue()
        def change_tariff(**kwargs):
            self.profile.input_rate = Decimal("9")
            self.profile.version += 1
            self.profile.save()
            return "Respuesta."
        self.execute({"input_tokens": 1000, "output_tokens": 0}, side_effect=change_tariff)
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.estimated_cost_usd, Decimal("0.001000"))
        self.assertEqual(usage.snapshot["input_rate"], "1.000000")

    def test_observed_overage_is_recorded_in_full_and_blocks_further_jobs(self):
        job = self.enqueue()
        self.execute({"input_tokens": 30000, "output_tokens": 1})
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.input_tokens, 30000)
        self.assertEqual(usage.estimated_cost_usd, Decimal("0.030002"))
        self.assertEqual(account_summary(self.account)["limit_breach_count"], 1)
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "usage_limit_breach")

    def test_replaying_a_claim_does_not_call_or_settle_twice(self):
        job = self.enqueue()
        claim = claim_next()
        with patch("apps.assistant.provider.answer_question", return_value="Respuesta.") as call:
            with patch("apps.assistant.provider.pop_usage", return_value={"input_tokens": 100, "output_tokens": 20}):
                process_claim(claim)
                process_claim(claim)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(AIUsage.objects.filter(job=job).count(), 1)
        self.assertEqual(account_summary(self.account)["used_tokens"], 120)

    def test_ledger_fencing_rejects_wrong_token(self):
        usage = self.uncertain()
        _fail(usage.job_id, uuid.uuid4(), {"input_tokens": 10, "output_tokens": 1})
        usage.refresh_from_db()
        self.assertEqual(usage.status, "uncertain")
        self.assertIsNone(usage.estimated_cost_usd)

    def test_manual_reconciliation_records_source_and_releases_reservation(self):
        usage = self.reconcile(self.uncertain())
        self.assertEqual(usage.accounting_source, "manual")
        self.assertEqual(usage.reconciled_by_id, self.owner.pk)
        self.assertIsNotNone(usage.reconciled_at)
        self.assertEqual(usage.reconciliation_snapshot["input_tokens"], 100)
        self.assertEqual(account_summary(self.account)["reserved_tokens"], 0)
        self.assertEqual(account_summary(self.account)["used_tokens"], 120)

    def test_manual_zero_requires_explicit_note_and_is_not_provider_usage(self):
        usage = self.uncertain()
        with self.assertRaises(ValidationError):
            self.reconcile(usage, input_tokens=0, output_tokens=0, note=" ")
        usage = self.reconcile(usage, input_tokens=0, output_tokens=0, note="Confirmación externa: solicitud sin consumo.")
        self.assertEqual(usage.estimated_cost_usd, 0)
        self.assertEqual(usage.accounting_source, "manual")

    def test_manual_reconciliation_replay_is_idempotent_but_other_content_rejected(self):
        usage = self.reconcile(self.uncertain())
        first_time = usage.reconciled_at
        repeated = self.reconcile(usage)
        self.assertEqual(repeated.reconciled_at, first_time)
        with self.assertRaises(ValidationError) as caught:
            self.reconcile(usage, output_tokens=21)
        self.assertEqual(caught.exception.code, "stale_reconciliation")

    def test_manual_reconciliation_requires_superadmin_and_account_owner(self):
        usage = self.uncertain()
        with self.assertRaises(PermissionDenied):
            self.reconcile(usage, actor=self.other)
        self.owner.is_superuser = False
        self.owner.save()
        with self.assertRaises(PermissionDenied):
            self.reconcile(usage)

    def test_manual_reconciliation_rejects_active_and_known_provider_usage(self):
        job = self.enqueue()
        with self.assertRaises(ValidationError):
            self.reconcile(AIUsage.objects.get(job=job))
        self.execute({"input_tokens": 100, "output_tokens": 20})
        with self.assertRaises(ValidationError):
            self.reconcile(AIUsage.objects.get(job=job))

    def test_manual_reconciliation_rejects_invalid_numbers_and_subcounts(self):
        usage = self.uncertain()
        for values in ({"input_tokens": True}, {"output_tokens": -1}, {"input_tokens": "10"},
                       {"cached_tokens": 101}, {"reasoning_tokens": 21}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.reconcile(usage, **values)

    def test_combined_manual_tokens_above_postgresql_integer_are_rejected_without_writes(self):
        usage = self.uncertain()
        with self.assertRaises(ValidationError) as caught:
            self.reconcile(usage, input_tokens=2_000_000_000, output_tokens=2_000_000_000)
        self.assertEqual(caught.exception.code, "usage_total_too_large")
        usage.refresh_from_db()
        self.assertEqual(usage.status, AIUsage.Status.UNCERTAIN)
        self.assertIsNone(usage.total_tokens)
        self.assertIsNone(usage.estimated_cost_usd)
        self.assertIsNone(usage.reconciled_by_id)
        self.assertEqual(usage.reconciliation_snapshot, {})

    def test_late_provider_usage_supersedes_manual_estimate_preserving_manual_audit(self):
        usage = self.reconcile(self.uncertain())
        original = dict(usage.reconciliation_snapshot)
        original_time = usage.reconciled_at
        _fail(usage.job_id, usage.dispatch_token, {"input_tokens": 200, "output_tokens": 40})
        usage.refresh_from_db()
        self.assertEqual(usage.accounting_source, "provider")
        self.assertEqual(usage.total_tokens, 240)
        self.assertEqual(usage.reconciliation_snapshot, original)
        self.assertEqual(usage.reconciled_at, original_time)
        self.assertEqual(usage.reconciled_by_id, self.owner.pk)
        self.reconcile(usage)  # Exact old command returns without rewriting real usage.
        usage.refresh_from_db()
        self.assertEqual(usage.total_tokens, 240)
        _fail(usage.job_id, usage.dispatch_token, {"input_tokens": 999, "output_tokens": 999})
        usage.refresh_from_db()
        self.assertEqual(usage.total_tokens, 240)

    def test_partial_late_provider_usage_cannot_erase_manual_reconciliation(self):
        usage = self.reconcile(self.uncertain())
        _fail(usage.job_id, usage.dispatch_token, {"input_tokens": 999})
        usage.refresh_from_db()
        self.assertEqual(usage.accounting_source, "manual")
        self.assertEqual(usage.input_tokens, 100)

    def test_calculator_prices_cached_input_once_and_rounds_up_small_costs(self):
        snapshot = profile_snapshot(self.profile)
        self.assertEqual(estimate_cost(snapshot, input_tokens=1000, output_tokens=500, cached_tokens=200), Decimal("0.001820"))
        self.assertEqual(estimate_cost(snapshot, input_tokens=1, output_tokens=0, cached_tokens=1), Decimal("0.000001"))
        for values in ({"input_tokens": True, "output_tokens": 0}, {"input_tokens": 1, "output_tokens": 0, "cached_tokens": 2}):
            with self.assertRaises(ValidationError):
                estimate_cost(snapshot, **values)
        for invalid in ("NaN", "Infinity", "-1", "not-a-number"):
            with self.assertRaises(ValidationError):
                estimate_cost({**snapshot, "input_rate": invalid}, input_tokens=1, output_tokens=0)


@skipUnlessDBFeature("has_select_for_update_skip_locked")
@override_settings(OPENAI_API_KEY="test-not-a-real-key", AI_DAILY_JOB_LIMIT=100, AI_MAX_PENDING_PER_EVENT=10)
class PostgreSQLBudgetConcurrencyTests(TransactionTestCase):
    """Real separate connections; intentionally skipped on SQLite."""

    def test_reservations_serialize_across_events_for_one_owner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        owner = get_user_model().objects.create_user(username="budget-pg")
        configure_test_account(owner, budget="0.040000")  # One .029 reservation, never two.
        events = [Event.objects.create(owner=owner, title=str(index), brief="Carrera de presupuesto", is_synthetic=True) for index in range(2)]
        barrier = Barrier(2)
        def reserve(event_id):
            try:
                actor = get_user_model().objects.get(pk=owner.pk)
                event = Event.objects.get(pk=event_id)
                barrier.wait(timeout=10)
                try:
                    enqueue(event=event, actor=actor, kind=Job.Kind.CHAT,
                            prompt="Revisa mi evento", idempotency_key=str(event_id))
                    return "accepted"
                except ValidationError as error:
                    return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(reserve, [event.pk for event in events]))
        self.assertCountEqual(results, ["accepted", "monthly_budget"])
        self.assertEqual(AIUsage.objects.count(), 1)
