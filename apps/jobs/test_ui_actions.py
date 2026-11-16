"""Browser intentions are explicit, session-bound and unrelated to model work."""

from datetime import timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIAccount, AIUsage
from apps.assistant.execution import agent_execution
from . import ui_actions
from .models import Job, UIAction


class UIActionTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="theme-owner")
        self.other = get_user_model().objects.create_user(username="theme-other")
        self.portal = PortalAccount.objects.create(user=self.owner)
        self.client.force_login(self.owner)
        session = self.client.session
        session["portal_auth_version"] = 1
        session.save()
        self.tab = str(uuid.uuid4())
        self.key = str(uuid.uuid4())
        self.create_url = reverse("events:romeo_action_create")

    def create(self, **values):
        data = {"action": "theme_dark", "tab_id": self.tab, "request_key": self.key}
        data.update(values)
        return self.client.post(self.create_url, data)

    def transition(self, action_id, step, **values):
        data = {"tab_id": self.tab}
        data.update(values)
        return self.client.post(reverse("events:romeo_action_" + step, args=[action_id]), data)

    def new_action(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_create_start_finish_reports_only_bounded_action_metadata_without_ai(self):
        before = timezone.now()
        with patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No network")), \
                patch("subprocess.Popen", side_effect=AssertionError("No shell")), \
                patch("apps.jobs.services.enqueue", side_effect=AssertionError("No model jobs")):
            response = self.create()
            self.assertEqual(response.status_code, 201)
            data = response.json()
            self.assertEqual(set(data), {"id", "action", "query", "state", "expires_at"})
            self.assertEqual((data["action"], data["state"]), ("theme_dark", "pending"))
            self.assertEqual(data["query"], "")
            action = UIAction.objects.get(pk=data["id"])
            self.assertGreaterEqual(action.expires_at, before + timedelta(seconds=60))
            self.assertLessEqual(action.expires_at, timezone.now() + timedelta(seconds=60))
            self.assertNotEqual(action.session_digest, self.client.session.session_key)
            self.assertEqual(len(action.session_digest), 64)
            self.assertEqual(self.transition(action.pk, "start").json()["state"], "executing")
            finished = self.transition(action.pk, "finish", outcome="completed")
            self.assertEqual(finished.json()["state"], "completed")
        self.assertIn("no-store", finished["Cache-Control"])
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(AIAccount.objects.exists())

    def test_create_request_key_replay_is_exact_and_never_adds_another_action(self):
        action_id = self.new_action()
        replay = self.create()
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["id"], action_id)
        self.assertEqual(self.create(action="theme_light").status_code, 409)
        self.assertEqual(self.create(tab_id=str(uuid.uuid4())).status_code, 409)
        self.assertEqual(UIAction.objects.count(), 1)

    def test_only_one_active_action_per_actor_tab_and_new_tab_is_independent(self):
        first = self.new_action()
        self.assertEqual(self.create(request_key=str(uuid.uuid4())).status_code, 409)
        self.assertEqual(self.create(request_key=str(uuid.uuid4()), tab_id=str(uuid.uuid4())).status_code, 201)
        self.transition(first, "finish", outcome="cancelled")
        self.assertEqual(self.create(request_key=str(uuid.uuid4())).status_code, 201)

    def test_completed_requires_executing_and_terminal_result_cannot_be_inverted(self):
        action = self.new_action()
        self.assertEqual(self.transition(action, "finish", outcome="completed").status_code, 409)
        self.assertEqual(self.transition(action, "finish", outcome="failed").status_code, 409)
        self.assertEqual(self.transition(action, "start").status_code, 200)
        self.assertEqual(self.transition(action, "start").status_code, 409)
        result = self.transition(action, "finish", outcome="completed")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.transition(action, "finish", outcome="completed").json(), result.json())
        for outcome in ("cancelled", "failed"):
            self.assertEqual(self.transition(action, "finish", outcome=outcome).status_code, 409)
        self.assertEqual(self.transition(action, "start").status_code, 409)

    def test_cancellation_is_allowed_before_and_during_execution_and_idempotent(self):
        for should_start in (False, True):
            with self.subTest(started=should_start):
                action = self.create(request_key=str(uuid.uuid4())).json()["id"]
                if should_start:
                    self.transition(action, "start")
                response = self.transition(action, "finish", outcome="cancelled")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["state"], "cancelled")
                self.assertEqual(self.transition(action, "finish", outcome="cancelled").status_code, 200)
                self.assertEqual(self.transition(action, "finish", outcome="completed").status_code, 409)

    def test_failed_executing_action_is_terminal(self):
        action = self.new_action()
        self.transition(action, "start")
        self.assertEqual(self.transition(action, "finish", outcome="failed").json()["state"], "failed")
        self.assertEqual(self.transition(action, "finish", outcome="failed").status_code, 200)
        self.assertEqual(self.transition(action, "finish", outcome="completed").status_code, 409)

    def test_expiration_rejects_execution_persists_expired_and_frees_active_slot(self):
        action = self.new_action()
        UIAction.objects.filter(pk=action).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.transition(action, "start").status_code, 409)
        self.assertEqual(UIAction.objects.get(pk=action).state, "expired")
        self.assertEqual(self.transition(action, "finish", outcome="cancelled").status_code, 409)
        self.assertEqual(self.create().json()["state"], "expired")
        self.assertEqual(self.create(request_key=str(uuid.uuid4())).status_code, 201)

    def test_executing_action_cannot_report_success_after_ttl(self):
        action = self.new_action()
        self.transition(action, "start")
        UIAction.objects.filter(pk=action).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.transition(action, "finish", outcome="completed").status_code, 409)
        self.assertEqual(UIAction.objects.get(pk=action).state, "expired")

    def test_new_request_expires_old_pending_action_without_separate_cleanup(self):
        action = self.new_action()
        UIAction.objects.filter(pk=action).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.create(request_key=str(uuid.uuid4())).status_code, 201)
        self.assertEqual(UIAction.objects.get(pk=action).state, "expired")

    def test_owner_tab_and_session_are_all_required_without_enumerating_actions(self):
        action = self.new_action()
        expected = {"error": "Acceso no permitido."}
        self.assertEqual(self.transition(action, "start", tab_id=str(uuid.uuid4())).json(), expected)
        self.assertEqual(self.transition(uuid.uuid4(), "start").json(), expected)
        second_session = Client()
        second_session.force_login(self.owner)
        response = second_session.post(reverse("events:romeo_action_start", args=[action]), {"tab_id": self.tab})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), expected)
        replay = second_session.post(self.create_url, {"tab_id": self.tab, "action": "theme_dark", "request_key": self.key})
        self.assertEqual(replay.status_code, 403)
        self.client.force_login(self.other)
        response = self.transition(action, "start")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), expected)
        self.assertEqual(UIAction.objects.get(pk=action).state, "pending")

    def test_revoked_role_and_inactive_actor_are_checked_fresh(self):
        action = self.new_action()
        # A direct stale authenticated request still cannot bypass fresh checks.
        request = RequestFactory().post(reverse("events:romeo_action_start", args=[action]), {"tab_id": self.tab})
        request.user, request.session = self.owner, self.client.session
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.REVIEWER)
        self.assertEqual(ui_actions.start(request, uuid.UUID(action)).status_code, 403)
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.ORGANIZER)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertTrue(self.owner.is_active)
        self.assertEqual(ui_actions.start(request, uuid.UUID(action)).status_code, 403)
        self.assertEqual(UIAction.objects.get(pk=action).state, "pending")

    def test_admin_can_change_theme_but_agent_execution_context_cannot_create_or_finish(self):
        self.owner.is_superuser = True
        self.owner.save(update_fields=["is_superuser"])
        action = self.new_action()
        with agent_execution("romeo-1"):
            self.assertEqual(self.create(request_key=str(uuid.uuid4()), tab_id=str(uuid.uuid4())).status_code, 403)
            self.assertEqual(self.transition(action, "start").status_code, 403)
            self.assertEqual(self.transition(action, "finish", outcome="cancelled").status_code, 403)
        self.assertEqual(UIAction.objects.count(), 1)
        self.assertEqual(UIAction.objects.get(pk=action).state, "pending")

    def test_strict_allowlist_uuid_and_outcome_validation_without_input_reflection(self):
        marker = "<script>private-input</script>"
        for values in ({"action": "shutdown"}, {"action": marker}, {"tab_id": marker}, {"request_key": "bad"}, {"action": ""}):
            with self.subTest(values=values):
                response = self.create(**values)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn(marker, response.content.decode())
        action = self.new_action()
        self.assertEqual(self.transition(action, "finish", outcome="running").status_code, 400)
        self.assertEqual(self.transition(action, "start", tab_id="bad").status_code, 400)
        self.assertEqual(UIAction.objects.count(), 1)

    def test_login_get_and_csrf_are_enforced_without_mutation(self):
        self.client.logout()
        self.assertEqual(self.create().status_code, 302)
        self.client.force_login(self.owner)
        for url in (self.create_url, reverse("events:romeo_action_start", args=[uuid.uuid4()]),
                    reverse("events:romeo_action_finish", args=[uuid.uuid4()])):
            self.assertEqual(self.client.get(url).status_code, 405)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        data = {"action": "theme_light", "tab_id": self.tab, "request_key": self.key}
        self.assertEqual(secured.post(self.create_url, data).status_code, 403)
        secured.get(reverse("events:index"))
        data["csrfmiddlewaretoken"] = secured.cookies["csrftoken"].value
        self.assertEqual(secured.post(self.create_url, data).status_code, 201)
        self.assertEqual(UIAction.objects.count(), 1)

    def test_database_constraints_reject_parallel_active_slot_and_duplicate_identity(self):
        action = self.new_action()
        original = UIAction.objects.get(pk=action)
        for values in ({"request_key": uuid.uuid4(), "tab_id": original.tab_id},
                       {"request_key": original.request_key, "tab_id": uuid.uuid4()}):
            with self.subTest(values=list(values)), self.assertRaises(IntegrityError), transaction.atomic():
                UIAction.objects.create(actor=self.owner, action="theme_light", state="pending",
                    session_digest=original.session_digest, expires_at=original.expires_at, **values)
        self.assertEqual(UIAction.objects.count(), 1)

    def test_six_fixed_actions_preserve_intent_across_start_and_finish_without_ai(self):
        self.assertEqual(set(UIAction.Action.values), {
            "theme_light", "theme_dark", "calendar_open", "directory_open", "people_search", "events_open",
        })
        with patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No API")), \
                patch("subprocess.Popen", side_effect=AssertionError("No shell")):
            for action_name in UIAction.Action.values:
                with self.subTest(action=action_name):
                    query = "Persona Ficticia" if action_name == "people_search" else ""
                    response = self.create(action=action_name, query=query, request_key=str(uuid.uuid4()))
                    self.assertEqual(response.status_code, 201)
                    data = response.json()
                    self.assertEqual((data["action"], data["query"]), (action_name, query))
                    started = self.transition(data["id"], "start")
                    self.assertEqual((started.json()["action"], started.json()["query"]), (action_name, query))
                    finished = self.transition(data["id"], "finish", outcome="completed")
                    self.assertEqual((finished.json()["state"], finished.json()["query"]), ("completed", query))
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(AIAccount.objects.exists())

    def test_search_unicode_is_nfc_trimmed_and_canonical_retry_is_bound_to_exact_query(self):
        first = self.create(action="people_search", query="  Jose\u0301  ")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["query"], "José")
        canonical = self.create(action="people_search", query="José")
        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(canonical.json(), first.json())
        for changed in ("Otra persona", "josé", "José Pérez"):
            with self.subTest(query=changed):
                self.assertEqual(self.create(action="people_search", query=changed).status_code, 409)
        self.assertEqual(UIAction.objects.get(pk=first.json()["id"]).query, "José")
        self.assertEqual(UIAction.objects.count(), 1)

    def test_search_requires_bounded_text_without_unicode_controls(self):
        invalid = ("", "   ", "x" * 101, "\nAna", "Ana\t", "Ana\x00", "Ana\x7f", "Ana\u202e", "Ana\u2028", "Ana\u2029")
        for query in invalid:
            with self.subTest(query=repr(query)):
                response = self.create(action="people_search", query=query)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"error": "Revisa los campos de la acción permitida."})
        self.assertEqual(self.create(action="people_search").status_code, 400)
        with self.assertRaises(ValueError):
            ui_actions._query("people_search", "Ana\ud800")
        self.assertFalse(UIAction.objects.exists())
        # Length is checked after NFC composition, so a100character name fits.
        response = self.create(action="people_search", query="e\u0301" * 100)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["query"], "é" * 100)

    def test_other_actions_reject_queries_and_extra_provider_parameters_are_never_instructions(self):
        for action_name in set(UIAction.Action.values) - {"people_search"}:
            with self.subTest(action=action_name):
                self.assertEqual(self.create(action=action_name, query="buscar otra cosa").status_code, 400)
        response = self.create(action="calendar_open", url="https://untrusted.invalid", selector="#delete-users", command="shutdown")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json()), {"id", "action", "query", "state", "expires_at"})
        self.assertEqual((response.json()["action"], response.json()["query"]), ("calendar_open", ""))
        self.assertNotIn("untrusted", response.content.decode())
        self.assertEqual(UIAction.objects.count(), 1)

    def test_query_is_literal_text_and_cannot_replace_the_persisted_intent_during_transition(self):
        literal = "javascript:alert(1); <img src=x>"
        created = self.create(action="people_search", query=literal).json()
        started = self.transition(created["id"], "start", query="changed", url="/admin/")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["query"], literal)
        finished = self.transition(created["id"], "finish", outcome="completed", action="shutdown", query="changed")
        self.assertEqual(finished.status_code, 200)
        self.assertEqual((finished.json()["action"], finished.json()["query"]), ("people_search", literal))
        self.assertEqual(UIAction.objects.get(pk=created["id"]).query, literal)

    def test_database_enforces_query_scope_and_action_whitelist(self):
        for action_name, query in (("shell", ""), ("people_search", ""), ("calendar_open", "unexpected")):
            with self.subTest(action=action_name), self.assertRaises(IntegrityError), transaction.atomic():
                UIAction.objects.create(actor=self.owner, request_key=uuid.uuid4(), tab_id=uuid.uuid4(),
                    session_digest="a" * 64, action=action_name, query=query, expires_at=timezone.now() + timedelta(seconds=60))
        self.assertFalse(UIAction.objects.exists())
