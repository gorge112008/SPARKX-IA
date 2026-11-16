"""Private API controls with synthetic secrets, isolated DB and no inference."""
from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from tools.opencode.catalog import policy_fingerprint

from apps.accounts.models import PortalAccount
from apps.assistant import provider
from apps.assistant.execution import agent_execution
from apps.jobs.models import Job
from . import runtime_credentials
from .agent_access import agent_preview_snapshot, update_agent_grant
from .control_forms import AgentAccessForm
from .models import AIAccount, AIProfile, AIUsage, AgentGrant
from .runtime_credentials import credential_status, disconnect_credential, key_reference, set_credential
from .services import profile_snapshot
from .testing import configure_test_account


@override_settings(DEBUG=True, ALLOWED_HOSTS=["127.0.0.1", "localhost", "testserver"],
                   SECURE_PROXY_SSL_HEADER=None, OPENAI_API_KEY="synthetic-env-fallback-never-use")
class APIControlTests(TestCase):
    def setUp(self):
        self.clear_runtime()
        self.addCleanup(self.clear_runtime)
        users = get_user_model()
        self.admin = users.objects.create_user(username="private-api-admin", is_superuser=True, is_staff=True)
        self.staff = users.objects.create_user(username="private-api-staff", is_staff=True)
        self.portal = users.objects.create_user(username="private-api-portal")
        PortalAccount.objects.update_or_create(user=self.portal, defaults={"role": PortalAccount.Role.ADMIN})
        self.organizer = users.objects.create_user(username="private-api-organizer")
        self.account = configure_test_account(self.admin, budget="1")
        self.profile = self.account.active_profile
        self.secret = "synthetic-private-only-credential-123456"
        self.client.force_login(self.admin)
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("API configuration must not infer"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(self.remote.assert_not_called)

    def clear_runtime(self):
        with runtime_credentials._lock:
            runtime_credentials._entries.clear()

    def test_retired_legacy_fallback_can_still_open_control_for_revocation(self):
        retired = AIProfile.objects.create(owner=self.admin, name="Retired synthetic fallback",
            provider="opencode", model="removed-model-fixture", mode="free", free_tier_confirmed=True)
        AgentGrant.objects.create(account=self.account, primary_profile=self.profile,
            fallback_profile=retired, configured_by=self.admin)
        response = self.request("control")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["agent_form"].initial["expected_fallback_policy_fingerprint"], "")

    def url(self, name):
        return reverse("ai_management:" + name)

    def request(self, name, data=None, *, client=None, method=None, **headers):
        client = client or self.client
        headers = {"HTTP_HOST": "127.0.0.1", "SERVER_PORT": "80", "REMOTE_ADDR": "127.0.0.1", **headers}
        return getattr(client, method or ("get" if data is None else "post"))(self.url(name), data or {}, **headers)

    def grant_data(self, **changes):
        data = {"enabled": "on", "primary_profile": self.profile.pk, "budget_usd": "1",
                "fallback_preset": "", "expected_version": 0}
        data.update(changes)
        return data

    def grant(self):
        return update_agent_grant(actor=self.admin, account=self.account, expected_version=0,
            name="Romeo-1", enabled=True, budget_usd=Decimal("1"), primary_profile=self.profile)

    def configured_reference(self):
        set_credential(actor=self.admin, provider="openai", secret=self.secret)
        self.grant()
        return agent_preview_snapshot(self.account)

    def test_login_and_post_only_are_required_without_creating_credentials(self):
        self.client.logout()
        self.assertEqual(self.request("control").status_code, 302)
        self.assertEqual(self.request("credential_save", {"provider": "openai", "api_key": self.secret}).status_code, 302)
        self.client.force_login(self.admin)
        for route in ("credential_save", "credential_remove", "agent_save"):
            with self.subTest(route=route):
                self.assertEqual(self.request(route).status_code, 405)
        self.assertFalse(credential_status(self.admin.pk, "openai")["managed"])
        self.assertFalse(AgentGrant.objects.exists())

    def test_staff_portal_admin_and_organizer_cannot_read_or_mutate_controls(self):
        before = AIProfile.objects.count()
        for actor in (self.staff, self.portal, self.organizer):
            self.client.force_login(actor)
            for route, data in (("control", None),
                                ("credential_save", {"provider": "openai", "api_key": self.secret}),
                                ("credential_remove", {"provider": "openai"}),
                                ("agent_save", self.grant_data())):
                with self.subTest(actor=actor.username, route=route):
                    response = self.request(route, data)
                    self.assertEqual(response.status_code, 403)
                    self.assertNotContains(response, self.secret, status_code=403)
            self.assertFalse(credential_status(actor.pk, "openai")["managed"])
        self.assertEqual(AIProfile.objects.count(), before)
        self.assertFalse(AgentGrant.objects.exists())

    def test_revoked_superuser_is_rechecked_even_with_stale_actor_object(self):
        get_user_model().objects.filter(pk=self.admin.pk).update(is_superuser=False)
        self.assertTrue(self.admin.is_superuser)
        with self.assertRaises(PermissionDenied):
            set_credential(actor=self.admin, provider="openai", secret=self.secret)
        self.assertEqual(self.request("control").status_code, 403)
        self.assertEqual(self.request("credential_save", {"provider": "openai", "api_key": self.secret}).status_code, 403)
        self.assertFalse(credential_status(self.admin.pk, "openai")["managed"])

    def test_agent_execution_cannot_administer_even_with_superuser_identity(self):
        with agent_execution():
            self.assertEqual(self.request("control").status_code, 403)
            self.assertEqual(self.request("credential_save", {"provider": "openai", "api_key": self.secret}).status_code, 403)
            self.assertEqual(self.request("agent_save", self.grant_data()).status_code, 403)
            for operation in (
                lambda: set_credential(actor=self.admin, provider="openai", secret=self.secret),
                lambda: disconnect_credential(actor=self.admin, provider="openai"),
                self.grant,
            ):
                with self.assertRaises(PermissionDenied):
                    operation()
        self.assertFalse(AgentGrant.objects.exists())
        self.assertFalse(credential_status(self.admin.pk, "openai")["managed"])

    def test_save_is_memory_only_and_secret_never_enters_response_or_snapshot(self):
        before = (AIProfile.objects.count(), AIAccount.objects.count())
        response = self.request("credential_save", {"provider": "openai", "api_key": self.secret})
        self.assertRedirects(response, self.url("control"), fetch_redirect_response=False)
        page = self.request("control")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Disponible en esta ejecución")
        self.assertNotContains(page, self.secret)
        self.assertIn('type="password"', page.content.decode())
        snapshot = profile_snapshot(self.profile)
        self.assertEqual(snapshot["credential_version"], 1)
        self.assertTrue(snapshot["credential_ref"])
        self.assertNotIn(self.secret, json.dumps(snapshot))
        self.assertEqual((AIProfile.objects.count(), AIAccount.objects.count()), before)
        persisted = {"profiles": list(AIProfile.objects.values()), "accounts": list(AIAccount.objects.values())}
        self.assertNotIn(self.secret, json.dumps(persisted, default=str))
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertIn("no-store", page["Cache-Control"])
        self.assertIn("script-src 'self'", page["Content-Security-Policy"])

    def test_invalid_credentials_redirect_to_generic_unbound_form_without_echo(self):
        for provider_name, secret in (("unreviewed-provider", self.secret), ("openai", self.secret + " invalid space")):
            with self.subTest(provider=provider_name):
                self.assertEqual(self.request("credential_save", {"provider": provider_name, "api_key": secret}).status_code, 302)
                page = self.request("control")
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, secret)
                self.assertFalse(page.context["credential_form"].is_bound)
                self.assertFalse(credential_status(self.admin.pk, "openai")["available"])
        self.assertFalse(Job.objects.exists())

    def test_rotation_invalidates_queued_reference_without_environment_fallback(self):
        old = self.configured_reference()
        self.assertEqual(key_reference(old, "openai"), (True, self.secret))
        rotated = self.secret + "-rotated"
        self.assertEqual(self.request("credential_save", {"provider": "openai", "api_key": rotated}).status_code, 302)
        new = agent_preview_snapshot(self.account)
        self.assertNotEqual(old["credential_ref"], new["credential_ref"])
        self.assertEqual(new["credential_version"], old["credential_version"] + 1)
        self.assertEqual(key_reference(old, "openai"), (True, ""))
        self.assertFalse(provider.profile_ready(old))
        self.assertTrue(provider.profile_ready(new))
        with provider.use_profile(old):
            self.assertEqual(provider._key("openai"), "")

    def test_disconnect_and_lost_process_state_fail_closed_despite_environment_key(self):
        snapshot = self.configured_reference()
        self.assertEqual(self.request("credential_remove", {"provider": "openai"}).status_code, 302)
        disconnected = agent_preview_snapshot(self.account)
        for state in (snapshot, disconnected):
            self.assertEqual(key_reference(state, "openai"), (True, ""))
            self.assertFalse(provider.profile_ready(state))
        self.clear_runtime()
        self.assertEqual(key_reference(snapshot, "openai"), (True, ""))
        self.assertFalse(provider.profile_ready(snapshot))

    def test_credential_expiry_blocks_reference_and_never_uses_environment(self):
        snapshot = self.configured_reference()
        status = credential_status(self.admin.pk, "openai")
        self.assertEqual(status["expires_at"] - status["changed_at"], timedelta(hours=2))
        with patch("apps.ai_management.runtime_credentials.timezone.now", return_value=status["expires_at"]):
            self.assertEqual(key_reference(snapshot, "openai"), (True, ""))
            self.assertFalse(provider.profile_ready(snapshot))
            self.assertFalse(credential_status(self.admin.pk, "openai")["available"])

    def test_credentials_and_agent_updates_require_csrf_and_reject_remote_plaintext(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        targets = (("credential_save", {"provider": "openai", "api_key": self.secret}),
                   ("credential_remove", {"provider": "openai"}), ("agent_save", self.grant_data()))
        for route, data in targets:
            with self.subTest(route=route):
                self.assertEqual(self.request(route, data, client=client).status_code, 403)
        self.assertEqual(self.request("control", client=client).status_code, 200)
        token = client.cookies["csrftoken"].value
        data = {"provider": "openai", "api_key": self.secret, "csrfmiddlewaretoken": token}
        self.assertEqual(self.request("credential_save", data, client=client, REMOTE_ADDR="192.0.2.5").status_code, 403)
        self.assertFalse(credential_status(self.admin.pk, "openai")["managed"])
        self.assertEqual(self.request("credential_save", data, client=client).status_code, 302)
        self.assertTrue(credential_status(self.admin.pk, "openai")["available"])

    def test_agent_form_requires_explicit_fallback_policy_and_optimistic_version(self):
        data = self.grant_data(fallback_preset="opencode_beam")
        self.assertEqual(self.request("agent_save", data).status_code, 400)
        self.assertFalse(AgentGrant.objects.exists())
        self.assertFalse(AIProfile.objects.filter(provider="opencode").exists())
        data["accept_fallback_policy"] = "on"
        data["expected_fallback_policy_fingerprint"] = policy_fingerprint("beam-free")
        self.assertEqual(self.request("agent_save", data).status_code, 302)
        grant = AgentGrant.objects.select_related("fallback_profile").get(account=self.account)
        self.assertEqual((grant.name, grant.code), ("Gica-1", "romeo-1"))
        self.assertEqual(grant.fallback_profile.name, "Gica-1 · alternativa · opencode_beam")
        self.assertEqual(grant.budget_usd, Decimal("1"))
        self.assertEqual(grant.primary_profile_id, self.profile.pk)
        self.assertEqual(grant.fallback_profile.provider, "opencode")
        self.assertEqual(grant.fallback_policy_approved_by_id, self.admin.pk)
        self.assertTrue(grant.fallback_policy_fingerprint)
        self.assertEqual(self.request("agent_save", {**data, "budget_usd": "0.5"}).status_code, 400)
        grant.refresh_from_db()
        self.assertEqual(grant.budget_usd, Decimal("1"))
        self.assertEqual(grant.version, 1)
        self.assertEqual(AIProfile.objects.filter(provider="opencode").count(), 1)
        self.assertFalse(Job.objects.exists())

    def test_fallback_acceptance_rejects_missing_stale_or_other_model_policy(self):
        for fingerprint in ("", "0" * 64, policy_fingerprint("mimo-v2.6-flash-free")):
            with self.subTest(fingerprint=fingerprint):
                response = self.request("agent_save", self.grant_data(fallback_preset="opencode_beam",
                    accept_fallback_policy="on", expected_fallback_policy_fingerprint=fingerprint))
                self.assertEqual(response.status_code, 400)
                self.assertFalse(AgentGrant.objects.exists())
                self.assertFalse(AIProfile.objects.filter(provider="opencode").exists())
                form = response.context["agent_form"]
                self.assertEqual(form["fallback_preset"].value(), "opencode_beam")
                self.assertFalse(form["accept_fallback_policy"].value())
                self.assertEqual(form["expected_fallback_policy_fingerprint"].value(), policy_fingerprint("beam-free"))
                self.assertContains(response, 'data-fallback-policy="opencode_beam" data-policy-fingerprint="'
                    + policy_fingerprint("beam-free") + '"', status_code=400)
        self.assertFalse(Job.objects.exists())

    def test_unbound_budget_has_readable_decimal_without_changing_bound_draft_or_storage(self):
        grant = self.grant()
        for amount, displayed in (("1.000000", "1"), ("0.100000", "0.1"), ("0.000001", "0.000001")):
            with self.subTest(amount=amount):
                grant.budget_usd = Decimal(amount)
                grant.save(update_fields=["budget_usd"])
                response = self.request("control")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["agent_form"]["budget_usd"].value(), displayed)
                self.assertContains(response, 'name="budget_usd" value="' + displayed + '"')
                grant.refresh_from_db()
                self.assertEqual(grant.budget_usd, Decimal(amount))
        draft = AgentAccessForm(self.grant_data(budget_usd="0.100000"), account=self.account, grant=grant)
        self.assertEqual(draft["budget_usd"].value(), "0.100000")

    def test_agent_form_rejects_foreign_profile_and_budget_above_pilot_limit(self):
        other = configure_test_account(self.organizer)
        for changes in ({"primary_profile": other.active_profile_id}, {"budget_usd": "1.000001"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.request("agent_save", self.grant_data(**changes)).status_code, 400)
        self.assertFalse(AgentGrant.objects.exists())
        self.assertFalse(Job.objects.exists())
