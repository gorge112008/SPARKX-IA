"""Lifetime OpenAI pilot limits; synthetic ledgers, no provider calls or secrets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.services import enqueue
from apps.ai_management.models import AIAccount, AIProfile, AIUsage, OpenAIPilotLock
from apps.ai_management.pilot import (OPENAI_PILOT_LIMIT_USD, OPENAI_PILOT_MINIMUM_RATES,
                    openai_pilot_summary, reserve_openai_pilot_locked, validate_openai_pilot_tariffs)
from apps.ai_management.services import current_month, mark_dispatched, profile_snapshot


def owner_fixture(label):
    owner = get_user_model().objects.create_user(username="pilot-" + label)
    profile = AIProfile.objects.create(owner=owner, name="Controlled OpenAI fixture", provider="openai",
        model="gpt-5.4-mini", mode="paid", input_rate=Decimal("0.75"), cached_rate=Decimal("0.075"), output_rate=Decimal("4.50"),
        max_input_tokens=24000, max_output_tokens=2500)
    account = AIAccount.objects.create(owner=owner, active_profile=profile, paid_enabled=True,
        monthly_budget_usd="100", monthly_token_limit=10000000)
    event = Event.objects.create(owner=owner, title="Fictional pilot " + label, brief="Synthetic QA only", is_synthetic=True)
    return owner, profile, account, event


def historical_usage(owner, account, event, *, status="settled", reserve="0.5", cost=None,
                     month=None, model="gpt-5.4-mini", provider="openai", dispatched=None):
    """Explicit historical accounting fixture, never an inference receipt."""
    job = Job.objects.create(event=event, actor=owner, kind="plan", prompt="Synthetic history fixture",
        base_revision=event.revision, idempotency_key=str(uuid.uuid4()), request_hash="0" * 64,
        status="failed")
    if dispatched is None:
        dispatched = status not in ("reserved", "released")
    return AIUsage.objects.create(job=job, account=account, month=month or current_month(),
        snapshot={"provider":provider,"model":model}, status=status,
        reserved_input_tokens=24000, reserved_output_tokens=2500, reserved_usd=reserve,
        estimated_cost_usd=cost, dispatch_token=uuid.uuid4() if dispatched else None)


class OpenAIPilotBudgetTests(TestCase):
    def setUp(self):
        OpenAIPilotLock.objects.get_or_create(pk=1)  # Test fixture after TransactionTestCase flushes.
        self.owner,self.profile,self.account,self.event = owner_fixture("primary")
        self.other,self.other_profile,self.other_account,self.other_event = owner_fixture("other")
        self.ready = patch("apps.assistant.provider.profile_ready", return_value=True)
        self.ready.start(); self.addCleanup(self.ready.stop)

    def enqueue(self, *, event=None, owner=None):
        return enqueue(event=event or self.event, actor=owner or self.owner, kind="plan",
                       prompt="Prepare a controlled synthetic proposal", idempotency_key=str(uuid.uuid4()))

    def prior(self, **changes):
        return historical_usage(self.owner,self.account,self.event,**changes)

    def test_server_cap_and_empty_summary_are_global_read_only(self):
        before = (Job.objects.count(),AIUsage.objects.count(),OpenAIPilotLock.objects.count())
        summary = openai_pilot_summary()
        self.assertEqual(OPENAI_PILOT_LIMIT_USD, Decimal("1"))
        self.assertEqual(summary["limit_usd"], Decimal("1"))
        self.assertEqual(summary["spent_usd"], Decimal("0"))
        self.assertEqual(summary["reserved_usd"], Decimal("0"))
        self.assertEqual(summary["available_usd"], Decimal("1"))
        self.assertEqual(before,(Job.objects.count(),AIUsage.objects.count(),OpenAIPilotLock.objects.count()))

    def test_reservation_uses_largest_input_rate_and_counts_against_global_cap(self):
        job = self.enqueue()
        self.assertEqual(job.ai_usage.reserved_usd, Decimal("0.029250"))
        summary = openai_pilot_summary()
        self.assertEqual(summary["reserved_usd"], Decimal("0.029250"))
        self.assertEqual(summary["available_usd"], Decimal("0.970750"))

    def test_only_two_reviewed_text_models_accept_their_exact_minimum_tariffs(self):
        self.assertEqual(set(OPENAI_PILOT_MINIMUM_RATES), {"gpt-5.4-mini", "gpt-6-luna"})
        for model, rates in OPENAI_PILOT_MINIMUM_RATES.items():
            with self.subTest(model=model):
                self.profile.model = model
                self.profile.input_rate, self.profile.cached_rate, self.profile.output_rate = rates
                self.profile.version += 1
                self.profile.save()
                usage = self.enqueue().ai_usage
                expected = Decimal("0.029250") if model == "gpt-5.4-mini" else Decimal("0.003650")
                self.assertEqual(usage.reserved_usd, expected)

    def test_zero_or_lower_custom_rates_cannot_discount_any_reviewed_model(self):
        keys = ("input_rate", "cached_rate", "output_rate")
        for model, rates in OPENAI_PILOT_MINIMUM_RATES.items():
            for key, floor in zip(keys, rates):
                for discounted in (Decimal("0"), floor - Decimal("0.000001")):
                    with self.subTest(model=model, key=key, discounted=discounted):
                        self.profile.model = model
                        self.profile.input_rate, self.profile.cached_rate, self.profile.output_rate = rates
                        setattr(self.profile, key, discounted)
                        self.profile.save()
                        with self.assertRaises(ValidationError) as caught:
                            self.enqueue()
                        self.assertEqual(caught.exception.code, "openai_pilot_tariffs")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_higher_custom_rates_are_conservative_and_allowed(self):
        self.profile.input_rate = Decimal("1")
        self.profile.cached_rate = Decimal("2")
        self.profile.output_rate = Decimal("10")
        self.profile.save()
        self.assertEqual(self.enqueue().ai_usage.reserved_usd, Decimal("0.073000"))

    def test_validator_rejects_missing_malformed_unreviewed_or_free_openai_snapshot(self):
        snapshot = profile_snapshot(self.profile)
        variants = [{**snapshot, "model": model} for model in ("gpt-custom", "gpt-5.4-mini-preview", ["gpt-5.4-mini"])]
        variants += [{**snapshot, "mode": mode} for mode in ("free", "local", None)]
        variants += [{**snapshot, "input_rate": rate} for rate in (None, True, "NaN", "Infinity", "-1", [])]
        variants += [{key: value for key, value in snapshot.items() if key != "cached_rate"}]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValidationError) as caught:
                validate_openai_pilot_tariffs(variant)
            self.assertEqual(caught.exception.code, "openai_pilot_tariffs")
        self.assertFalse(Job.objects.exists())

    def test_reservation_revalidates_forged_zero_snapshot_before_any_hold(self):
        snapshot = {**profile_snapshot(self.profile), "input_rate": "0", "cached_rate": "0", "output_rate": "0"}
        job = Job(event=self.event, actor=self.owner)
        with self.assertRaises(ValidationError) as caught:
            reserve_openai_pilot_locked(job=job, snapshot=snapshot, reserve_usd=Decimal("0"))
        self.assertEqual(caught.exception.code, "openai_pilot_tariffs")
        self.assertFalse(AIUsage.objects.exists())

    def test_dispatch_revalidates_saved_zero_tariff_without_marking_sent(self):
        usage = self.enqueue().ai_usage
        usage.snapshot = {**usage.snapshot, "output_rate": "0"}
        usage.save(update_fields=["snapshot"])
        with self.assertRaises(ValidationError) as caught:
            mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "openai_pilot_tariffs")
        usage.refresh_from_db()
        self.assertEqual(usage.status, "reserved")
        self.assertIsNone(usage.dispatch_token)

    def test_dispatch_revalidates_saved_unknown_model_without_marking_sent(self):
        usage = self.enqueue().ai_usage
        usage.snapshot = {**usage.snapshot, "model": "unreviewed-openai-model"}
        usage.save(update_fields=["snapshot"])
        with self.assertRaises(ValidationError) as caught:
            mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "openai_pilot_tariffs")
        usage.refresh_from_db()
        self.assertIsNone(usage.dispatch_token)

    def test_dispatch_rejects_imported_hold_below_its_saved_tariff(self):
        usage = self.enqueue().ai_usage
        usage.reserved_usd = Decimal("0")
        usage.save(update_fields=["reserved_usd"])
        with self.assertRaises(ValidationError) as caught:
            mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "openai_pilot_under_reserved")
        usage.refresh_from_db()
        self.assertIsNone(usage.dispatch_token)

    def test_dispatch_rejects_token_limits_larger_than_the_reserved_hold(self):
        usage = self.enqueue().ai_usage
        usage.snapshot = {**usage.snapshot, "max_input_tokens": 24001}
        usage.save(update_fields=["snapshot"])
        with self.assertRaises(ValidationError) as caught:
            mark_dispatched(usage, uuid.uuid4())
        self.assertEqual(caught.exception.code, "openai_pilot_under_reserved")
        usage.refresh_from_db()
        self.assertIsNone(usage.dispatch_token)

    def test_spent_and_holds_cross_accounts_months_and_models(self):
        self.prior(reserve="0.3",cost="0.2")
        historical_usage(self.other,self.other_account,self.other_event,reserve="0.4",cost="0.3",
                         month=date(2025,1,1),model="gpt-6-luna")
        self.prior(status="uncertain",reserve="0.4",month=date(2025,2,1),model="retired-openai-model")
        summary = openai_pilot_summary()
        self.assertEqual(summary["spent_usd"], Decimal("0.5"))
        self.assertEqual(summary["reserved_usd"], Decimal("0.4"))
        self.assertEqual(summary["available_usd"], Decimal("0.1"))
        self.assertEqual(summary["usage_count"],3)

    def test_month_model_and_owner_changes_cannot_reset_a_spent_pilot(self):
        self.prior(reserve="1",cost="1",month=date(2025,1,1))
        for owner,profile,event in ((self.owner,self.profile,self.event),(self.other,self.other_profile,self.other_event)):
            for model in ("gpt-5.4-mini","gpt-6-luna"):
                profile.model=model;profile.version+=1;profile.save()
                with self.subTest(owner=owner.pk,model=model), self.assertRaises(ValidationError) as failure:
                    self.enqueue(event=event,owner=owner)
                self.assertEqual(failure.exception.code,"openai_pilot_budget")
        self.assertEqual(Job.objects.count(),1)
        self.assertEqual(AIUsage.objects.count(),1)

    def test_reserved_dispatched_and_unknown_rows_all_keep_full_holds(self):
        for status in ("reserved","dispatched","uncertain"):
            self.prior(status=status,reserve="0.3")
        summary = openai_pilot_summary()
        self.assertEqual(summary["reserved_usd"], Decimal("0.9"))
        self.assertEqual(summary["available_usd"], Decimal("0.1"))
        self.assertEqual(summary["spent_usd"], Decimal("0"))

    def test_settled_without_observed_cost_is_held_instead_of_fabricated_as_zero(self):
        self.prior(status="settled",reserve="0.4",cost=None)
        summary = openai_pilot_summary()
        self.assertEqual(summary["reserved_usd"], Decimal("0.4"))
        self.assertEqual(summary["available_usd"], Decimal("0.6"))
        self.assertEqual(summary["uncertain_count"],1)

    def test_only_undispatched_releases_free_a_hold(self):
        self.prior(status="released",reserve="0.5",dispatched=False)
        self.prior(status="released",reserve="0.3",dispatched=True)
        summary = openai_pilot_summary()
        self.assertEqual(summary["reserved_usd"], Decimal("0.3"))
        self.assertEqual(summary["available_usd"], Decimal("0.7"))

    def test_exact_total_one_dollar_is_allowed_but_another_reservation_is_not(self):
        self.prior(status="uncertain",reserve="0.970750")
        job=self.enqueue()
        self.assertEqual(openai_pilot_summary()["committed_usd"],Decimal("1"))
        self.assertEqual(job.ai_usage.reserved_usd,Decimal("0.029250"))
        with self.assertRaises(ValidationError) as failure:self.enqueue()
        self.assertEqual(failure.exception.code,"openai_pilot_budget")
        self.assertEqual(AIUsage.objects.count(),2)

    def test_observed_overrun_blocks_further_work_even_with_apparent_remaining_money(self):
        historical_usage(self.other,self.other_account,self.other_event,reserve="0.4",cost="0.5",month=date(2025,1,1))
        self.assertEqual(openai_pilot_summary()["available_usd"],Decimal("0.5"))
        with self.assertRaises(ValidationError) as failure:self.enqueue()
        self.assertEqual(failure.exception.code,"openai_pilot_usage_breach")

    def test_partial_observed_token_breach_also_blocks_new_reservations(self):
        prior=self.prior(status="uncertain",reserve="0.1")
        prior.input_tokens=24001;prior.save(update_fields=["input_tokens"])
        with self.assertRaises(ValidationError) as failure:self.enqueue()
        self.assertEqual(failure.exception.code,"openai_pilot_usage_breach")

    def test_non_synthetic_event_is_rejected_before_job_and_ledger_persist(self):
        self.event.is_synthetic=False;self.event.save(update_fields=["is_synthetic"])
        with self.assertRaises(ValidationError) as failure:self.enqueue()
        self.assertEqual(failure.exception.code,"openai_pilot_synthetic_required")
        self.assertEqual(Job.objects.count(),0)
        self.assertEqual(AIUsage.objects.count(),0)

    def test_dispatch_rechecks_synthetic_declaration_without_sending(self):
        usage=self.enqueue().ai_usage
        Event.objects.filter(pk=self.event.pk).update(is_synthetic=False)
        with self.assertRaises(ValidationError) as failure:mark_dispatched(usage,uuid.uuid4())
        self.assertEqual(failure.exception.code,"openai_pilot_synthetic_required")
        usage.refresh_from_db()
        self.assertEqual(usage.status,"reserved")
        self.assertIsNone(usage.dispatch_token)

    def test_dispatch_counts_own_existing_hold_once(self):
        self.prior(status="uncertain",reserve="0.970750")
        usage=self.enqueue().ai_usage
        self.assertTrue(mark_dispatched(usage,uuid.uuid4()))
        self.assertEqual(openai_pilot_summary()["committed_usd"],Decimal("1"))

    def test_dispatch_refuses_global_overcommit_created_since_enqueue(self):
        usage=self.enqueue().ai_usage
        historical_usage(self.other,self.other_account,self.other_event,status="uncertain",reserve="0.99")
        with self.assertRaises(ValidationError) as failure:mark_dispatched(usage,uuid.uuid4())
        self.assertEqual(failure.exception.code,"openai_pilot_budget")
        usage.refresh_from_db()
        self.assertIsNone(usage.dispatch_token)

    def test_missing_mutex_fails_closed_instead_of_resetting_budget(self):
        OpenAIPilotLock.objects.all().delete()
        with self.assertRaises(ValidationError) as failure:self.enqueue()
        self.assertEqual(failure.exception.code,"openai_pilot_not_ready")
        self.assertEqual(OpenAIPilotLock.objects.count(),0)
        self.assertEqual(AIUsage.objects.count(),0)

    def test_monthly_budget_permission_and_ownership_are_still_required(self):
        self.account.paid_enabled=False;self.account.save(update_fields=["paid_enabled"])
        with self.assertRaises(ValidationError) as failure:self.enqueue()
        self.assertEqual(failure.exception.code,"paid_disabled")
        self.assertEqual(AIUsage.objects.count(),0)

    def test_exhausted_openai_pilot_does_not_disable_free_provider(self):
        self.prior(reserve="1",cost="1")
        self.other_profile.provider="opencode";self.other_profile.model="glm-5.3-flash-free"
        self.other_profile.mode="free";self.other_profile.free_tier_confirmed=True
        self.other_profile.input_rate=self.other_profile.cached_rate=self.other_profile.output_rate=Decimal("0")
        self.other_profile.max_output_tokens=2048;self.other_profile.version+=1;self.other_profile.save()
        job=self.enqueue(event=self.other_event,owner=self.other)
        self.assertEqual(job.ai_usage.reserved_usd,Decimal("0"))
        self.assertEqual(openai_pilot_summary()["usage_count"],1)


@skipUnless(connection.vendor == "postgresql", "Global pilot reservation races require PostgreSQL")
class OpenAIPilotConcurrentTests(TransactionTestCase):
    def test_two_owners_compete_for_the_same_last_global_budget(self):
        OpenAIPilotLock.objects.get_or_create(pk=1)
        first=owner_fixture("race-first");second=owner_fixture("race-second")
        historical_usage(first[0],first[2],first[3],reserve="0.97",cost="0.97",month=date(2025,1,1))
        barrier=Barrier(2)
        def submit(fixture):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    job=enqueue(event=fixture[3],actor=fixture[0],kind="plan",prompt="Synthetic budget race",idempotency_key=str(uuid.uuid4()))
                    return "reserved",str(job.pk)
                except ValidationError as error:return error.code,None
            finally:close_old_connections()
        with patch("apps.assistant.provider.profile_ready",return_value=True), ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(submit,fixture) for fixture in (first,second)]
            results=[future.result(timeout=20)[0] for future in futures]
        self.assertCountEqual(results,["reserved","openai_pilot_budget"])
        self.assertEqual(openai_pilot_summary()["committed_usd"],Decimal("0.999250"))
