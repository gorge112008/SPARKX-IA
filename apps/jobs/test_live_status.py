"""Local observations only: no provider, budget mutation or active database."""

from datetime import timedelta
import json
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.assistant.models import Message
from apps.events.models import Event
from .live_status import RECENT_TERMINAL_AGE, build_live_status, view
from .models import Job
from .trace import STAGES


class LiveStatusTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="live-organizer")
        self.other = get_user_model().objects.create_user(username="live-other")
        self.portal = PortalAccount.objects.create(user=self.owner)
        self.event = Event.objects.create(owner=self.owner, title="Seminario ficticio UNAC", brief="No enviar")
        self.second = Event.objects.create(owner=self.owner, title="Segundo evento ficticio", brief="No enviar")
        self.foreign = Event.objects.create(owner=self.other, title="Título privado ajeno", brief="No enviar")
        self.url = reverse("events:romeo_status")

    def job(self, *, event=None, actor=None, status=Job.Status.QUEUED, **kwargs):
        values = {
            "event": event or self.event, "actor": actor or self.owner,
            "kind": Job.Kind.PLAN, "status": status, "prompt": "PROMPT-PRIVADO-NO-EXPONER",
            "base_revision": 1, "request_hash": "a" * 64, "idempotency_key": str(uuid.uuid4()),
            "error": "ERROR-PRIVADO-NO-EXPONER", "result": {"private": "RESULTADO-PRIVADO"},
        }
        if status == Job.Status.RUNNING:
            values.update(claim_token=uuid.uuid4(), lease_until=timezone.now() + timedelta(minutes=2))
        values.update(kwargs)
        return Job.objects.create(**values)

    def login(self, user=None):
        self.client.force_login(user or self.owner)
        session = self.client.session
        session["portal_auth_version"] = 1
        session.save()

    def test_no_jobs_is_idle_and_does_not_create_configuration(self):
        from apps.ai_management.models import AIAccount, AIUsage
        with CaptureQueriesContext(connection) as queries:
            data = build_live_status(self.owner)
        self.assertEqual(set(data), {"agent", "state", "jobs", "observed_at"})
        self.assertEqual(data["agent"], "Gica-1")
        self.assertEqual(data["state"], "idle")
        self.assertEqual(data["jobs"], [])
        self.assertTrue(all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries))
        self.assertFalse(AIAccount.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(Job.objects.exists())

    def test_anonymous_redirects_to_login_and_non_get_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        with self.assertRaises(PermissionDenied):
            build_live_status(AnonymousUser())
        self.login()
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(self.client.head(self.url).status_code, 405)

    def test_deactivation_is_rechecked_for_stale_user_without_server_error(self):
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertTrue(self.owner.is_active)
        with self.assertRaises(PermissionDenied):
            build_live_status(self.owner)
        request = RequestFactory().get(self.url)
        request.user = self.owner
        response = view(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content), {"error": "Acceso no permitido."})

    def test_current_role_revocation_returns_json_403_even_with_event_ownership(self):
        self.job()
        self.login()
        # Cached role on the user must not preserve the old organizer access.
        self.owner.portal_account.role = PortalAccount.Role.ORGANIZER
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.REVIEWER)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Acceso no permitido."})
        self.assertIn("no-store", response["Cache-Control"])

    def test_administrator_is_still_restricted_to_own_event_and_own_actor(self):
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        own = self.job()
        self.job(event=self.foreign)  # Matching actor alone does not confer ownership.
        self.job(actor=self.other)  # Matching event alone does not expose another actor.
        self.job(event=self.foreign, actor=self.other)
        data = build_live_status(self.owner)
        self.assertEqual([item["id"] for item in data["jobs"]], [str(own.pk)])
        self.assertNotIn("Título privado ajeno", json.dumps(data))

    def test_optional_event_uuid_is_validated_without_reflecting_input(self):
        self.login()
        marker = "<script>arbitrary-marker</script>"
        for supplied in (marker, "", "123", "[]"):
            with self.subTest(supplied=supplied):
                response = self.client.get(self.url, {"event_id": supplied})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"error": "Referencia de evento inválida."})
                self.assertNotIn(marker, response.content.decode())

    def test_optional_foreign_or_unknown_event_is_nonenumerating_json_403(self):
        self.login()
        for supplied in (self.foreign.pk, uuid.uuid4()):
            with self.subTest(supplied=supplied):
                response = self.client.get(self.url, {"event_id": supplied})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"error": "Acceso no permitido."})
                self.assertNotIn(str(supplied), response.content.decode())

    def test_current_event_prioritizes_but_never_expands_scope_and_caps_two(self):
        other_own = self.job(event=self.second, status=Job.Status.RUNNING)
        preferred = self.job()
        self.job(event=self.second)
        self.job(event=self.foreign, actor=self.other, status=Job.Status.RUNNING)
        terminal = self.job(status=Job.Status.SUCCEEDED)
        data = build_live_status(self.owner, str(self.event.pk))
        self.assertEqual([item["id"] for item in data["jobs"]], [str(preferred.pk), str(other_own.pk)])
        self.assertEqual(data["state"], "queued")
        self.assertNotIn(str(terminal.pk), json.dumps(data))
        # No event preference still prefers already running work to queued work.
        self.assertEqual(build_live_status(self.owner)["jobs"][0]["id"], str(other_own.pk))

    def test_recent_terminal_fallback_is_latest_and_expires(self):
        older = self.job(status=Job.Status.FAILED)
        latest = self.job(event=self.second, status=Job.Status.SUCCEEDED)
        Job.objects.filter(pk=older.pk).update(updated_at=timezone.now() - timedelta(minutes=1))
        data = build_live_status(self.owner, self.event.pk)
        self.assertEqual(data["state"], "succeeded")
        self.assertEqual([row["id"] for row in data["jobs"]], [str(latest.pk)])
        Job.objects.update(updated_at=timezone.now() - RECENT_TERMINAL_AGE - timedelta(seconds=1))
        self.assertEqual(build_live_status(self.owner)["state"], "idle")

    def test_payload_contains_only_allowlisted_fields_and_server_stage_label(self):
        stamp = timezone.now().isoformat()
        self.event.title = "X" * 150
        self.event.save(update_fields=["title"])
        job = self.job(execution_trace=[
            {"stage": "queued", "at": stamp},
            {"stage": "context_ready", "at": stamp, "label": "UNTRUSTED-LABEL", "prompt": "PRIVATE-TRACE"},
            {"stage": "model_private_thoughts", "at": stamp, "label": "PRIVATE-TRACE"},
            {"stage": ["unhashable"], "at": stamp},
            {"stage": "request_started", "at": "invalid-date"},
            {"stage": "validating", "at": "2026-11-15T10:00:00"},
        ])
        self.login()
        with patch("apps.jobs.services.enqueue", side_effect=AssertionError("read-only")), \
                patch("apps.jobs.services.process_claim", side_effect=AssertionError("no dispatch")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("no network")), \
                patch("subprocess.run", side_effect=AssertionError("no child")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        row = response.json()["jobs"][0]
        self.assertEqual(set(row), {"id", "event_id", "event_title", "event_url", "kind", "status", "stage", "stage_label", "updated_at"})
        self.assertEqual(row["id"], str(job.pk))
        self.assertEqual(row["event_title"], "X" * 100)
        self.assertEqual(row["event_url"], reverse("events:detail", args=[self.event.pk]))
        self.assertEqual(row["stage"], "context_ready")
        self.assertEqual(row["stage_label"], STAGES["context_ready"][0])
        for marker in ("PROMPT-PRIVADO", "ERROR-PRIVADO", "RESULTADO-PRIVADO", "PRIVATE-TRACE", "UNTRUSTED-LABEL"):
            self.assertNotIn(marker, response.content.decode())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_malformed_or_missing_trace_uses_status_label_without_exception(self):
        job = self.job(execution_trace={"unexpected": "PRIVATE-TRACE"})
        row = build_live_status(self.owner)["jobs"][0]
        self.assertEqual(row["stage"], "")
        self.assertEqual(row["stage_label"], job.get_status_display())
        Job.objects.filter(pk=job.pk).update(execution_trace=[None, [], {"stage": "queued"}, {"stage": "failed", "at": None}])
        self.assertEqual(build_live_status(self.owner)["jobs"][0]["stage"], "")

    def local_reply(self, *, event=None, **kwargs):
        return Message.objects.create(
            event=event or self.event, role=Message.Role.ASSISTANT,
            content="CONTENIDO-PRIVADO-LOCAL", request_key="local:" + str(uuid.uuid4()), **kwargs,
        )

    def test_recent_local_completion_exposes_metadata_only_and_expires(self):
        reply = self.local_reply()
        data = build_live_status(self.owner)
        self.assertEqual(data["state"], "local_completed")
        self.assertEqual(data["jobs"], [])
        self.assertEqual(set(data["local_result"]), {"id", "event_id", "event_title", "event_url", "created_at"})
        self.assertEqual(data["local_result"]["id"], str(reply.pk))
        self.assertEqual(data["local_result"]["event_url"], reverse("events:detail", args=[self.event.pk]))
        self.assertNotIn("CONTENIDO-PRIVADO-LOCAL", json.dumps(data))
        Message.objects.filter(pk=reply.pk).update(created_at=timezone.now() - RECENT_TERMINAL_AGE - timedelta(seconds=1))
        data = build_live_status(self.owner)
        self.assertEqual(data["state"], "idle")
        self.assertNotIn("local_result", data)

    def test_local_result_obeys_owner_and_optional_event_and_ignores_other_messages(self):
        reply = self.local_reply()
        self.local_reply(event=self.second)
        self.local_reply(event=self.foreign)
        Message.objects.create(event=self.event, role=Message.Role.USER, content="Privado", request_key="local:" + str(uuid.uuid4()))
        Message.objects.create(event=self.event, role=Message.Role.ASSISTANT, content="Privado", request_key=str(uuid.uuid4()))
        linked = self.job(status=Job.Status.SUCCEEDED)
        self.local_reply(job=linked)
        # A later terminal completion takes precedence over the earlier local reply.
        self.assertEqual(build_live_status(self.owner)["state"], "succeeded")
        Job.objects.filter(pk=linked.pk).update(updated_at=reply.created_at - timedelta(seconds=1))
        data = build_live_status(self.owner, self.event.pk)
        self.assertEqual(data["local_result"]["id"], str(reply.pk))
        self.assertEqual(data["local_result"]["event_id"], str(self.event.pk))

    def test_active_jobs_override_local_completion_and_latest_completed_action_wins(self):
        completed = self.job(status=Job.Status.FAILED)
        reply = self.local_reply()
        # Windows clock resolution can give both auto timestamps the same tick.
        # Establish the action ordering explicitly instead of depending on speed.
        anchor = timezone.now()
        Job.objects.filter(pk=completed.pk).update(updated_at=anchor - timedelta(seconds=2))
        Message.objects.filter(pk=reply.pk).update(created_at=anchor - timedelta(seconds=1))
        data = build_live_status(self.owner)
        self.assertEqual(data["state"], "local_completed")
        Job.objects.filter(pk=completed.pk).update(updated_at=anchor)
        self.assertEqual(build_live_status(self.owner)["state"], "failed")
        running = self.job(status=Job.Status.RUNNING)
        self.local_reply()
        data = build_live_status(self.owner)
        self.assertEqual(data["state"], "running")
        self.assertEqual(data["jobs"][0]["id"], str(running.pk))
        self.assertNotIn("local_result", data)
