"""Read-only comparison/report HTTP contracts, using synthetic ledger entries."""
from datetime import date, timedelta
from decimal import Decimal
import re
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from apps.jobs.models import Job
from apps.ai_management.catalog import CATALOG
from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.ai_management.services import current_month, profile_snapshot
from apps.ai_management.testing import configure_test_account


@override_settings(OPENAI_API_KEY="reporting-test-key-never-used", OLLAMA_ENABLED=False)
class ReportingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username="report-owner", is_staff=True)
        cls.other = users.objects.create_user(username="report-other", is_staff=True)
        cls.member = users.objects.create_user(username="report-member")
        cls.account = configure_test_account(cls.owner)
        cls.other_account = configure_test_account(cls.other)
        cls.member_account = configure_test_account(cls.member)
        cls.event = Event.objects.create(owner=cls.owner, title="Evento propio", brief="Prueba sintética")
        cls.second_event = Event.objects.create(owner=cls.owner, title="Segundo evento propio", brief="Prueba sintética")
        cls.foreign_event = Event.objects.create(owner=cls.other, title="Evento ajeno confidencial", brief="Prueba sintética")

    def setUp(self):
        self.client.force_login(self.owner)
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("A simulation/report must not call inference"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(self.remote.assert_not_called)

    def url(self, name):
        return reverse("ai_management:" + name)

    def manual(self, **changes):
        data = {"source": "manual", "input_tokens": 1000, "cached_tokens": 400,
                "output_tokens": 300, "requests": 25, "month": ""}
        data.update(changes)
        return data

    def history(self, **changes):
        data = {"source": "history", "event": "", "kind": "", "month": ""}
        data.update(changes)
        return data

    def usage(self, *, event=None, account=None, actor=None, kind=Job.Kind.PLAN, month=None, **changes):
        event, account = event or self.event, account or self.account
        job = Job.objects.create(event=event, actor=actor or event.owner, kind=kind, prompt="Prueba de reporte",
                                 base_revision=event.revision, request_hash="c" * 64,
                                 idempotency_key=str(uuid.uuid4()), status=Job.Status.SUCCEEDED)
        fields = {"job": job, "account": account, "month": month or current_month(),
                  "snapshot": profile_snapshot(account.active_profile), "reserved_input_tokens": 24000,
                  "reserved_output_tokens": 2500, "reserved_usd": Decimal("0.029000"),
                  "status": AIUsage.Status.SETTLED, "accounting_source": AIUsage.AccountingSource.PROVIDER,
                  "input_tokens": 100, "output_tokens": 30, "total_tokens": 130,
                  "cached_tokens": 0, "reasoning_tokens": 0, "estimated_cost_usd": Decimal("0.000160")}
        fields.update(changes)
        return AIUsage.objects.create(**fields)

    def rows(self, response):
        return {row["code"]: row for row in response.context["comparison"]["comparisons"]}

    def state(self):
        return {
            "accounts": list(AIAccount.objects.order_by("id").values()),
            "profiles": list(AIProfile.objects.order_by("id").values()),
            "usage": list(AIUsage.objects.order_by("id").values()),
            "jobs": list(Job.objects.order_by("id").values()),
        }

    def test_comparison_get_and_post_require_login(self):
        self.client.logout()
        for method in (self.client.get, self.client.post):
            response = method(self.url("compare"), self.manual())
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)

    def test_nonstaff_can_simulate_and_read_own_reports_without_spend_permission(self):
        self.client.force_login(self.member)
        for url in (self.url("compare"), self.url("usage")):
            self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(self.url("compare"), self.manual())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account"].owner_id, self.member.pk)

    def test_comparison_requires_csrf_and_valid_token_is_accepted(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url("compare"), self.manual()).status_code, 403)
        self.assertEqual(client.get(self.url("compare")).status_code, 200)
        response = client.post(self.url("compare"), {**self.manual(), "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.rows(response)), len(CATALOG))

    def test_comparison_has_only_read_and_local_post_methods(self):
        self.assertEqual(self.client.put(self.url("compare"), {}).status_code, 405)
        self.assertEqual(self.client.delete(self.url("compare")).status_code, 405)

    def test_manual_compares_catalogue_presets_without_applying_credits_or_posted_tariffs(self):
        response = self.client.post(self.url("compare"), self.manual(
            preset="openai_luna", credits="200", active_profile=self.other_account.active_profile_id,
            provider="ollama", model="untrusted", input_rate=0, output_rate=0, owner=self.other.pk))
        self.assertEqual(response.status_code, 200)
        rows = self.rows(response)
        self.assertEqual(set(rows), set(CATALOG))
        self.assertEqual(rows["openai_luna"]["gross"], Decimal("0.006250"))
        self.assertEqual(rows["openai_54_mini"]["gross"], Decimal("0.045750"))
        self.assertEqual(rows["openai_54_mini"]["cached_tokens_applied"], 400 * 25)
        self.assertContains(response, f"Un escenario, {len(CATALOG)} opciones")
        self.assertEqual(rows["groq_paid"]["gross"], Decimal("0.003750"))
        self.assertEqual(rows["gemini_paid"]["gross"], Decimal("0.023550"))
        for key in ("groq_free", "gemini_free", "ollama_local"):
            self.assertEqual(rows[key]["gross"], 0)
        for row in rows.values():
            self.assertNotIn("after_credits", row)
            self.assertNotIn("credits", row)
        self.assertEqual(rows["openai_luna"]["cached_tokens_applied"], 0)
        self.assertEqual(rows["groq_paid"]["cached_tokens_applied"], 400 * 25)

    def test_comparison_and_read_reports_do_not_modify_ledger_or_active_budget(self):
        self.usage()
        before = self.state()
        self.assertEqual(self.client.post(self.url("compare"), self.manual()).status_code, 200)
        self.assertEqual(self.client.post(self.url("compare"), self.history()).status_code, 200)
        self.assertEqual(self.client.get(self.url("usage"), {"month": ""}).status_code, 200)
        self.assertEqual(self.state(), before)

    def test_credits_only_apply_to_single_provider_calculator_and_never_comparison(self):
        quote = self.client.post(self.url("calculator"), {"preset": "groq_paid", "input_tokens": 1000,
            "cached_tokens": 400, "output_tokens": 300, "requests": 25, "credits": "200"})
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(quote.context["quote"]["after_credits"], 0)
        comparison = self.client.post(self.url("compare"), self.manual(credits="200"))
        rows = self.rows(comparison)
        self.assertEqual(rows["groq_paid"]["gross"], Decimal("0.003750"))
        self.assertEqual(rows["openai_luna"]["gross"], Decimal("0.006250"))

    def test_openai_calculator_uses_full_input_without_cache_discount(self):
        response = self.client.post(self.url("calculator"), {"preset": "openai_luna", "input_tokens": 1000,
            "cached_tokens": 400, "output_tokens": 300, "requests": 1, "credits": 0})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["quote"]["cache_disabled"])
        self.assertEqual(response.context["quote"]["per_request"], Decimal("0.000250"))

    def test_mini_calculator_applies_declared_cache_subset_without_claiming_free_usage(self):
        before = self.state()
        response = self.client.post(self.url("calculator"), {
            "preset": "openai_54_mini", "input_tokens": 1000, "cached_tokens": 400,
            "output_tokens": 300, "requests": 25, "credits": 0,
        })
        self.assertEqual(response.status_code, 200)
        quote = response.context["quote"]
        self.assertFalse(quote["cache_disabled"])
        self.assertEqual(quote["per_request"], Decimal("0.001830"))
        self.assertEqual(quote["gross"], Decimal("0.045750"))
        self.assertEqual(quote["tokens"], 32500)
        self.assertContains(response, "sin aciertos garantizados")
        self.assertContains(response, "el exceso puede consumir saldo")
        self.assertNotContains(response, "La integración OpenAI usa caché desactivada")
        self.assertEqual(self.state(), before)

    def test_manual_required_numbers_and_context_limits_fail_locally(self):
        cases = [{"input_tokens": ""}, {"output_tokens": ""}, {"requests": ""}, {"requests": 0},
                 {"requests": 100001}, {"input_tokens": 128001}, {"output_tokens": 16001},
                 {"input_tokens": 128000, "output_tokens": 16000}, {"cached_tokens": 1001},
                 {"input_tokens": -1}, {"output_tokens": "NaN"}, {"source": "unknown"}]
        before = self.state()
        for changes in cases:
            with self.subTest(changes=changes):
                response = self.client.post(self.url("compare"), self.manual(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["form"].errors)
                self.assertIsNone(response.context["comparison"])
        self.assertEqual(self.state(), before)

    def test_manual_explicit_zero_scenario_can_be_quoted(self):
        response = self.client.post(self.url("compare"), self.manual(input_tokens=0, cached_tokens=0, output_tokens=0, requests=1))
        self.assertEqual(response.status_code, 200)
        for row in self.rows(response).values():
            self.assertTrue(row["available"])
            self.assertEqual(row["gross"], 0)

    def test_foreign_event_id_is_404_even_when_manual_scenario_does_not_use_it(self):
        event_id = str(self.foreign_event.pk)
        targets = [(self.client.get, self.url("usage"), {"event": event_id}),
                   (self.client.get, self.url("compare"), {"event": event_id}),
                   (self.client.post, self.url("compare"), self.manual(event=event_id)),
                   (self.client.post, self.url("compare"), self.history(event=event_id))]
        for method, url, data in targets:
            with self.subTest(url=url, data=data):
                self.assertEqual(method(url, data).status_code, 404)

    def test_nonexistent_event_does_not_turn_into_all_events(self):
        event_id = str(uuid.uuid4())
        self.assertEqual(self.client.get(self.url("usage"), {"event": event_id}).status_code, 404)
        self.assertEqual(self.client.post(self.url("compare"), self.history(event=event_id)).status_code, 404)

    def test_malformed_filters_are_rejected_without_unfiltered_results(self):
        self.usage()
        for params in ({"event": "not-a-uuid"}, {"kind": "admin"}, {"month": "2026-13"},
                       {"month": "2026-1"}, {"month": "1899-12"}, {"month": "2101-01"}):
            with self.subTest(params=params):
                usage = self.client.get(self.url("usage"), params)
                self.assertEqual(usage.status_code, 400)
                self.assertIsNone(usage.context["usage_page"])
                comparison = self.client.post(self.url("compare"), self.history(**params))
                self.assertEqual(comparison.status_code, 400)
                self.assertIsNone(comparison.context["comparison"])

    def test_usage_filters_intersect_event_action_and_accounting_month(self):
        period = current_month()
        previous = date(period.year - 1, 12, 1) if period.month == 1 else date(period.year, period.month - 1, 1)
        selected = self.usage()
        self.usage(kind=Job.Kind.CHAT)
        self.usage(event=self.second_event)
        self.usage(month=previous)
        self.usage(event=self.foreign_event, account=self.other_account)
        response = self.client.get(self.url("usage"), {"event": self.event.pk, "kind": "plan", "month": period.strftime("%Y-%m")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item.pk for item in response.context["usage_page"]], [selected.pk])
        self.assertEqual(response.context["analysis_summary"]["total_count"], 1)
        self.assertEqual(response.context["selected_event"].pk, self.event.pk)
        self.assertEqual(response.context["event_groups"][0]["event_id"], self.event.pk)
        self.assertEqual(response.context["operation_groups"][0]["kind"], "plan")

    def test_usage_default_month_and_explicit_all_months_are_distinct(self):
        period = current_month()
        previous = date(period.year - 1, 12, 1) if period.month == 1 else date(period.year, period.month - 1, 1)
        self.usage()
        self.usage(month=previous)
        current = self.client.get(self.url("usage"))
        all_months = self.client.get(self.url("usage"), {"month": ""})
        self.assertEqual(current.context["analysis_summary"]["total_count"], 1)
        self.assertEqual(all_months.context["analysis_summary"]["total_count"], 2)

    def test_owner_scope_checks_actor_and_event_as_well_as_account(self):
        selected = self.usage()
        self.usage(event=self.foreign_event, account=self.account, actor=self.owner)
        self.usage(event=self.event, account=self.account, actor=self.other)
        self.usage(event=self.foreign_event, account=self.other_account)
        response = self.client.get(self.url("usage"), {"month": ""})
        self.assertEqual([item.pk for item in response.context["usage_page"]], [selected.pk])
        self.assertNotContains(response, self.foreign_event.title)
        historical = self.client.post(self.url("compare"), self.history())
        self.assertEqual(historical.context["comparison"]["scenario"]["requests"], 1)

    def test_event_selectors_expose_only_owned_events(self):
        response = self.client.get(self.url("usage"))
        choices = dict(response.context["filter_form"].fields["event"].widget.choices)
        self.assertIn(str(self.event.pk), choices)
        self.assertNotIn(str(self.foreign_event.pk), choices)
        preselected = self.client.get(self.url("compare"), {"event": self.event.pk})
        self.assertEqual(preselected.status_code, 200)
        self.assertEqual(preselected.context["form"].initial["source"], "history")

    def test_history_navigation_preserves_action_month_and_source_before_post(self):
        for event_id in ("", str(self.event.pk)):
            with self.subTest(event_id=event_id):
                response = self.client.get(self.url("compare"), {
                    "source": "history", "kind": "chat", "month": "2026-10", "event": event_id,
                })
                self.assertEqual(response.status_code, 200)
                initial = response.context["form"].initial
                self.assertEqual(initial.get("source"), "history")
                self.assertEqual(initial.get("kind"), "chat")
                self.assertEqual(initial.get("month"), "2026-10")

    def test_invalid_get_deep_links_are_400_without_quote_or_foreign_data(self):
        cases = ({"source": "unknown"}, {"kind": "admin"}, {"month": "2026-13"},
                 {"month": "1899-12"}, {"event": "malformed-uuid"},
                 {"pen_rate": "NaN"}, {"pen_rate": "Infinity"}, {"pen_rate": "3.75"},
                 {"pen_rate": "3.75", "pen_date": (timezone.localdate() + timedelta(days=1)).isoformat(), "pen_source": "Manual"})
        before = self.state()
        for params in cases:
            with self.subTest(params=params):
                response = self.client.get(self.url("compare"), params)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["form"].errors)
                self.assertIsNone(response.context["comparison"])
                self.assertNotContains(response, self.foreign_event.title, status_code=400)
                self.assertNotContains(response, "reporting-test-key-never-used", status_code=400)
        self.assertEqual(self.state(), before)

    def test_valid_get_prepares_form_without_calculating_or_mutating(self):
        before = self.state()
        cases = ({}, {"source": "history", "kind": "chat", "event": str(self.event.pk), "month": ""},
                 {"pen_rate": "3.75", "pen_date": timezone.localdate().isoformat(), "pen_source": "Manual"})
        with patch("apps.ai_management.reporting.compare_scenario", side_effect=AssertionError("GET must not calculate")):
            for params in cases:
                with self.subTest(params=params):
                    response = self.client.get(self.url("compare"), params)
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.context["form"].errors)
                    self.assertIsNone(response.context["comparison"])
        self.assertEqual(self.state(), before)

    def test_history_comparison_keeps_ledger_money_separate_from_new_tariffs(self):
        self.usage(estimated_cost_usd=Decimal("1.250000"), input_tokens=1000, output_tokens=300, total_tokens=1300, cached_tokens=400)
        response = self.client.post(self.url("compare"), self.history(event=str(self.event.pk), kind="plan"))
        comparison = response.context["comparison"]
        self.assertEqual(comparison["historical"]["historical_cost_usd"], Decimal("1.250000"))
        self.assertEqual(self.rows(response)["openai_luna"]["gross"], Decimal("0.000250"))
        self.assertEqual(self.rows(response)["groq_paid"]["gross"], Decimal("0.000150"))

    def test_historical_comparison_rounds_each_request_before_summing(self):
        for _ in range(2):
            self.usage(input_tokens=1, output_tokens=0, total_tokens=1)
        response = self.client.post(self.url("compare"), self.history())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["comparison"]["scenario"]["requests"], 2)
        self.assertEqual(self.rows(response)["openai_luna"]["gross"], Decimal("0.000002"))

    def test_history_explicit_coverage_excludes_unknown_and_released_records(self):
        self.usage()
        for status in (AIUsage.Status.UNCERTAIN, AIUsage.Status.RELEASED):
            self.usage(status=status, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=None,
                       accounting_source=AIUsage.AccountingSource.UNKNOWN)
        response = self.client.post(self.url("compare"), self.history())
        coverage = response.context["comparison"]["scenario"]["coverage"]
        self.assertEqual(coverage["total_count"], 3)
        self.assertEqual(coverage["included_count"], 1)
        self.assertEqual(coverage["excluded_count"], 2)
        self.assertEqual(coverage["not_settled_count"], 2)
        self.assertEqual(coverage["released_count"], 1)
        self.assertEqual(response.context["comparison"]["historical"]["unknown_cost_count"], 1)

    def test_historical_zero_subtotal_warns_that_another_cost_is_unknown(self):
        self.usage(estimated_cost_usd=Decimal("0"))
        self.usage(estimated_cost_usd=None)
        response = self.client.post(self.url("compare"), self.history())
        self.assertEqual(response.status_code, 200)
        historical = response.context["comparison"]["historical"]
        self.assertEqual(historical["known_cost_count"], 1)
        self.assertEqual(historical["historical_cost_usd"], 0)
        self.assertEqual(historical["unknown_cost_count"], 1)
        self.assertContains(response, "Subtotal de 1")
        self.assertContains(response, "1 todavía sin determinar")

    def test_no_complete_history_means_unquotable_including_free_presets(self):
        self.usage(status=AIUsage.Status.UNCERTAIN, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=None)
        response = self.client.post(self.url("compare"), self.history())
        for row in self.rows(response).values():
            self.assertFalse(row["available"])
            self.assertIsNone(row["gross"])
            self.assertTrue(row["reason"])

    def test_historical_context_too_large_is_not_presented_as_zero_cost(self):
        self.usage(input_tokens=129000, output_tokens=0, total_tokens=129000)
        response = self.client.post(self.url("compare"), self.history())
        for row in self.rows(response).values():
            self.assertFalse(row["available"])
            self.assertIsNone(row["gross"])
            self.assertEqual(row["incompatible_count"], 1)

    def test_manual_and_provider_accounting_sources_stay_separate_in_history(self):
        self.usage(accounting_source=AIUsage.AccountingSource.MANUAL)
        self.usage(accounting_source=AIUsage.AccountingSource.PROVIDER)
        response = self.client.post(self.url("compare"), self.history())
        coverage = response.context["comparison"]["scenario"]["coverage"]
        self.assertEqual(coverage["manual_count"], 1)
        self.assertEqual(coverage["provider_count"], 1)

    def test_pen_conversion_is_optional_and_usd_remains_authoritative(self):
        baseline = self.client.post(self.url("compare"), self.manual())
        self.assertIsNone(baseline.context["comparison"]["conversion"])
        before = self.state()
        response = self.client.post(self.url("compare"), self.manual(pen_rate="3.750000",
            pen_date=timezone.localdate().isoformat(), pen_source="Consulta manual de prueba"))
        self.assertEqual(response.status_code, 200)
        conversion = response.context["comparison"]["conversion"]
        self.assertEqual(conversion["rate"], Decimal("3.750000"))
        rows = self.rows(response)
        self.assertEqual(rows["openai_luna"]["gross"], Decimal("0.006250"))
        self.assertEqual(rows["openai_luna"]["gross_pen"], Decimal("0.023438"))
        self.assertEqual(self.state(), before)

    def test_pen_rate_is_finite_positive_bounded_and_dated(self):
        date_string = timezone.localdate().isoformat()
        for rate in ("NaN", "Infinity", "-Infinity", "0", "-1", "10000.000001", "0.0000001", "1e100"):
            with self.subTest(rate=rate):
                response = self.client.post(self.url("compare"), self.manual(pen_rate=rate, pen_date=date_string, pen_source="Manual"))
                self.assertEqual(response.status_code, 400)
                self.assertIn("pen_rate", response.context["form"].errors)
                self.assertIsNone(response.context["comparison"])

    def test_partial_pen_conversion_requires_rate_date_and_source(self):
        for fields in ({"pen_rate": "3.75"}, {"pen_date": timezone.localdate().isoformat()}, {"pen_source": "Manual"}):
            with self.subTest(fields=fields):
                response = self.client.post(self.url("compare"), self.manual(**fields))
                self.assertEqual(response.status_code, 400)
                self.assertIsNone(response.context["comparison"])

    def test_pen_conversion_rejects_future_date_and_overlong_source(self):
        for changes, field in (({"pen_date": (timezone.localdate() + timedelta(days=1)).isoformat()}, "pen_date"),
                               ({"pen_source": "a" * 121}, "pen_source")):
            data = {"pen_rate": "3.75", "pen_date": timezone.localdate().isoformat(), "pen_source": "Manual", **changes}
            with self.subTest(changes=changes):
                response = self.client.post(self.url("compare"), self.manual(**data))
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context["form"].errors)

    def test_pen_source_is_escaped_text_and_never_fetched(self):
        source = '<img src=x onerror="alert(1)">'
        response = self.client.post(self.url("compare"), self.manual(pen_rate="3.75",
            pen_date=timezone.localdate().isoformat(), pen_source=source))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;img")
        self.assertNotContains(response, source)
        self.assertNotContains(response, "reporting-test-key-never-used")

    def test_reporting_html_keeps_unknown_cost_distinct_from_explicit_zero(self):
        unknown_event = Event.objects.create(owner=self.owner, title="Tokens desconocidos", brief="Prueba")
        zero_event = Event.objects.create(owner=self.owner, title="Tokens cero", brief="Prueba")
        self.usage(event=unknown_event, status=AIUsage.Status.UNCERTAIN, input_tokens=None,
                   output_tokens=None, total_tokens=None, estimated_cost_usd=None)
        self.usage(event=zero_event, input_tokens=0, output_tokens=0, total_tokens=0, estimated_cost_usd=0)
        response = self.client.get(self.url("usage"), {"month": ""})
        self.assertEqual(response.context["analysis_summary"]["unknown_usage_count"], 1)
        rows = re.findall(r"<tr>(.*?)</tr>", response.content.decode(), re.S)
        unknown = next(row for row in rows if "Tokens desconocidos" in row and "Desconocida" in row)
        zero = next(row for row in rows if "Tokens cero" in row and "Total:" in row)
        self.assertIn("Sin determinar", unknown)
        self.assertRegex(re.sub(r"<[^>]*>", " ", zero), r"\b0\s*/\s*0\b")
