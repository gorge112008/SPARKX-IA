"""Frozen, source-scoped Responses requests and private stage observers; no network."""
import io
import json
from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ai_management.models import AIUsage
from apps.ai_management.testing import configure_test_account
from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.services import enqueue, run_one
from apps.planning.models import TaskProgress
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan
from . import provider
from .models import Message


MINI = "gpt-5.4-mini"
LUNA = "gpt-6-luna"


@override_settings(OPENAI_API_KEY="synthetic-test-key-not-a-credential")
class OpenAIContextIsolationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="openai-context-owner")
        self.other = get_user_model().objects.create_user(username="openai-context-other")
        self.account = configure_test_account(self.owner, budget="1", token_limit=200000)
        self.profile = self.account.active_profile
        self.profile.model = MINI
        self.profile.output_rate = Decimal("4.50")
        self.profile.save(update_fields=["model", "output_rate"])
        self.event = Event.objects.create(owner=self.owner, title="Piloto ficticio",
            brief="Datos sintéticos declarados, sin mensajes a terceros", is_synthetic=True)
        self.addCleanup(provider.pop_usage)

    def snapshot(self, model=MINI):
        return {"provider": "openai", "model": model, "mode": "paid",
                "max_input_tokens": 24000, "max_output_tokens": 2500}

    def source_job(self, *, model=MINI, source="openai", kind="chat", prompt="Consulta acreditada"):
        job = Job.objects.create(event=self.event, actor=self.owner, kind=kind, prompt=prompt,
            status="succeeded", base_revision=self.event.revision, request_hash="a" * 64,
            idempotency_key=str(uuid4()))
        AIUsage.objects.create(job=job, account=self.account, month=date(2026, 11, 1),
            snapshot={"provider": source, "model": model}, reserved_input_tokens=100,
            reserved_output_tokens=100, reserved_usd=0, status="settled", input_tokens=10,
            output_tokens=10, total_tokens=20, estimated_cost_usd=0, accounting_source="provider")
        return job

    def exchange(self, *, model=MINI, source="openai", content="Respuesta acreditada"):
        job = self.source_job(model=model, source=source, prompt="Pregunta de " + model)
        Message.objects.create(event=self.event, role="user", content=job.prompt, request_key=str(job.pk))
        Message.objects.create(event=self.event, role="assistant", content=content, job=job)

    def approved_plan(self, *, model=MINI, source="openai", manual=False):
        payload = valid_plan()
        payload["summary"] = "Resumen exclusivo de " + source + "/" + model
        candidate = create_candidate(event=self.event, actor=self.owner, payload=payload,
            base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)
        if not manual:
            job = self.source_job(model=model, source=source, kind="plan")
            job.result = {"candidate_id": str(candidate.pk)}
            job.save(update_fields=["result"])
        plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return plan

    def freeze(self, *, model=MINI, action="chat", prompt="Consulta nueva"):
        frozen = provider.freeze_openai_context(event=self.event, prompt=prompt, action=action,
                                                snapshot=self.snapshot(model))
        self.event._openai_context_snapshot = frozen
        return frozen

    def content(self, frozen):
        return json.loads(frozen["payload"]["input"][1]["content"])

    def response(self, text="Respuesta sintética"):
        return io.BytesIO(json.dumps({"status": "completed", "output": [{"type": "message",
            "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}).encode())

    def test_openai_history_excludes_opencode_other_openai_model_unknown_and_local(self):
        self.exchange(content="Mini propio")
        self.exchange(model=LUNA, content="Luna ajeno")
        self.exchange(model="glm-5.3-flash-free", source="opencode", content="GLM ajeno")
        Message.objects.create(event=self.event, role="assistant", content="Manual desconocido")
        Message.objects.create(event=self.event, role="assistant", content="Local privado", request_key="local:" + str(uuid4()))
        content = self.content(self.freeze())
        self.assertEqual(content["history"], [{"role": "user", "content": "Pregunta de " + MINI},
                                               {"role": "assistant", "content": "Mini propio"}])
        self.assertEqual(content["context"]["event"]["brief"], self.event.brief)

    def test_only_matching_job_candidate_revision_plan_and_human_progress_are_included(self):
        plan = self.approved_plan()
        TaskProgress.objects.create(plan=plan, task_id="t1", status="completed", updated_by=self.owner,
                                    note="Nota privada innecesaria")
        same = self.content(self.freeze())
        self.assertEqual(same["context"]["approved_plan"], plan.payload)
        self.assertEqual(same["context"]["task_progress"]["summary"]["completed"], 1)
        other = self.content(self.freeze(model=LUNA))
        self.assertIsNone(other["context"]["approved_plan"])
        self.assertIsNone(other["context"]["task_progress"])
        self.assertNotIn(plan.payload["summary"], json.dumps(other))
        self.assertNotIn("Nota privada", json.dumps(same))

    def test_opencode_and_manually_approved_plans_are_omitted_from_openai(self):
        for manual, source in ((True, "openai"), (False, "opencode")):
            with self.subTest(manual=manual, source=source):
                self.approved_plan(model=MINI, source=source, manual=manual)
                frozen = self.freeze(action="plan")
                self.assertIsNone(self.content(frozen)["context"]["approved_plan"])
                self.assertIn("cuyo texto se ha omitido", frozen["payload"]["input"][0]["content"])

    def test_plan_preflight_and_dispatch_reuse_one_frozen_body_with_zero_orm(self):
        frozen = self.freeze(action="plan")
        expected = deepcopy(frozen["payload"])
        self.event.brief = "Cambio posterior que no debe filtrarse a este envío"
        self.event._planning_snapshot = {"ignored_after_freeze": "No volver a leer"}
        with provider.use_profile(self.snapshot()), patch("apps.assistant.provider._opener.open", return_value=self.response(json.dumps(valid_plan()))) as remote:
            with self.assertNumQueries(0):
                provider.ensure_input_fits(event=self.event, kind="plan", prompt=frozen["prompt"], snapshot=self.snapshot())
                self.assertEqual(provider.generate_plan(event=self.event, prompt=frozen["prompt"]), valid_plan())
        self.assertEqual(json.loads(remote.call_args.args[0].data), expected)

    def test_chat_preflight_and_dispatch_ignore_unqualified_supplied_conversation(self):
        self.exchange(content="Texto Mini acreditado")
        frozen = self.freeze()
        unsafe = {"context": {"event": {"brief": "Texto ajeno"}}, "history": [{"role": "assistant", "content": "Respuesta ajena"}]}
        with provider.use_profile(self.snapshot()), patch("apps.assistant.provider._opener.open", return_value=self.response()) as remote:
            with self.assertNumQueries(0):
                provider.ensure_input_fits(event=self.event, kind="chat", prompt=frozen["prompt"], snapshot=self.snapshot(), conversation=unsafe)
                provider.answer_question(event=self.event, prompt=frozen["prompt"], conversation=unsafe)
        self.assertEqual(json.loads(remote.call_args.args[0].data), frozen["payload"])
        self.assertNotIn("Respuesta ajena", json.dumps(frozen["payload"]))

    def test_changed_model_prompt_action_event_revision_or_limits_stops_before_http(self):
        frozen = self.freeze()
        cases = [(self.snapshot(LUNA), "Consulta nueva", "chat"),
                 (self.snapshot(), "Otro texto", "chat"),
                 (self.snapshot(), "Consulta nueva", "plan"),
                 ({**self.snapshot(), "max_output_tokens": 100}, "Consulta nueva", "chat")]
        for profile, prompt, kind in cases:
            with self.subTest(profile=profile["model"], prompt=prompt, kind=kind), provider.use_profile(profile), patch("apps.assistant.provider._opener.open") as remote:
                with self.assertRaises(provider.ProviderError):
                    provider.ensure_input_fits(event=self.event, kind=kind, prompt=prompt, snapshot=profile)
                remote.assert_not_called()
        self.event.revision += 1
        with provider.use_profile(self.snapshot()), patch("apps.assistant.provider._opener.open") as remote:
            with self.assertRaises(provider.ProviderError):
                provider.answer_question(event=self.event, prompt=frozen["prompt"])
            remote.assert_not_called()

    def test_worker_freezes_openai_plan_and_chat_before_preflight_and_dispatch(self):
        for kind in ("plan", "chat"):
            with self.subTest(kind=kind):
                job = enqueue(event=self.event, actor=self.owner, kind=kind,
                    prompt="Preparar ejemplo controlado " + kind, idempotency_key=str(uuid4()))
                original = provider.ensure_input_fits
                observed = []
                def preflight(**kwargs):
                    observed.append(deepcopy(kwargs["event"]._openai_context_snapshot["payload"]))
                    return original(**kwargs)
                text = json.dumps(valid_plan()) if kind == "plan" else "Respuesta controlada"
                with patch("apps.assistant.provider.chat_context", side_effect=AssertionError("Generic history must not prepare an OpenAI Job")), \
                     patch("apps.assistant.provider.ensure_input_fits", side_effect=preflight), \
                     patch("apps.assistant.provider._opener.open", return_value=self.response(text)) as remote:
                    result = run_one()
                self.assertEqual(result.pk, job.pk)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(json.loads(remote.call_args.args[0].data), observed[0])

    def test_observer_reports_only_real_boundary_names_and_restores_after_scope(self):
        stages = []
        with provider.use_profile(self.snapshot()), provider.observe_requests(stages.append), patch("apps.assistant.provider._opener.open", return_value=self.response()):
            provider._response({"model": MINI})
        self.assertEqual(stages, ["request_started", "response_received"])
        provider._notify_request("request_started")
        self.assertEqual(len(stages), 2)

    def test_failing_pre_request_observer_prevents_network(self):
        def failed(stage):
            raise RuntimeError("Trace unavailable")
        with provider.use_profile(self.snapshot()), provider.observe_requests(failed), patch("apps.assistant.provider._opener.open") as remote:
            with self.assertRaisesMessage(RuntimeError, "Trace unavailable"):
                provider._response({"model": MINI})
            remote.assert_not_called()

    def test_failing_post_response_observer_preserves_reported_usage(self):
        def failed(stage):
            if stage == "response_received":
                raise RuntimeError("Post-response trace unavailable")
        with provider.use_profile(self.snapshot()), provider.observe_requests(failed), patch("apps.assistant.provider._opener.open", return_value=self.response()) as remote:
            with self.assertRaisesMessage(RuntimeError, "Post-response trace unavailable"):
                provider._response({"model": MINI})
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(provider.pop_usage(), {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30})

    def test_nested_observer_failure_restores_outer_without_leaking_callbacks(self):
        outer, inner = [], []
        with provider.observe_requests(outer.append):
            provider._notify_request("request_started")
            with self.assertRaises(RuntimeError):
                with provider.observe_requests(inner.append):
                    provider._notify_request("request_started")
                    raise RuntimeError("Controlled failure")
            provider._notify_request("response_received")
        provider._notify_request("request_started")
        self.assertEqual(outer, ["request_started", "response_received"])
        self.assertEqual(inner, ["request_started"])
