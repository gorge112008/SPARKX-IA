"""Controlled local verification of observed execution and the Romeo worker."""
import json
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ai_management.models import AIUsage
from apps.ai_management.testing import configure_test_account
from apps.events.models import Event
from apps.jobs.management.commands.runromeo import next_controlled_job
from .models import Job
from .services import claim_next, enqueue, process_claim, run_one
from .trace import trace_rows


class Receipt:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        plan = {"title": "Demo ficticia", "summary": "Propuesta controlada", "sessions": [], "tasks": [], "risks": []}
        return json.dumps({"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": json.dumps(plan)}]}], "usage": {
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0},
        }}).encode()


@override_settings(OPENAI_API_KEY="fake-key-never-used")
class RomeoTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(username="romeo-owner", password="test-only-secret")
        self.account = configure_test_account(self.owner)
        profile = self.account.active_profile
        profile.model = "gpt-5.4-mini"
        profile.input_rate, profile.cached_rate, profile.output_rate = "0.75", "0.075", "4.50"
        profile.save()
        self.event = Event.objects.create(owner=self.owner, title="Demo ficticia", brief="Seminario de prueba completamente ficticio.", is_synthetic=True)

    def enqueue(self, event=None):
        return enqueue(event=event or self.event, actor=self.owner, kind="plan",
            prompt="Prepara una propuesta ficticia", idempotency_key=str(uuid.uuid4()))

    @patch("apps.assistant.provider._opener.open", return_value=Receipt())
    def test_observed_trace_and_usage_do_not_approve_plan(self, network):
        job = self.enqueue()
        result = process_claim(claim_next(job_id=job.pk))
        self.assertEqual(result.status, "succeeded")
        self.assertEqual([entry["stage"] for entry in result.execution_trace], [
            "queued", "context_ready", "request_started", "response_received", "validating", "review_ready"])
        self.assertEqual(result.ai_usage.total_tokens, 150)
        self.assertEqual(result.ai_usage.status, AIUsage.Status.SETTLED)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.active_plan_id)
        network.assert_called_once()

    @patch("apps.assistant.provider._opener.open", side_effect=TimeoutError)
    def test_network_failure_keeps_hold_and_never_invents_response(self, network):
        job = self.enqueue()
        result = process_claim(claim_next(job_id=job.pk))
        stages = [entry["stage"] for entry in result.execution_trace]
        self.assertEqual(result.status, "failed")
        self.assertIn("request_started", stages)
        self.assertNotIn("response_received", stages)
        self.assertEqual(result.ai_usage.status, "uncertain")
        self.assertIsNone(result.ai_usage.total_tokens)
        network.assert_called_once()

    def test_worker_selection_and_claim_remain_scoped_to_requested_job(self):
        first = self.enqueue()
        other = Event.objects.create(owner=self.owner, title="Otra demo", brief="Ficticia", is_synthetic=True)
        second = self.enqueue(other)
        # Windows clocks can give both creations the same timestamp; make the
        # intended queue order explicit rather than depending on random UUIDs.
        Job.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(next_controlled_job(self.owner.pk), first.pk)
        self.assertEqual(claim_next(job_id=second.pk).pk, second.pk)
        first.refresh_from_db()
        self.assertEqual(first.status, "queued")

    @patch("apps.assistant.provider._opener.open")
    def test_controlled_worker_closes_expired_claim_without_retry(self, network):
        job = self.enqueue()
        claim_next(job_id=job.pk)
        Job.objects.filter(pk=job.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.assertEqual(next_controlled_job(self.owner.pk), job.pk)
        self.assertIsNone(run_one(job_id=job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIsNone(next_controlled_job(self.owner.pk))
        network.assert_not_called()

    def test_trace_escapes_prompt_and_omits_untrusted_observations(self):
        job = self.enqueue()
        job.prompt = '<script>alert("unsafe")</script>'
        job.execution_trace = [{"stage": "private-thoughts", "at": "not-a-time"}]
        job.save()
        self.assertEqual(trace_rows(job), [])
        self.client.force_login(self.owner)
        response = self.client.get(reverse("events:detail", args=[self.event.pk]))
        self.assertContains(response, "Gica-1")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
        self.assertNotContains(response, "private-thoughts")

    @patch("apps.assistant.provider._opener.open")
    def test_prepare_command_is_inert_and_preserves_existing_plan(self, network):
        call_command("prepare_romeo", username=self.owner.username, stdout=StringIO())
        self.account.refresh_from_db()
        self.assertEqual(self.account.monthly_budget_usd, 1)
        self.assertEqual(self.account.active_profile.model, "gpt-5.4-mini")
        self.assertTrue(self.account.paid_enabled)
        self.assertFalse(Job.objects.exists())
        network.assert_not_called()

    def test_foreign_event_trace_is_not_accessible(self):
        job = self.enqueue()
        stranger = get_user_model().objects.create_user(username="stranger")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("events:detail", args=[self.event.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("events:job", args=[self.event.pk, job.pk]), HTTP_HX_REQUEST="true").status_code, 404)
