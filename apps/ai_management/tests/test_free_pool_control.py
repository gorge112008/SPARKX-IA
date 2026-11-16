"""Human-only pool configuration through HTTP, with no external model calls."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.assistant.execution import agent_execution
from apps.jobs.models import Job
from tools.opencode.catalog import policy_fingerprint
from apps.ai_management.agent_access import update_agent_grant
from apps.ai_management.catalog import OPENCODE_DEMO_MODELS
from apps.ai_management.models import AIProfile, AIUsage, AgentPoolEntry, FreeGatewayState
from apps.ai_management.testing import configure_test_account


@override_settings(DEBUG=True, ALLOWED_HOSTS=["127.0.0.1", "localhost"],
                   SECURE_PROXY_SSL_HEADER=None, OPENAI_API_KEY="synthetic-test-not-a-credential")
class FreePoolControlTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="free-pool-admin", is_superuser=True, is_staff=True)
        self.member = users.objects.create_user(username="free-pool-member")
        self.staff = users.objects.create_user(username="free-pool-staff", is_staff=True)
        self.portal_admin = users.objects.create_user(username="free-pool-portal")
        PortalAccount.objects.update_or_create(user=self.portal_admin, defaults={"role": "admin"})
        self.account = configure_test_account(self.owner, budget="1")
        self.grant = update_agent_grant(actor=self.owner, account=self.account, expected_version=0,
            name="Romeo-1", enabled=True, budget_usd=Decimal("1"), primary_profile=self.account.active_profile)
        self.client = Client(HTTP_HOST="127.0.0.1", SERVER_PORT="80", REMOTE_ADDR="127.0.0.1")
        self.client.force_login(self.owner)
        for boundary in ("apps.assistant.provider._opener.open", "apps.assistant.free_harness.run_free_harness"):
            remote = patch(boundary, side_effect=AssertionError("Pool configuration must never infer"))
            mock = remote.start()
            self.addCleanup(remote.stop)
            self.addCleanup(mock.assert_not_called)

    def url(self, name):
        return reverse("ai_management:" + name)

    def data(self, **changes):
        data = {"preset": "opencode_beam", "enabled": "on", "roles": "chat", "priority": 10,
                "daily_request_limit": 5, "daily_token_limit": 60000,
                "expected_policy_fingerprint": policy_fingerprint("beam-free"),
                "expected_grant_version": self.grant.version}
        data.update(changes)
        return data

    def post(self, **changes):
        return self.client.post(self.url("pool_entry_save"), self.data(**changes))

    def test_catalog_shows_twelve_unapproved_models_without_creating_profiles_or_grants(self):
        before = AIProfile.objects.count()
        response = self.client.get(self.url("control"))
        self.assertEqual(response.status_code, 200)
        rows = response.context["pool_rows"]
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["policy"]["model"] for row in rows}, OPENCODE_DEMO_MODELS)
        self.assertTrue(all(not row.get("entry") for row in rows))
        self.assertFalse(response.context["pool_form"].initial["enabled"])
        self.assertFalse(response.context["pool_form"].initial["accept_policy"])
        self.assertContains(response, "por día UTC")
        self.assertNotContains(response, "nemotron-3-ultra-free")
        self.assertEqual(AIProfile.objects.count(), before)
        self.assertFalse(AgentPoolEntry.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_disabled_configuration_requires_no_acceptance_and_does_not_enable_pool(self):
        response = self.post(enabled="")
        self.assertEqual(response.status_code, 302)
        entry = AgentPoolEntry.objects.get()
        self.assertFalse(entry.enabled)
        self.assertEqual(entry.policy_fingerprint, "")
        self.assertIsNone(entry.approved_by_id)
        self.grant.refresh_from_db()
        self.assertFalse(self.grant.free_pool_enabled)
        self.assertFalse(self.grant.free_pool_for_plans)
        self.account.refresh_from_db()
        self.assertEqual(self.account.active_profile.provider, "openai")
        self.assertFalse(Job.objects.exists())

    def test_enable_requires_exact_model_policy_and_records_human_approval(self):
        before = AIProfile.objects.count()
        rejected = self.post()
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.context["pool_form"]["preset"].value(), "opencode_beam")
        self.assertEqual(rejected.context["pool_selected_code"], "opencode_beam")
        self.assertContains(rejected, f'data-pool-policy="opencode_beam" data-policy-fingerprint="{policy_fingerprint("beam-free")}" open', status_code=400)
        self.assertFalse(AgentPoolEntry.objects.exists())
        self.assertEqual(AIProfile.objects.count(), before)
        self.assertEqual(self.post(accept_policy="on").status_code, 302)
        entry = AgentPoolEntry.objects.select_related("profile").get()
        self.assertTrue(entry.enabled)
        self.assertEqual(entry.policy_fingerprint, policy_fingerprint("beam-free"))
        self.assertEqual(entry.approved_by_id, self.owner.pk)
        self.assertIsNotNone(entry.approved_at)
        self.assertEqual(entry.profile.provider, "opencode")
        self.assertEqual(entry.profile.owner_id, self.owner.pk)
        self.assertEqual(entry.profile.max_output_tokens, 2048)
        self.assertEqual((entry.profile.input_rate, entry.profile.cached_rate, entry.profile.output_rate), (0, 0, 0))
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_edit_prefills_selected_model_without_reaccepting_and_rejects_stale_version(self):
        self.assertEqual(self.post(accept_policy="on", roles="both", priority=3).status_code, 302)
        response = self.client.get(self.url("control"), {"pool_model": "opencode_beam"})
        form = response.context["pool_form"]
        self.assertEqual(form.initial["preset"], "opencode_beam")
        self.assertEqual(form.initial["roles"], "both")
        self.assertEqual(form.initial["priority"], 3)
        self.assertFalse(form.initial["accept_policy"])
        self.assertEqual(self.post(accept_policy="on", priority=4).status_code, 400)
        self.assertEqual(AgentPoolEntry.objects.get().priority, 3)

    def test_policy_fingerprint_missing_stale_or_from_another_model_cannot_approve(self):
        for fingerprint in ("", "0" * 64, policy_fingerprint("mimo-v2.6-flash-free")):
            with self.subTest(fingerprint=fingerprint):
                response = self.post(accept_policy="on", expected_policy_fingerprint=fingerprint)
                self.assertEqual(response.status_code, 400)
                self.assertContains(response, "Las condiciones cambiaron", status_code=400)
                self.assertFalse(response.context["pool_form"]["accept_policy"].value())
                self.assertEqual(response.context["pool_form"]["preset"].value(), "opencode_beam")
                self.assertEqual(response.context["pool_form"]["expected_policy_fingerprint"].value(), policy_fingerprint("beam-free"))
        self.assertFalse(AgentPoolEntry.objects.exists())

    def test_only_catalog_presets_and_bounded_roles_and_limits_are_accepted(self):
        before = AIProfile.objects.count()
        cases = [{"preset": "openai_54_mini"}, {"preset": "nemotron-3-ultra-free"},
                 {"roles": "admin"}, {"priority": 0}, {"priority": 101},
                 {"daily_request_limit": 0}, {"daily_request_limit": 101},
                 {"daily_token_limit": 2048}, {"daily_token_limit": 1000001}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.post(accept_policy="on", **changes).status_code, 400)
        self.assertEqual(AIProfile.objects.count(), before)
        self.assertFalse(AgentPoolEntry.objects.exists())

    def test_foreign_account_and_posted_rates_do_not_redirect_configuration(self):
        foreign = configure_test_account(self.member)
        response = self.post(accept_policy="on", account=foreign.pk, provider="openai",
                             model="unreviewed", input_rate="999", output_rate="999")
        self.assertEqual(response.status_code, 302)
        entry = AgentPoolEntry.objects.select_related("profile").get()
        self.assertEqual(entry.grant_id, self.grant.pk)
        self.assertEqual(entry.profile.owner_id, self.owner.pk)
        self.assertEqual(entry.profile.model, "beam-free")
        self.assertEqual(entry.profile.output_rate, 0)

    def test_non_superusers_and_agent_context_cannot_configure_pool(self):
        for actor in (self.member, self.staff, self.portal_admin):
            self.client.force_login(actor)
            self.assertEqual(self.post(accept_policy="on").status_code, 403)
        self.client.force_login(self.owner)
        with agent_execution():
            self.assertEqual(self.post(accept_policy="on").status_code, 403)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_superuser=False)
        self.assertEqual(self.post(accept_policy="on").status_code, 403)
        self.assertFalse(AgentPoolEntry.objects.exists())

    def test_post_only_csrf_and_local_transport_apply_to_pool(self):
        self.assertEqual(self.client.get(self.url("pool_entry_save")).status_code, 405)
        client = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1", SERVER_PORT="80", REMOTE_ADDR="127.0.0.1")
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url("pool_entry_save"), self.data(accept_policy="on")).status_code, 403)
        self.assertEqual(client.get(self.url("control")).status_code, 200)
        data = self.data(accept_policy="on", csrfmiddlewaretoken=client.cookies["csrftoken"].value)
        self.assertEqual(client.post(self.url("pool_entry_save"), data, REMOTE_ADDR="192.0.2.4").status_code, 403)
        self.assertEqual(client.post(self.url("pool_entry_save"), data).status_code, 302)
        self.assertEqual(AgentPoolEntry.objects.count(), 1)

    def test_shared_gateway_pause_is_visible_without_claiming_provider_reset(self):
        from datetime import timedelta
        from django.utils import timezone

        FreeGatewayState.objects.create(account=self.account, cooldown_until=timezone.now() + timedelta(minutes=10),
                                       last_error_code="quota_or_rate_limit")
        page = self.client.get(self.url("control"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "La pasarela gratuita está en pausa")
        self.assertContains(page, "no conocemos la hora de restablecimiento")
        self.assertFalse(Job.objects.exists())

    def test_pool_flags_can_be_disabled_and_legacy_posts_preserve_their_configuration(self):
        data = {"enabled": "on", "primary_profile": self.account.active_profile_id,
                "budget_usd": "1", "expected_version": self.grant.version,
                "fallback_preset": "", "pool_options_present": "on",
                "free_pool_enabled": "on", "free_pool_for_plans": "on"}
        self.assertEqual(self.client.post(self.url("agent_save"), data).status_code, 302)
        self.grant.refresh_from_db()
        self.assertTrue(self.grant.free_pool_enabled)
        self.assertTrue(self.grant.free_pool_for_plans)
        self.assertFalse(AgentPoolEntry.objects.exists())
        legacy = {key: value for key, value in data.items()
                  if key not in {"pool_options_present", "free_pool_enabled", "free_pool_for_plans"}}
        legacy["expected_version"] = self.grant.version
        self.assertEqual(self.client.post(self.url("agent_save"), legacy).status_code, 302)
        self.grant.refresh_from_db()
        self.assertTrue(self.grant.free_pool_enabled)
        self.assertTrue(self.grant.free_pool_for_plans)
        legacy.update(pool_options_present="on", expected_version=self.grant.version)
        self.assertEqual(self.client.post(self.url("agent_save"), legacy).status_code, 302)
        self.grant.refresh_from_db()
        self.assertFalse(self.grant.free_pool_enabled)
        self.assertFalse(self.grant.free_pool_for_plans)
        self.assertFalse(Job.objects.exists())

    def test_new_partial_stays_hidden_for_cached_runtime_without_pool_route_or_context(self):
        from types import ModuleType
        from django.template.loader import render_to_string
        from apps.ai_management.control_forms import PoolEntryForm

        old_urls = ModuleType("cached_runtime_urls_without_pool")
        old_urls.urlpatterns = []
        with override_settings(ROOT_URLCONF=old_urls):
            html = render_to_string("ai_management/_free_pool.html", {"pool_form": PoolEntryForm(grant=self.grant)})
        self.assertEqual(html.strip(), "")
        self.assertEqual(render_to_string("ai_management/_free_pool.html", {}).strip(), "")
