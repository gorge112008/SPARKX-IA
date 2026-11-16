"""HTTP permissions, forms and accounting presentation; no remote inference."""
from decimal import Decimal
import re
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.events.models import Event
from apps.jobs.models import Job
from apps.ai_management.catalog import catalog_entry
from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.ai_management.services import current_month, profile_snapshot
from apps.ai_management.testing import configure_test_account


@override_settings(OPENAI_API_KEY="http-only-test-secret", GROQ_API_KEY="groq-http-only-secret",
                   GEMINI_API_KEY="gemini-http-only-secret", OLLAMA_ENABLED=False)
class AIManagementViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username="ai-admin-http", is_staff=True, is_superuser=True)
        cls.other = users.objects.create_user(username="ai-other-admin-http", is_staff=True, is_superuser=True)
        cls.member = users.objects.create_user(username="ai-member-http")
        cls.account = configure_test_account(cls.owner)
        cls.other_account = configure_test_account(cls.other)
        cls.member_account = configure_test_account(cls.member)
        cls.profile = cls.account.active_profile
        cls.other_profile = cls.other_account.active_profile

    def setUp(self):
        self.client.force_login(self.owner)
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("An HTTP management page must never call an AI provider"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(self.remote.assert_not_called)

    def url(self, name, **kwargs):
        return reverse("ai_management:" + name, kwargs=kwargs or None)

    def profile_data(self, **changes):
        result = {"name": "Perfil HTTP", "preset": "openai_luna", "enabled": "on",
                  "max_input_tokens": 24000, "max_output_tokens": 2500, "expected_version": 0}
        result.update(changes)
        return result

    def budget_data(self, **changes):
        result = {"active_profile": self.profile.pk, "monthly_budget_usd": "5.000000",
                  "monthly_token_limit": 100000, "paid_enabled": "on", "expected_version": self.account.version}
        result.update(changes)
        return result

    def calculator_data(self, **changes):
        result = {"preset": "openai_luna", "input_tokens": 1000, "cached_tokens": 400,
                  "output_tokens": 300, "requests": 25, "credits": "0.002000"}
        result.update(changes)
        return result

    def reconciliation_data(self, **changes):
        result = {"input_tokens": 100, "cached_tokens": 20, "output_tokens": 30,
                  "reasoning_tokens": 10, "note": "Panel de prueba: comprobación externa declarada."}
        result.update(changes)
        return result

    def make_usage(self, *, owner=None, account=None, title="Consumo HTTP", **changes):
        owner, account = owner or self.owner, account or self.account
        event = Event.objects.create(owner=owner, title=title, brief="Datos sintéticos de una prueba HTTP")
        job = Job.objects.create(event=event, actor=owner, kind=Job.Kind.CHAT, prompt="Solicitud sintética",
                                 base_revision=event.revision, request_hash="a" * 64,
                                 idempotency_key=str(uuid.uuid4()), status=Job.Status.FAILED)
        fields = {"job": job, "account": account, "month": current_month(),
                  "snapshot": profile_snapshot(account.active_profile), "reserved_input_tokens": 24000,
                  "reserved_output_tokens": 2500, "reserved_usd": Decimal("0.029000"),
                  "dispatch_token": uuid.uuid4(), "status": AIUsage.Status.UNCERTAIN}
        fields.update(changes)
        return AIUsage.objects.create(**fields)

    def test_every_management_surface_requires_login(self):
        item = self.make_usage()
        self.client.logout()
        urls = [self.url(name) for name in ("index", "providers", "budget", "calculator", "usage", "profile_create")]
        urls += [self.url("profile_edit", profile_id=self.profile.pk), self.url("reconcile", usage_id=item.pk)]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login") + "?next=", response.url)

    def test_member_can_read_own_summary_providers_usage_and_calculator(self):
        self.client.force_login(self.member)
        for name in ("index", "providers", "usage", "calculator"):
            with self.subTest(name=name):
                response = self.client.get(self.url(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["account"].owner_id, self.member.pk)

    def test_configuration_and_reconciliation_require_superuser_for_get_and_post(self):
        item = self.make_usage(owner=self.member, account=self.member_account)
        self.client.force_login(self.member)
        targets = [(self.url("budget"), self.budget_data()),
                   (self.url("profile_create"), self.profile_data()),
                   (self.url("profile_edit", profile_id=self.member_account.active_profile_id), self.profile_data(expected_version=1)),
                   (self.url("reconcile", usage_id=item.pk), self.reconciliation_data())]
        before = AIProfile.objects.count()
        for url, data in targets:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(AIProfile.objects.count(), before)
        item.refresh_from_db()
        self.assertEqual(item.status, AIUsage.Status.UNCERTAIN)

    def test_superuser_can_configure_even_without_staff_flag(self):
        self.owner.is_staff = False
        self.owner.is_superuser = True
        self.owner.save(update_fields=["is_staff", "is_superuser"])
        self.assertEqual(self.client.get(self.url("budget")).status_code, 200)

    def test_foreign_profile_and_reconciliation_are_404_for_superuser(self):
        item = self.make_usage(owner=self.other, account=self.other_account)
        targets = [(self.url("profile_edit", profile_id=self.other_profile.pk), self.profile_data(expected_version=1)),
                   (self.url("reconcile", usage_id=item.pk), self.reconciliation_data())]
        for url, data in targets:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, data).status_code, 404)
        item.refresh_from_db()
        self.assertIsNone(item.reconciled_by_id)

    def test_missing_profile_and_usage_are_404(self):
        self.assertEqual(self.client.get(self.url("profile_edit", profile_id=999999)).status_code, 404)
        self.assertEqual(self.client.get(self.url("reconcile", usage_id=999999)).status_code, 404)

    def test_unsupported_methods_do_not_mutate(self):
        item = self.make_usage()
        for name in ("index", "providers", "usage"):
            with self.subTest(name=name):
                self.assertEqual(self.client.post(self.url(name)).status_code, 405)
        for url in (self.url("budget"), self.url("calculator"), self.url("profile_create"), self.url("reconcile", usage_id=item.pk)):
            with self.subTest(url=url):
                self.assertEqual(self.client.put(url, {}).status_code, 405)

    def test_all_mutations_require_csrf_including_calculator(self):
        item = self.make_usage()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        targets = [(self.url("budget"), self.budget_data()), (self.url("profile_create"), self.profile_data()),
                   (self.url("profile_edit", profile_id=self.profile.pk), self.profile_data(expected_version=1)),
                   (self.url("reconcile", usage_id=item.pk), self.reconciliation_data()),
                   (self.url("calculator"), self.calculator_data())]
        for url, data in targets:
            with self.subTest(url=url):
                self.assertEqual(client.post(url, data).status_code, 403)

    def test_valid_csrf_token_allows_local_calculation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        page = client.get(self.url("calculator"))
        self.assertEqual(page.status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post(self.url("calculator"), {**self.calculator_data(), "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["quote"])

    def test_calculator_handles_cache_subset_credit_and_request_count(self):
        response = self.client.post(self.url("calculator"), self.calculator_data(preset="groq_paid"))
        self.assertEqual(response.status_code, 200)
        quote = response.context["quote"]
        self.assertEqual(quote["per_request"], Decimal("0.000150"))
        self.assertEqual(quote["gross"], Decimal("0.003750"))
        self.assertEqual(quote["after_credits"], Decimal("0.001750"))
        self.assertEqual(quote["tokens"], (1000 + 300) * 25)

    def test_calculator_does_not_modify_balance_profile_job_or_usage(self):
        before = (AIAccount.objects.values().get(pk=self.account.pk), AIProfile.objects.count(),
                  Job.objects.count(), AIUsage.objects.count())
        response = self.client.post(self.url("calculator"), self.calculator_data(credits="200"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["quote"]["after_credits"], 0)
        self.assertEqual(AIAccount.objects.values().get(pk=self.account.pk), before[0])
        self.assertEqual((AIProfile.objects.count(), Job.objects.count(), AIUsage.objects.count()), before[1:])

    def test_free_and_local_calculation_are_zero_without_claiming_real_usage(self):
        for preset in ("groq_free", "gemini_free", "ollama_local"):
            with self.subTest(preset=preset):
                response = self.client.post(self.url("calculator"), self.calculator_data(preset=preset, credits=0))
                self.assertEqual(response.status_code, 200)
                quote = response.context["quote"]
                self.assertEqual(quote["per_request"], 0)
                self.assertEqual(quote["gross"], 0)
                self.assertEqual(quote["after_credits"], 0)
                self.assertGreater(quote["tokens"], 0)
        self.assertFalse(AIUsage.objects.exists())

    def test_calculator_rejects_invalid_subsets_and_bounds(self):
        for changes, field in (({"cached_tokens": 1001}, "cached_tokens"), ({"input_tokens": -1}, "input_tokens"),
                               ({"output_tokens": "NaN"}, "output_tokens"), ({"requests": 0}, "requests"),
                               ({"credits": "-1"}, "credits"), ({"preset": "https://evil.invalid"}, "preset")):
            with self.subTest(changes=changes):
                response = self.client.post(self.url("calculator"), self.calculator_data(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context["form"].errors)
                self.assertIsNone(response.context["quote"])
        self.assertFalse(AIUsage.objects.exists())

    def test_calculator_ignores_posted_rates_model_endpoint_and_key(self):
        response = self.client.post(self.url("calculator"), self.calculator_data(
            input_rate="999", cached_rate="999", output_rate="999", provider="ollama", model="attacker-model",
            api_key="posted-secret-must-not-render", endpoint="https://evil.invalid/"))
        self.assertEqual(response.status_code, 200)
        quote = response.context["quote"]
        self.assertEqual(quote["per_request"], Decimal("0.000250"))
        self.assertTrue(quote["cache_disabled"])
        self.assertEqual(quote["profile"]["provider"], "openai")
        self.assertEqual(quote["profile"]["model"], "gpt-6-luna")
        self.assertNotContains(response, "posted-secret-must-not-render")
        self.assertNotContains(response, "evil.invalid")

    def test_create_profile_takes_tariffs_model_and_owner_from_server(self):
        response = self.client.post(self.url("profile_create"), self.profile_data(
            preset="groq_paid", owner=self.other.pk, provider="gemini", model="attacker-model", mode="free",
            input_rate="0", cached_rate="0", output_rate="0", version=999,
            api_key="posted-secret-must-not-render", source_url="https://evil.invalid/"))
        self.assertRedirects(response, self.url("providers"), fetch_redirect_response=False)
        item = AIProfile.objects.get(owner=self.owner, name="Perfil HTTP")
        expected = catalog_entry("groq_paid")
        for field in ("provider", "model", "mode", "input_rate", "cached_rate", "output_rate", "source_url", "verified_on"):
            self.assertEqual(getattr(item, field), expected[field])
        self.assertEqual(item.version, 1)
        self.assertEqual(item.owner_id, self.owner.pk)
        listing = self.client.get(self.url("providers"))
        self.assertNotContains(listing, "posted-secret-must-not-render")
        self.assertNotContains(listing, "evil.invalid")

    def test_enabled_free_profile_requires_explicit_confirmation(self):
        for preset in ("groq_free", "gemini_free"):
            with self.subTest(preset=preset):
                response = self.client.post(self.url("profile_create"), self.profile_data(preset=preset))
                self.assertEqual(response.status_code, 400)
                self.assertIn("free_tier_confirmed", response.context["form"].errors)
        self.assertFalse(AIProfile.objects.filter(owner=self.owner, mode="free").exists())

    def test_confirmed_free_profile_can_be_saved_without_spend_or_network(self):
        response = self.client.post(self.url("profile_create"), self.profile_data(preset="groq_free", free_tier_confirmed="on"))
        self.assertEqual(response.status_code, 302)
        item = AIProfile.objects.get(owner=self.owner, name="Perfil HTTP")
        self.assertTrue(item.free_tier_confirmed)
        self.assertEqual(item.mode, "free")
        self.assertEqual((item.input_rate, item.cached_rate, item.output_rate), (0, 0, 0))
        self.assertFalse(AIUsage.objects.exists())

    def test_unconfirmed_free_profile_can_only_be_saved_disabled(self):
        data = self.profile_data(preset="gemini_free")
        del data["enabled"]
        response = self.client.post(self.url("profile_create"), data)
        self.assertEqual(response.status_code, 302)
        item = AIProfile.objects.get(owner=self.owner, name="Perfil HTTP")
        self.assertFalse(item.enabled)
        self.assertFalse(item.free_tier_confirmed)

    def test_profile_edit_uses_version_cas_and_preserves_current_value(self):
        url = self.url("profile_edit", profile_id=self.profile.pk)
        first = self.client.post(url, self.profile_data(name="Nombre actualizado", expected_version=1))
        self.assertEqual(first.status_code, 302)
        second = self.client.post(url, self.profile_data(name="Valor obsoleto", expected_version=1))
        self.assertEqual(second.status_code, 400)
        self.assertTrue(second.context["form"].non_field_errors())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.version, 2)
        self.assertEqual(self.profile.name, "Nombre actualizado")

    def test_budget_selects_owned_profile_and_increments_server_version(self):
        response = self.client.post(self.url("budget"), self.budget_data(owner=self.other.pk, version=999))
        self.assertRedirects(response, self.url("index"), fetch_redirect_response=False)
        self.account.refresh_from_db()
        self.assertEqual(self.account.owner_id, self.owner.pk)
        self.assertEqual(self.account.active_profile_id, self.profile.pk)
        self.assertEqual(self.account.version, 2)
        self.assertEqual(self.account.monthly_budget_usd, Decimal("5.000000"))
        self.assertFalse(AIUsage.objects.exists())

    def test_budget_stale_version_does_not_overwrite_current_limits(self):
        data = self.budget_data()
        self.assertEqual(self.client.post(self.url("budget"), data).status_code, 302)
        stale = self.client.post(self.url("budget"), {**data, "monthly_budget_usd": "999"})
        self.assertEqual(stale.status_code, 400)
        self.assertTrue(stale.context["form"].non_field_errors())
        self.account.refresh_from_db()
        self.assertEqual(self.account.monthly_budget_usd, Decimal("5.000000"))
        self.assertEqual(self.account.version, 2)

    def test_budget_cannot_activate_foreign_or_disabled_profile(self):
        self.profile.enabled = False
        self.profile.save(update_fields=["enabled"])
        for profile_id in (self.other_profile.pk, self.profile.pk):
            with self.subTest(profile_id=profile_id):
                response = self.client.post(self.url("budget"), self.budget_data(active_profile=profile_id))
                self.assertEqual(response.status_code, 400)
                self.assertIn("active_profile", response.context["form"].errors)
        self.account.refresh_from_db()
        self.assertEqual(self.account.version, 1)

    def test_paid_permission_requires_positive_budget(self):
        response = self.client.post(self.url("budget"), self.budget_data(monthly_budget_usd=0))
        self.assertEqual(response.status_code, 400)
        self.assertIn("monthly_budget_usd", response.context["form"].errors)

    def test_budget_can_disable_ai_and_paid_authorization_at_zero_cost(self):
        data = self.budget_data(active_profile="", monthly_budget_usd=0, monthly_token_limit=0)
        del data["paid_enabled"]
        self.assertEqual(self.client.post(self.url("budget"), data).status_code, 302)
        self.account.refresh_from_db()
        self.assertIsNone(self.account.active_profile_id)
        self.assertFalse(self.account.paid_enabled)
        self.assertEqual(self.account.monthly_budget_usd, 0)

    def test_usage_listing_and_summary_do_not_include_other_owner_data(self):
        own = self.make_usage(title="Consumo propio visible")
        self.make_usage(owner=self.other, account=self.other_account, title="Consumo ajeno reservado")
        response = self.client.get(self.url("usage"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item.pk for item in response.context["usage_page"]], [own.pk])
        self.assertContains(response, "Consumo propio visible")
        self.assertNotContains(response, "Consumo ajeno reservado")
        home = self.client.get(self.url("index"))
        self.assertEqual(home.context["summary"]["usage_count"], 1)
        self.assertEqual(home.context["summary"]["uncertain_count"], 1)

    def test_usage_context_keeps_unknown_tokens_distinct_from_observed_zero(self):
        unknown = self.make_usage(title="Consumo desconocido")
        zero = self.make_usage(title="Consumo cero", status=AIUsage.Status.SETTLED,
                               input_tokens=0, output_tokens=0, total_tokens=0, estimated_cost_usd=0,
                               accounting_source=AIUsage.AccountingSource.PROVIDER)
        response = self.client.get(self.url("usage"))
        rows = {item.pk: item for item in response.context["usage_page"]}
        self.assertIsNone(rows[unknown.pk].input_tokens)
        self.assertIsNone(rows[unknown.pk].output_tokens)
        self.assertIsNone(rows[unknown.pk].estimated_cost_usd)
        self.assertEqual(rows[zero.pk].input_tokens, 0)
        self.assertEqual(rows[zero.pk].output_tokens, 0)
        self.assertEqual(rows[zero.pk].estimated_cost_usd, 0)
        rendered = re.findall(r"<tr>(.*?)</tr>", response.content.decode(), re.S)
        unknown_row = next(row for row in rendered if "Consumo desconocido" in row and "Total:" in row)
        zero_row = next(row for row in rendered if "Consumo cero" in row and "Total:" in row)
        unknown_cells = re.findall(r"<td[^>]*>(.*?)</td>", unknown_row, re.S)
        zero_cells = re.findall(r"<td[^>]*>(.*?)</td>", zero_row, re.S)
        self.assertIn("Desconocida", unknown_cells[3])
        self.assertIn("Sin determinar", unknown_cells[4])
        self.assertRegex(re.sub(r"<[^>]*>", " ", zero_cells[3]), r"\b0\s*/\s*0\b")
        self.assertNotIn("Desconocida", zero_cells[3])
        self.assertNotIn("Sin determinar", zero_cells[4])

    def test_manual_reconciliation_records_actor_source_time_and_snapshot(self):
        item = self.make_usage()
        data = self.reconciliation_data(actor=self.other.pk, accounting_source="provider", estimated_cost_usd=0)
        response = self.client.post(self.url("reconcile", usage_id=item.pk), data)
        self.assertRedirects(response, self.url("usage"), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertEqual(item.status, AIUsage.Status.SETTLED)
        self.assertEqual(item.accounting_source, AIUsage.AccountingSource.MANUAL)
        self.assertEqual(item.reconciled_by_id, self.owner.pk)
        self.assertIsNotNone(item.reconciled_at)
        self.assertEqual(item.reconciliation_note, data["note"])
        self.assertEqual(item.reconciliation_snapshot["input_tokens"], 100)
        self.assertEqual(item.estimated_cost_usd, Decimal("0.000142"))
        self.assertEqual(item.total_tokens, 130)

    def test_manual_reconciliation_requires_note_and_valid_subsets(self):
        item = self.make_usage()
        for changes, field in (({"note": ""}, "note"), ({"cached_tokens": 101}, "cached_tokens"),
                               ({"reasoning_tokens": 31}, "reasoning_tokens"), ({"input_tokens": -1}, "input_tokens")):
            with self.subTest(changes=changes):
                response = self.client.post(self.url("reconcile", usage_id=item.pk), self.reconciliation_data(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context["form"].errors)
        item.refresh_from_db()
        self.assertIsNone(item.reconciled_by_id)
        self.assertEqual(item.status, AIUsage.Status.UNCERTAIN)

    def test_reconciliation_replay_is_idempotent_and_changed_replay_rejected(self):
        item = self.make_usage()
        url, data = self.url("reconcile", usage_id=item.pk), self.reconciliation_data()
        self.assertEqual(self.client.post(url, data).status_code, 302)
        item.refresh_from_db()
        first_time, first_snapshot = item.reconciled_at, dict(item.reconciliation_snapshot)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        rejected = self.client.post(url, {**data, "input_tokens": 200})
        self.assertEqual(rejected.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.reconciled_at, first_time)
        self.assertEqual(item.reconciliation_snapshot, first_snapshot)

    def test_manual_zero_is_explicit_and_does_not_claim_provider_measurement(self):
        item = self.make_usage()
        response = self.client.post(self.url("reconcile", usage_id=item.pk), self.reconciliation_data(
            input_tokens=0, output_tokens=0, cached_tokens=0, reasoning_tokens=0,
            note="Panel de prueba: confirme explícitamente que no hubo consumo."))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.input_tokens, 0)
        self.assertEqual(item.estimated_cost_usd, 0)
        self.assertEqual(item.accounting_source, AIUsage.AccountingSource.MANUAL)

    def test_known_provider_usage_cannot_be_overwritten_from_reconciliation_form(self):
        item = self.make_usage(status=AIUsage.Status.SETTLED, accounting_source=AIUsage.AccountingSource.PROVIDER,
                               input_tokens=100, output_tokens=30, total_tokens=130, estimated_cost_usd="0.000160")
        response = self.client.post(self.url("reconcile", usage_id=item.pk), self.reconciliation_data())
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["form"].non_field_errors())
        item.refresh_from_db()
        self.assertEqual(item.accounting_source, AIUsage.AccountingSource.PROVIDER)
        self.assertIsNone(item.reconciled_by_id)

    def test_profile_names_and_reconciliation_notes_are_escaped_when_rendered(self):
        self.profile.name = '<img src=x onerror="alert(1)">'
        self.profile.save(update_fields=["name"])
        listing = self.client.get(self.url("providers"))
        self.assertContains(listing, "&lt;img")
        self.assertNotContains(listing, self.profile.name)
        item = self.make_usage()
        note = '<script>alert("synthetic")</script> Fuente de prueba externa.'
        self.assertEqual(self.client.post(self.url("reconcile", usage_id=item.pk), self.reconciliation_data(note=note)).status_code, 302)
        history = self.client.get(self.url("usage"))
        self.assertContains(history, "&lt;script&gt;")
        self.assertNotContains(history, note)
        for name in ("index", "providers", "budget", "calculator", "usage"):
            response = self.client.get(self.url(name))
            self.assertNotContains(response, "http-only-test-secret")
            self.assertNotContains(response, "groq-http-only-secret")
            self.assertNotContains(response, "gemini-http-only-secret")
