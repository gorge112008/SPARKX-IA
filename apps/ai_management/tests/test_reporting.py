"""Meaningful read-only reporting and comparison tests; no provider calls."""

from copy import deepcopy
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.events.models import Event
from apps.jobs.models import Job
from apps.ai_management.catalog import CATALOG, catalog_entry
from apps.ai_management.models import AIAccount, AIUsage
from apps.ai_management.reporting import (
    MAX_SCENARIO_JOBS, aggregate_usage, compare_scenario, group_usage_by_event,
    group_usage_by_operation, historical_scenario, manual_scenario, owner_usage,
)
from apps.ai_management.services import estimate_cost, profile_snapshot
from apps.ai_management.testing import configure_test_account


class ReportingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="report-owner")
        cls.other = get_user_model().objects.create_user(username="report-other")
        cls.account = configure_test_account(cls.owner)
        cls.other_account = configure_test_account(cls.other)
        cls.event = Event.objects.create(owner=cls.owner, title="Seminario propio", brief="Informe de prueba")
        cls.second = Event.objects.create(owner=cls.owner, title="Taller propio", brief="Otro evento")
        cls.foreign = Event.objects.create(owner=cls.other, title="Evento privado", brief="No exponer")
        cls.snapshot = profile_snapshot(cls.account.active_profile)

    def usage(self, *, event=None, actor=None, account=None, kind="chat", job_status="succeeded",
              status="settled", source="provider", month=date(2026, 11, 1), **extra):
        job = Job.objects.create(
            event=event or self.event, actor=actor or self.owner, kind=kind,
            prompt="Consulta sintética de prueba", base_revision=1, request_hash="0" * 64,
            idempotency_key=str(uuid.uuid4()), status=job_status,
        )
        data = {"job": job, "account": account or self.account, "month": month,
                "snapshot": deepcopy(self.snapshot), "status": status, "accounting_source": source,
                "reserved_input_tokens": 24000, "reserved_output_tokens": 2500,
                "reserved_usd": Decimal("0.029000"), "input_tokens": 1000, "output_tokens": 500,
                "total_tokens": 1500, "cached_tokens": 200, "reasoning_tokens": 50,
                "estimated_cost_usd": Decimal("0.001820")}
        if status != "settled":
            data.update(input_tokens=None, output_tokens=None, total_tokens=None,
                        cached_tokens=None, reasoning_tokens=None, estimated_cost_usd=None)
        return AIUsage.objects.create(**{**data, **extra})

    def bulk_usage(self, count):
        jobs = [Job(event=self.event, actor=self.owner, kind="chat", prompt="Prueba de escala",
                    base_revision=1, request_hash="0" * 64, idempotency_key=str(uuid.uuid4()),
                    status="succeeded") for _ in range(count)]
        Job.objects.bulk_create(jobs)
        AIUsage.objects.bulk_create([
            AIUsage(job=job, account=self.account, month=date(2026, 11, 1), snapshot=self.snapshot,
                    status="settled", accounting_source="provider", reserved_input_tokens=24000,
                    reserved_output_tokens=2500, reserved_usd=Decimal("0.029000"),
                    input_tokens=0, output_tokens=0, total_tokens=0, cached_tokens=0,
                    reasoning_tokens=0, estimated_cost_usd=Decimal("0")) for job in jobs
        ])

    def test_scope_requires_account_owner_event_owner_and_job_actor(self):
        allowed = self.usage()
        self.usage(account=self.other_account)  # Account owner disagrees.
        self.usage(actor=self.other)  # Soliciting actor disagrees.
        self.usage(event=self.foreign)  # Event owner disagrees.
        self.usage(event=self.foreign, actor=self.other, account=self.other_account)
        self.assertEqual(list(owner_usage(self.owner).values_list("id", flat=True)), [allowed.pk])
        self.assertEqual(owner_usage(self.other).count(), 1)

    def test_event_ownership_change_removes_old_owner_visibility(self):
        self.usage()
        Event.objects.filter(pk=self.event.pk).update(owner=self.other)
        self.assertFalse(owner_usage(self.owner).exists())
        self.assertFalse(owner_usage(self.other).exists())

    def test_anonymous_and_empty_accounts_are_read_only_and_empty(self):
        anonymous_rows = owner_usage(AnonymousUser())
        self.assertEqual(aggregate_usage(anonymous_rows)["total_count"], 0)
        third = get_user_model().objects.create_user(username="report-no-account")
        before = AIAccount.objects.count()
        self.assertEqual(aggregate_usage(owner_usage(third))["total_count"], 0)
        self.assertEqual(AIAccount.objects.count(), before)

    def test_filters_use_owner_and_ledger_month_not_created_time(self):
        chosen = self.usage(kind="plan", month=date(2026, 10, 1))
        self.usage(kind="chat", month=date(2026, 10, 1))
        self.usage(kind="plan", event=self.second, month=date(2026, 10, 1))
        self.usage(kind="plan", month=date(2026, 11, 1))
        rows = owner_usage(self.owner, event_id=str(self.event.pk), kind="plan", month="2026-10")
        self.assertEqual(list(rows.values_list("id", flat=True)), [chosen.pk])
        self.assertEqual(owner_usage(self.owner, event_id=self.foreign.pk).count(), 0)

    @override_settings(TIME_ZONE="Asia/Tokyo")
    def test_datetime_month_is_explicitly_lima_even_with_another_ui_timezone(self):
        october = self.usage(month=date(2026, 10, 1))
        self.usage(month=date(2026, 11, 1))
        instant = datetime(2026, 11, 1, 2, tzinfo=datetime_timezone.utc)
        self.assertEqual(list(owner_usage(self.owner, month=instant).values_list("id", flat=True)), [october.pk])

    def test_invalid_filters_raise_before_any_database_query(self):
        cases = ({"month": "2026-13"}, {"month": "2026-1"}, {"month": "0000-01"},
                 {"month": date(2026, 11, 2)}, {"month": datetime(2026, 11, 1)},
                 {"month": True}, {"event_id": "not-a-uuid"}, {"kind": "approve"})
        for case in cases:
            with self.subTest(case=case), self.assertNumQueries(0), self.assertRaises(ValidationError):
                owner_usage(self.owner, **case)

    def test_aggregate_preserves_zero_unknown_released_and_manual_sources(self):
        self.usage(input_tokens=0, output_tokens=0, total_tokens=0, cached_tokens=0,
                   reasoning_tokens=0, estimated_cost_usd=Decimal("0"))
        self.usage(source="manual", estimated_cost_usd=Decimal("0.002000"))
        self.usage(status="uncertain", source="unknown", input_tokens=10)
        self.usage(status="reserved", source="unknown", job_status="queued")
        self.usage(status="dispatched", source="unknown")
        self.usage(status="released", source="unknown", estimated_cost_usd=Decimal("999"))
        with self.assertNumQueries(1):
            summary = aggregate_usage(owner_usage(self.owner))
        self.assertEqual(summary["total_count"], 6)
        self.assertEqual(summary["settled_count"], 2)
        self.assertEqual(summary["known_cost_count"], 2)
        self.assertEqual(summary["unknown_cost_count"], 3)
        self.assertEqual(summary["unknown_usage_count"], 3)
        self.assertEqual(summary["manual_count"], 1)
        self.assertEqual(summary["provider_count"], 1)
        self.assertEqual(summary["released_count"], 1)
        self.assertEqual(summary["historical_cost_usd"], Decimal("0.002000"))
        self.assertEqual(summary["reserved_usd"], Decimal("0.087000"))
        self.assertEqual(summary["used_tokens"], 1500)

    def test_partial_settled_and_unknown_cost_are_not_silently_labelled_zero(self):
        self.usage(input_tokens=None, total_tokens=None, estimated_cost_usd=None)
        summary = aggregate_usage(owner_usage(self.owner))
        self.assertEqual(summary["historical_cost_usd"], Decimal("0"))
        self.assertEqual(summary["known_cost_count"], 0)
        self.assertEqual(summary["unknown_cost_count"], 1)
        self.assertEqual(summary["unknown_usage_count"], 1)
        self.assertEqual(summary["used_tokens"], 0)
        scenario = historical_scenario(owner_usage(self.owner))
        self.assertEqual(scenario["requests"], 0)
        for comparison in compare_scenario(scenario):
            self.assertFalse(comparison["available"])
            self.assertIsNone(comparison["gross"])
            self.assertTrue(comparison["reason"])

    def test_cancelled_and_stale_jobs_still_contribute_their_settled_consumption(self):
        self.usage(job_status="cancelled")
        self.usage(job_status="stale")
        summary = aggregate_usage(owner_usage(self.owner))
        self.assertEqual(summary["settled_count"], 2)
        self.assertEqual(summary["historical_cost_usd"], Decimal("0.003640"))
        self.assertEqual(historical_scenario(owner_usage(self.owner))["requests"], 2)

    def test_groups_have_correct_scope_totals_and_fixed_query_count(self):
        self.usage(kind="chat")
        self.usage(kind="plan", event=self.second, source="manual", estimated_cost_usd=Decimal("0.003000"))
        self.usage(kind="chat", event=self.second, status="released")
        self.usage(event=self.foreign, account=self.other_account, actor=self.other)
        with self.assertNumQueries(2):
            events = group_usage_by_event(owner_usage(self.owner))
            operations = group_usage_by_operation(owner_usage(self.owner))
        self.assertEqual([row["event_title"] for row in events], ["Seminario propio", "Taller propio"])
        self.assertEqual(sum(row["total_count"] for row in events), 3)
        self.assertEqual(sum(row["historical_cost_usd"] for row in events), Decimal("0.004820"))
        by_kind = {row["kind"]: row for row in operations}
        self.assertEqual(by_kind["plan"]["manual_count"], 1)
        self.assertEqual(by_kind["chat"]["released_count"], 1)
        self.assertEqual(by_kind["chat"]["label"], Job.Kind.CHAT.label)

    def test_historical_scenario_retains_zero_manual_and_unknown_cache_without_mutation(self):
        zero = self.usage(input_tokens=0, output_tokens=0, total_tokens=0,
                          cached_tokens=0, reasoning_tokens=0, estimated_cost_usd=Decimal("0"))
        manual = self.usage(source="manual", cached_tokens=None, total_tokens=None)
        self.usage(status="uncertain", input_tokens=1, output_tokens=2, total_tokens=3)
        self.usage(status="released")
        with self.assertNumQueries(1):
            scenario = historical_scenario(owner_usage(self.owner))
        self.assertEqual(scenario["requests"], 2)
        self.assertEqual(scenario["input_tokens"], 1000)
        self.assertEqual(scenario["output_tokens"], 500)
        self.assertEqual(scenario["coverage"]["manual_count"], 1)
        self.assertEqual(scenario["coverage"]["provider_count"], 1)
        self.assertEqual(scenario["coverage"]["cache_unknown_count"], 1)
        self.assertEqual(scenario["coverage"]["derived_total_count"], 1)
        self.assertEqual(scenario["coverage"]["excluded_count"], 2)
        self.assertEqual(scenario["coverage"]["released_count"], 1)
        manual.refresh_from_db()
        zero.refresh_from_db()
        self.assertIsNone(manual.cached_tokens)
        self.assertIsNone(manual.total_tokens)
        self.assertEqual(zero.total_tokens, 0)

    def test_historical_invalid_buckets_and_subcounts_are_excluded_explicitly(self):
        self.usage(input_tokens=None, total_tokens=None)
        self.usage(total_tokens=1501)
        self.usage(cached_tokens=1001)
        self.usage(reasoning_tokens=501)
        self.usage(input_tokens=2_000_000_000, output_tokens=2_000_000_000, total_tokens=None)
        self.usage(source="unknown")
        scenario = historical_scenario(owner_usage(self.owner))
        self.assertEqual(scenario["coverage"]["invalid_count"], 5)
        self.assertEqual(scenario["coverage"]["unknown_source_count"], 1)
        self.assertEqual(scenario["requests"], 1)
        summary = aggregate_usage(owner_usage(self.owner))
        self.assertEqual(summary["known_usage_count"], 1)
        self.assertEqual(summary["unknown_usage_count"], 5)

    def test_historical_known_tokens_with_unknown_historical_cost_remain_explained(self):
        self.usage(estimated_cost_usd=None)
        scenario = historical_scenario(owner_usage(self.owner))
        self.assertEqual(scenario["requests"], 1)
        self.assertEqual(scenario["coverage"]["unknown_cost_count"], 1)
        self.assertTrue(all(row["available"] for row in compare_scenario(scenario)))

    def test_historical_scenario_raises_instead_of_truncating_above_1000(self):
        self.bulk_usage(MAX_SCENARIO_JOBS + 1)
        with self.assertNumQueries(1), self.assertRaises(ValidationError) as caught:
            historical_scenario(owner_usage(self.owner))
        self.assertEqual(caught.exception.code, "scenario_too_large")
        with self.assertNumQueries(1):
            summary = aggregate_usage(owner_usage(self.owner))
        self.assertEqual(summary["total_count"], MAX_SCENARIO_JOBS + 1)
        self.assertEqual(group_usage_by_event(owner_usage(self.owner))[0]["settled_count"], MAX_SCENARIO_JOBS + 1)

    def test_manual_scenario_uses_one_row_for_repetitions_and_preserves_zero(self):
        with self.assertNumQueries(0):
            scenario = manual_scenario(input_tokens=0, output_tokens=0, requests=100000)
            rows = compare_scenario(scenario)
        self.assertEqual(len(scenario["rows"]), 1)
        self.assertEqual(scenario["requests"], 100000)
        self.assertEqual(scenario["coverage"]["declared_count"], 100000)
        self.assertEqual(scenario["coverage"]["manual_count"], 0)  # No historical reconciliation claimed.
        self.assertTrue(all(row["gross"] == 0 and row["available"] for row in rows))

    def test_manual_scenario_rejects_bad_numbers_boolean_cache_and_repetitions(self):
        for values in ({"input_tokens": True}, {"output_tokens": -1}, {"cached_tokens": 101},
                       {"requests": True}, {"requests": 0}, {"requests": 100001}):
            params = {"input_tokens": 100, "output_tokens": 50, **values}
            with self.subTest(values=values), self.assertNumQueries(0), self.assertRaises(ValidationError):
                manual_scenario(**params)

    def test_comparison_preserves_catalogue_order_conditions_and_does_not_apply_credits(self):
        scenario = manual_scenario(input_tokens=1000, output_tokens=500, cached_tokens=200, requests=3)
        original = deepcopy(scenario)
        with self.assertNumQueries(0):
            comparisons = compare_scenario(scenario)
        self.assertEqual([row["code"] for row in comparisons], list(CATALOG))
        self.assertEqual(len(comparisons), len(CATALOG))
        self.assertEqual(scenario, original)
        for row in comparisons:
            self.assertTrue(row["source_url"])
            self.assertTrue(row["verified_on"])
            self.assertTrue(row["condition"])
            self.assertNotIn("after_credits", row)
            self.assertNotIn("best", row)
            self.assertEqual(row["coverage"], scenario["coverage"])

    def test_rounding_is_per_individual_request_before_repetition_or_sum(self):
        scenario = manual_scenario(input_tokens=1, output_tokens=0, requests=2)
        compared = {row["code"]: row for row in compare_scenario(scenario)}
        self.assertEqual(compared["openai_luna"]["gross"], Decimal("0.000002"))
        self.assertEqual(compared["openai_luna"]["per_request"], Decimal("0.000001"))
        combined = estimate_cost(catalog_entry("openai_luna"), input_tokens=2, output_tokens=0)
        self.assertEqual(combined, Decimal("0.000001"))
        self.usage(input_tokens=1, output_tokens=0, total_tokens=1, cached_tokens=0, reasoning_tokens=0)
        self.usage(input_tokens=1, output_tokens=0, total_tokens=1, cached_tokens=0, reasoning_tokens=0)
        compared_history = {row["code"]: row for row in compare_scenario(historical_scenario(owner_usage(self.owner)))}
        self.assertEqual(compared_history["openai_luna"]["gross"], Decimal("0.000002"))

    def test_original_costs_do_not_change_when_current_catalogue_changes(self):
        usage = self.usage()
        original_snapshot = deepcopy(usage.snapshot)
        before = aggregate_usage(owner_usage(self.owner))["historical_cost_usd"]
        entry = {**CATALOG["openai_luna"], "input_rate": "9", "output_rate": "9"}
        with patch.dict(CATALOG, {"openai_luna": entry}):
            summary = aggregate_usage(owner_usage(self.owner))
            compared = {row["code"]: row for row in compare_scenario(historical_scenario(owner_usage(self.owner)))}
        self.assertEqual(summary["historical_cost_usd"], before)
        self.assertEqual(before, Decimal("0.001820"))
        self.assertEqual(compared["openai_luna"]["gross"], Decimal("0.013500"))
        usage.refresh_from_db()
        self.assertEqual(usage.snapshot, original_snapshot)
        self.assertEqual(usage.estimated_cost_usd, before)

    def test_query_count_stays_fixed_for_summary_groups_and_catalogue_comparisons(self):
        for count in (2, 30):
            self.bulk_usage(count)
            with self.subTest(count=count), self.assertNumQueries(4):
                aggregate_usage(owner_usage(self.owner))
                group_usage_by_event(owner_usage(self.owner))
                group_usage_by_operation(owner_usage(self.owner))
                compare_scenario(historical_scenario(owner_usage(self.owner)))

    def test_manual_limits_and_incompatible_historical_requests_are_not_quoted_as_zero(self):
        for values in ((128001, 0), (1, 16001), (128000, 3073)):
            with self.subTest(values=values), self.assertRaises(ValidationError) as caught:
                manual_scenario(input_tokens=values[0], output_tokens=values[1])
            self.assertEqual(caught.exception.code, "scenario_context_limit")
        compatible = manual_scenario(input_tokens=128000, output_tokens=3072)
        self.assertTrue(all(row["available"] for row in compare_scenario(compatible)))
        self.usage(input_tokens=128001, output_tokens=0, total_tokens=128001, cached_tokens=0, reasoning_tokens=0)
        self.usage(input_tokens=1, output_tokens=0, total_tokens=1, cached_tokens=0, reasoning_tokens=0)
        scenario = historical_scenario(owner_usage(self.owner))
        self.assertEqual(scenario["requests"], 2)
        for row in compare_scenario(scenario):
            self.assertFalse(row["available"])
            self.assertIsNone(row["gross"])
            self.assertIsNone(row["per_request"])
            self.assertEqual(row["incompatible_count"], 1)
            self.assertEqual(row["available_count"], 1)
            self.assertTrue(row["reason"])

    def test_luna_comparison_disables_cached_discount_while_mini_and_other_profiles_apply_it(self):
        scenario = manual_scenario(input_tokens=1000, output_tokens=500, cached_tokens=200, requests=2)
        rows = {row["code"]: row for row in compare_scenario(scenario)}
        self.assertEqual(rows["openai_luna"]["cached_tokens_applied"], 0)
        self.assertEqual(rows["openai_luna"]["gross"], Decimal("0.000700"))
        self.assertIn("Sin descuento", rows["openai_luna"]["cache_note"])
        self.assertEqual(rows["openai_54_mini"]["cached_tokens_applied"], 400)
        self.assertEqual(rows["openai_54_mini"]["gross"], Decimal("0.005730"))
        self.assertIn("sin aciertos garantizados", rows["openai_54_mini"]["cache_note"])
        self.assertEqual(rows["groq_paid"]["cached_tokens_applied"], 400)
        self.assertEqual(rows["groq_paid"]["gross"], Decimal("0.000436"))
        self.assertEqual(rows["gemini_paid"]["cached_tokens_applied"], 400)
        self.assertEqual(rows["gemini_paid"]["gross"], Decimal("0.002992"))
