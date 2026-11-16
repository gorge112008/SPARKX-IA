"""Explicit OpenAI routing, provider payload and lifetime cap; all HTTP mocked."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ai_management.agent_access import update_agent_grant
from apps.ai_management.models import AIAccount, AIProfile, AIUsage, AgentGrant
from apps.ai_management.pilot import openai_pilot_summary
from apps.ai_management import runtime_credentials
from apps.ai_management.services import current_month
from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.management.commands.runromeo import next_controlled_job
from apps.jobs.services import claim_next, prepare_claim, run_one
from apps.planning.models import PlanCandidate, PlanRevision
from apps.assistant.compact_contract import BASE_CONTEXT, OPENAI_SCHEMA, OPENAI_PROPOSAL_SCHEMA
from apps.assistant.compact_planning import compact_wire
from apps.assistant.models import CompactPlanRequest
from apps.assistant.provider import profile_ready as provider_profile_ready
from apps.assistant.tests.test_compact_planning import PROPOSAL, QUESTIONS
from apps.assistant.tests import test_compact_planning as compact_fixtures


class _Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self, maximum): return json.dumps(self.payload).encode("utf-8")[:maximum]


class CompactOpenAITests(TestCase):
    post = compact_fixtures.CompactWorkflowTests.post
    preview = compact_fixtures.CompactWorkflowTests.preview
    archive = compact_fixtures.CompactWorkflowTests.archive
    poll = compact_fixtures.CompactWorkflowTests.poll

    def setUp(self):
        compact_fixtures.CompactWorkflowTests.setUp(self)
        self.openai_profile = AIProfile.objects.create(owner=self.owner, name="OpenAI reviewed fixture", provider="openai",
            model="gpt-5.4-mini", mode="paid", input_rate=Decimal(".75"), cached_rate=Decimal(".075"),
            output_rate=Decimal("4.5"), max_input_tokens=24000, max_output_tokens=2500)
        self.account.active_profile = self.openai_profile
        self.account.paid_enabled = True
        self.account.monthly_budget_usd = 1
        self.account.save()
        self.grant.refresh_from_db()
        self.grant = update_agent_grant(actor=self.owner, account=self.account, expected_version=self.grant.version,
            name="Gica-1", enabled=True, budget_usd=1, primary_profile=self.openai_profile,
            free_pool_enabled=True, free_pool_for_plans=True)

    def queue(self, **changes):
        response = self.post(provider="openai", **changes)
        self.assertEqual(response.status_code, 202, response.content)
        return Job.objects.get(pk=response.json()["job_id"])

    def process(self, job, result=PROPOSAL, *, status="completed", wrapper=True):
        text = json.dumps({"result": result} if wrapper else result)
        response = {"status": status, "output": [{"type": "message", "status": "completed", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 1400, "output_tokens": 220, "total_tokens": 1620,
                "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}
        with (patch("apps.assistant.provider._key", return_value="unit-placeholder"),
                patch("apps.assistant.provider._opener.open", return_value=_Response(response)) as remote,
                patch("apps.assistant.free_harness.run_compact_harness", side_effect=AssertionError("No free fallback")) as free):
            processed = run_one(job_id=job.pk)
        free.assert_not_called()
        return processed, remote

    def test_explicit_openai_real_pilot_reserves_gross_standard_cost_and_normalizes_strict_json(self):
        job = self.queue()
        self.assertFalse(self.event.is_synthetic)
        self.assertEqual(job.ai_usage.snapshot["provider"], "openai")
        self.assertEqual(job.ai_usage.snapshot["agent_route"], "primary")
        self.assertEqual(job.ai_usage.reserved_usd, Decimal(".017100"))
        self.assertEqual(job.ai_usage.reserved_input_tokens, 12000)
        self.assertEqual(job.ai_usage.reserved_output_tokens, 1800)
        self.assertEqual(next_controlled_job(self.owner.pk), job.pk)
        processed, remote = self.process(job)
        self.assertEqual(processed.status, "succeeded", processed.error)
        self.assertEqual(remote.call_count, 1)
        request = remote.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["model"], "gpt-5.4-mini")
        self.assertEqual(payload["max_output_tokens"], 1800)
        self.assertEqual(payload["reasoning"], {"effort": "none"})
        self.assertEqual(payload["service_tier"], "default")
        self.assertNotIn("tools", payload)
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["schema"], OPENAI_SCHEMA)
        self.assertEqual(json.loads(payload["input"][1]["content"])["context"], BASE_CONTEXT)
        self.assertNotIn("Castillo", request.data.decode())
        self.assertEqual(PlanCandidate.objects.count(), 1)
        self.assertEqual(PlanRevision.objects.count(), 0)
        result = self.poll(job).json()
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "gpt-5.4-mini")
        self.assertEqual(result["status"], "proposal")
        self.assertEqual(result["usage"]["total_tokens"], 1620)

    def test_preview_exact_openai_payload_matches_frozen_send_and_does_not_reserve(self):
        before = (Job.objects.count(), AIUsage.objects.count())
        preview = self.preview(provider="openai")
        self.assertEqual(preview.status_code, 200, preview.content)
        public = preview.json()
        self.assertEqual(public["provider"], "openai")
        self.assertEqual(public["model"], "gpt-5.4-mini")
        self.assertEqual(public["response_schema"], OPENAI_SCHEMA)
        self.assertNotIn("job_id", public)
        self.assertEqual(before, (Job.objects.count(), AIUsage.objects.count()))
        job = self.queue()
        frozen = prepare_claim(claim_next(job_id=job.pk), for_parallel=True)
        payload = frozen.event._compact_context_snapshot["payload"]
        self.assertFalse(hasattr(frozen.event, "_openai_context_snapshot"))
        self.assertEqual(public["system_prompt"], payload["input"][0]["content"])
        self.assertEqual(public["user_prompt"], payload["input"][1]["content"])
        self.assertEqual(public["response_schema"], payload["text"]["format"]["schema"])

    @override_settings(OPENAI_API_KEY="")
    def test_missing_key_preview_and_enqueue_resume_after_private_connection_without_new_run(self):
        run_id = self.bootstrap["run_id"]
        request_key = str(uuid.uuid4())
        secret = "synthetic-openai-key-for-local-tests"
        with (patch.dict(runtime_credentials._entries, {}, clear=True),
                patch("apps.assistant.provider.profile_ready", wraps=provider_profile_ready)):
            for response in (self.preview(provider="openai"), self.post(provider="openai", request_key=request_key)):
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()["code"], "ai_not_configured")
                self.assertNotIn("job_id", response.json())
                self.assertNotIn("credential_ref", response.content.decode())
            self.assertFalse(Job.objects.exists())
            self.assertFalse(AIUsage.objects.exists())
            self.assertFalse(CompactPlanRequest.objects.exists())

            runtime_credentials.set_credential(actor=self.owner, provider="openai", secret=secret)
            preview = self.preview(provider="openai")
            self.assertEqual(preview.status_code, 200, preview.content)
            self.assertEqual(preview.json()["run_id"], run_id)
            self.assertNotIn(secret, preview.content.decode())
            self.assertNotIn("credential_ref", preview.content.decode())
            self.assertFalse(Job.objects.exists())
            self.assertFalse(AIUsage.objects.exists())
            queued = self.post(provider="openai", request_key=request_key)
            self.assertEqual(queued.status_code, 202, queued.content)
            self.assertEqual(self.post(provider="openai", request_key=request_key).json()["job_id"], queued.json()["job_id"])
            self.assertEqual(Job.objects.count(), 1)
            self.assertEqual(AIUsage.objects.count(), 1)
            self.assertEqual(CompactPlanRequest.objects.get().run_id, uuid.UUID(run_id))
            self.assertEqual(CompactPlanRequest.objects.get().context, BASE_CONTEXT)

    @override_settings(OPENAI_API_KEY="")
    def test_missing_key_after_questions_preserves_answers_until_connection_is_restored(self):
        answers = {"q1": "planning", "q2": "case"}
        with (patch.dict(runtime_credentials._entries, {}, clear=True),
                patch("apps.assistant.provider.profile_ready", wraps=provider_profile_ready)):
            runtime_credentials.set_credential(actor=self.owner, provider="openai", secret="synthetic-openai-before-pause")
            parent = self.queue(); self.process(parent, QUESTIONS)
            before_usage = list(AIUsage.objects.order_by("pk").values())
            runtime_credentials.disconnect_credential(actor=self.owner, provider="openai")
            preview = self.preview(parent_job_id=str(parent.pk), answers=answers)
            queued = self.post("answers", parent_job_id=str(parent.pk), answers=answers)
            for response in (preview, queued):
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()["code"], "ai_not_configured")
            self.assertEqual(Job.objects.count(), 1)
            self.assertEqual(before_usage, list(AIUsage.objects.order_by("pk").values()))
            parent.compact_request.refresh_from_db()
            self.assertEqual(parent.compact_request.response, QUESTIONS)

            runtime_credentials.set_credential(actor=self.owner, provider="openai", secret="synthetic-openai-after-pause")
            resumed = self.preview(parent_job_id=str(parent.pk), answers=answers)
            self.assertEqual(resumed.status_code, 200, resumed.content)
            self.assertEqual(resumed.json()["round_number"], 2)
            self.assertEqual(resumed.json()["context"]["answers"], {"focus": "planning", "format": "case"})
            queued = self.post("answers", parent_job_id=str(parent.pk), answers=answers)
            self.assertEqual(queued.status_code, 202, queued.content)
            child = CompactPlanRequest.objects.get(job_id=queued.json()["job_id"])
            self.assertEqual(child.parent.job_id, parent.pk)
            self.assertEqual(child.run_id, parent.compact_request.run_id)
            self.assertEqual(Job.objects.count(), 2)
            self.assertEqual(before_usage, list(AIUsage.objects.filter(job=parent).order_by("pk").values()))

    def test_second_round_inherits_openai_and_review_mode_without_new_provider_flag(self):
        job = self.queue(review_only=True); self.process(job, QUESTIONS)
        parent = job.compact_request
        answers = {"q1": "planning", "q2": "case"}
        preview = self.preview(parent_job_id=str(job.pk), answers=answers)
        self.assertEqual(preview.json()["provider"], "openai")
        self.assertEqual(preview.json()["response_schema"], OPENAI_PROPOSAL_SCHEMA)
        self.assertNotIn("anyOf", preview.json()["response_schema"]["properties"]["result"])
        self.assertNotIn('"state":"questions"', preview.json()["system_prompt"])
        response = self.post("answers", parent_job_id=str(job.pk), answers=answers)
        self.assertEqual(response.status_code, 202, response.content)
        child = Job.objects.get(pk=response.json()["job_id"])
        self.assertEqual(child.ai_usage.snapshot["provider"], "openai")
        self.assertTrue(child.compact_request.review_only)
        processed, remote = self.process(child)
        body = json.loads(remote.call_args.args[0].data)
        self.assertEqual(body["text"]["format"]["schema"], OPENAI_PROPOSAL_SCHEMA)
        self.assertEqual(preview.json()["system_prompt"], body["input"][0]["content"])
        self.assertEqual(processed.result["compact_state"], "private_ready")
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertEqual(self.preview(provider="free", parent_job_id=str(job.pk), answers=answers).status_code, 400)

    def failed_clarification(self):
        parent = self.queue(); self.process(parent, QUESTIONS)
        response = self.post("answers", parent_job_id=str(parent.pk), answers={"q1": "planning", "q2": "case"})
        self.assertEqual(response.status_code, 202, response.content)
        child = Job.objects.get(pk=response.json()["job_id"])
        failed, remote = self.process(child, QUESTIONS)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(remote.call_count, 1)
        return parent, failed

    def new_browser_run(self):
        self.client = Client(); self.client.force_login(self.owner)
        bootstrap = self.client.post(reverse("assistant:pilot_control"), {"operation": "bootstrap"}, content_type="application/json")
        self.assertEqual(bootstrap.status_code, 200, bootstrap.content)
        previous = self.bootstrap["run_id"]
        self.bootstrap = bootstrap.json()
        self.assertNotEqual(previous, self.bootstrap["run_id"])

    def test_repeated_questions_fail_with_finite_diagnostic_and_keep_reported_consumption(self):
        parent, failed = self.failed_clarification()
        self.assertEqual(failed.result["diagnostic"], {"phase": "contract", "code": "compact_invalid"})
        self.assertEqual(self.poll(failed).json()["code"], "compact_invalid")
        self.assertNotIn("questions", json.dumps(failed.result))
        self.assertNotIn("planning", failed.error)
        self.assertEqual(failed.compact_request.response, {})
        self.assertEqual(failed.ai_usage.total_tokens, 1620)
        self.assertEqual(parent.ai_usage.total_tokens, 1620)
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertIsNone(run_one(job_id=failed.pk))

    def test_one_explicit_retry_from_new_browser_preserves_answers_mode_failed_jobs_and_accounting(self):
        from apps.events.templatetags.event_history import event_compact_retry
        parent, failed = self.failed_clarification()
        tag_context = {"request": SimpleNamespace(user=self.owner)}
        self.assertEqual(event_compact_retry(tag_context, self.event), str(failed.pk))
        self.assertEqual(event_compact_retry({"request": SimpleNamespace(user=self.other)}, self.event), "")
        self.assertEqual(event_compact_retry({}, self.event), "")
        old_usage = list(AIUsage.objects.order_by("pk").values())
        old_context = deepcopy(failed.compact_request.context)
        self.new_browser_run()
        preview = self.preview(failed_job_id=str(failed.pk))
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["context"], old_context)
        self.assertEqual(preview.json()["response_schema"], OPENAI_PROPOSAL_SCHEMA)
        self.assertEqual(Job.objects.count(), 2)
        response = self.post("retry", failed_job_id=str(failed.pk))
        self.assertEqual(response.status_code, 202, response.content)
        retry = Job.objects.get(pk=response.json()["job_id"])
        self.assertEqual(retry.compact_request.parent.job_id, failed.pk)
        self.assertEqual(retry.compact_request.round_number, 2)
        self.assertEqual(retry.compact_request.context, old_context)
        self.assertEqual(retry.ai_usage.reserved_usd, Decimal(".017100"))
        self.assertEqual(event_compact_retry(tag_context, self.event), "")
        duplicate = self.post("retry", failed_job_id=str(failed.pk))
        self.assertEqual(duplicate.status_code, 202)
        self.assertEqual(duplicate.json()["job_id"], str(retry.pk))
        self.assertEqual(Job.objects.count(), 3)
        self.assertEqual(old_usage, list(AIUsage.objects.filter(job__in=[parent, failed]).order_by("pk").values()))
        result, remote = self.process(retry)
        self.assertEqual(result.status, "succeeded", result.error)
        body = json.loads(remote.call_args.args[0].data)
        self.assertEqual(preview.json()["system_prompt"], body["input"][0]["content"])
        failed.refresh_from_db(); self.assertEqual(failed.status, "failed")
        self.assertEqual(self.post("retry", failed_job_id=str(retry.pk)).status_code, 400)
        self.new_browser_run()
        self.assertEqual(self.post("retry", failed_job_id=str(failed.pk)).status_code, 400)
        self.assertEqual(Job.objects.count(), 3)

    def test_retry_failure_cannot_spawn_a_retry_chain(self):
        _parent, failed = self.failed_clarification()
        response = self.post("retry", failed_job_id=str(failed.pk))
        retry = Job.objects.get(pk=response.json()["job_id"])
        failed_retry, _ = self.process(retry, QUESTIONS)
        self.assertEqual(failed_retry.status, "failed")
        self.assertEqual(self.post("retry", failed_job_id=str(retry.pk)).status_code, 400)
        duplicate = self.post("retry", failed_job_id=str(failed.pk))
        self.assertEqual(duplicate.json()["job_id"], str(retry.pk))
        self.assertEqual(Job.objects.count(), 3)
        self.assertEqual(AIUsage.objects.count(), 3)

    def test_retry_stale_expired_foreign_or_cancelled_is_rejected_without_new_reservation(self):
        from apps.assistant.compact_planning import retry_source
        _parent, failed = self.failed_clarification()
        self.assertIsNone(retry_source(event=self.event, actor=self.other, failed_job_id=failed.pk))
        self.assertEqual(self.post("retry", failed_job_id=str(failed.pk), answers={}).status_code, 400)
        self.assertEqual(self.post("retry", failed_job_id=str(failed.pk), provider="openai").status_code, 400)
        self.assertEqual(self.post("retry", failed_job_id=str(failed.pk), expected_revision=self.event.revision + 1).status_code, 409)
        CompactPlanRequest.objects.filter(job=failed).update(created_at=timezone.now() - timedelta(hours=3))
        self.assertEqual(self.preview(failed_job_id=str(failed.pk)).status_code, 400)
        self.assertEqual(self.post("retry", failed_job_id=str(failed.pk)).status_code, 400)
        self.assertEqual(Job.objects.count(), 2)
        self.assertEqual(AIUsage.objects.count(), 2)

    def test_retry_respects_remaining_budget_and_never_releases_previous_usage(self):
        _parent, failed = self.failed_clarification()
        before = list(AIUsage.objects.order_by("pk").values())
        AgentGrant.objects.filter(pk=self.grant.pk).update(budget_usd=Decimal(".01"))
        response = self.post("retry", failed_job_id=str(failed.pk))
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Job.objects.count(), 2)
        self.assertEqual(before, list(AIUsage.objects.order_by("pk").values()))

    def test_failed_free_call_does_not_block_explicit_openai_and_same_key_cannot_switch(self):
        free = self.post()
        self.assertEqual(free.status_code, 202, free.content)
        original = Job.objects.get(pk=free.json()["job_id"])
        from apps.assistant.free_harness import FreeHarnessError
        with patch("apps.assistant.free_harness.run_compact_harness", side_effect=FreeHarnessError("quota", http_status=429)):
            failed = run_one(job_id=original.pk)
        self.assertEqual(failed.status, "failed")
        job = self.queue()
        self.assertNotEqual(original.pk, job.pk)
        self.assertEqual(self.post(provider="openai", request_key=original.idempotency_key).status_code, 400)

    def test_global_lifetime_dollar_cap_counts_other_owner_and_prior_month_reservations(self):
        other = get_user_model().objects.create_user(username="other-budget-owner")
        account = AIAccount.objects.create(owner=other, monthly_budget_usd=2)
        event = Event.objects.create(owner=other, title="Budget fixture", is_synthetic=True)
        seed = Job.objects.create(event=event, actor=other, kind="plan", prompt="Old fixture", base_revision=1,
            request_hash="a" * 64, idempotency_key=str(uuid.uuid4()))
        AIUsage.objects.create(job=seed, account=account, month=date(2026, 1, 1), snapshot={"provider": "openai"},
            reserved_input_tokens=100, reserved_output_tokens=100, reserved_usd=Decimal(".99"), status="uncertain")
        response = self.post(provider="openai")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "openai_pilot_budget")
        self.assertEqual(Job.objects.count(), 1)
        self.assertEqual(openai_pilot_summary()["reserved_usd"], Decimal(".99"))

    def test_missing_key_paid_consent_or_small_grant_stops_before_dispatch_without_free_fallback(self):
        with patch("apps.assistant.provider.profile_ready", return_value=False):
            self.assertEqual(self.post(provider="openai").status_code, 400)
        self.assertFalse(Job.objects.exists())
        self.account.paid_enabled = False; self.account.save()
        self.assertEqual(self.post(provider="openai").status_code, 400)
        self.account.paid_enabled = True; self.account.save()
        AgentGrant.objects.filter(pk=self.grant.pk).update(budget_usd=Decimal(".001"))
        self.assertEqual(self.post(provider="openai").status_code, 400)
        self.assertFalse(Job.objects.exists())

    def test_incomplete_or_wrong_native_wrapper_does_not_publish_or_retry(self):
        job = self.queue(); failed, remote = self.process(job, status="incomplete")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(remote.call_count, 1)
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertIsNone(run_one(job_id=job.pk))

    def test_wrong_wrapper_is_accounted_but_not_published(self):
        job = self.queue(); failed, remote = self.process(job, wrapper=False)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(remote.call_count, 1)
        self.assertFalse(PlanCandidate.objects.exists())
        job.ai_usage.refresh_from_db()
        self.assertEqual(job.ai_usage.total_tokens, 1620)

    def test_dispatch_rechecks_global_cap_and_revocation_without_remote_request(self):
        job = self.queue()
        other = get_user_model().objects.create_user(username="dispatch-budget-other")
        account = AIAccount.objects.create(owner=other, monthly_budget_usd=2)
        event = Event.objects.create(owner=other, title="Dispatch budget fixture", is_synthetic=True)
        seed = Job.objects.create(event=event, actor=other, kind="plan", prompt="Old fixture", base_revision=1,
            request_hash="b" * 64, idempotency_key=str(uuid.uuid4()))
        AIUsage.objects.create(job=seed, account=account, month=current_month(), snapshot={"provider": "openai"},
            reserved_input_tokens=100, reserved_output_tokens=100, reserved_usd=Decimal(".99"), status="uncertain")
        with patch("apps.assistant.provider._response") as remote:
            result = run_one(job_id=job.pk)
        remote.assert_not_called()
        self.assertEqual(result.status, "failed")
        job.ai_usage.refresh_from_db(); self.assertEqual(job.ai_usage.status, "released")

    def test_paid_authorization_revoked_after_queue_prevents_dispatch(self):
        job = self.queue()
        self.account.paid_enabled = False; self.account.save()
        with patch("apps.assistant.provider._response") as remote:
            result = run_one(job_id=job.pk)
        remote.assert_not_called()
        self.assertEqual(result.status, "failed")
        job.ai_usage.refresh_from_db(); self.assertEqual(job.ai_usage.status, "released")

    def test_openai_private_archive_has_actual_provider_model_and_exact_native_format(self):
        job = self.queue(review_only=True); self.process(job)
        temporal = Path(settings.BASE_DIR) / "Temporal" / "qa-gica-compact"
        temporal.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="openai-archive-", dir=temporal) as base, override_settings(BASE_DIR=Path(base)):
            result = self.archive(job)
            self.assertEqual(result.status_code, 200, result.content)
            content = json.loads(next(Path(base).rglob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(content["provider"], "openai")
            self.assertEqual(content["model"], "gpt-5.4-mini")
            self.assertEqual(content["public_prompt"]["response_schema"], OPENAI_SCHEMA)
            self.assertEqual(content["response"], PROPOSAL)
            self.assertEqual(self.archive(job).status_code, 200)
        self.assertFalse(PlanCandidate.objects.exists())
