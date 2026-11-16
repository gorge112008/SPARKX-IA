"""Model-scoped synthetic context preparation. No live inference or catalogue."""
import json
from copy import deepcopy
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai_management.models import AIAccount, AIUsage
from apps.directory.models import EventPerson, Person
from apps.events.models import Event
from apps.jobs.models import Job
from apps.planning.models import TaskProgress
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan
from . import provider
from .models import Message


A = "glm-5.3-flash-free"
B = "minimax-m3.1-flash-free"


class ModelContextIsolationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="model-context-owner")
        self.other = users.objects.create_user(username="model-context-other")
        self.account = AIAccount.objects.create(owner=self.owner)
        self.other_account = AIAccount.objects.create(owner=self.other)
        self.event = Event.objects.create(owner=self.owner, title="Encuentro ficticio",
            brief="Ficha declarada por el organizador", is_synthetic=True)

    def profile(self, model=A):
        return {"provider": "opencode", "model": model, "mode": "free",
                "max_input_tokens": 24000, "max_output_tokens": 2048}

    def job(self, *, model=A, kind="chat", prompt="Consulta ficticia A", event=None,
            actor=None, account=None, source="opencode", status="succeeded"):
        event, actor = event or self.event, actor or self.owner
        job = Job.objects.create(event=event, actor=actor, kind=kind, prompt=prompt,
            base_revision=event.revision, request_hash="a" * 64,
            idempotency_key=str(uuid4()), status=status)
        AIUsage.objects.create(job=job, account=account or self.account, month=date(2026, 11, 1),
            snapshot={"provider": source, "model": model}, reserved_input_tokens=100,
            reserved_output_tokens=100, reserved_usd=0, status="settled",
            input_tokens=10, output_tokens=10, total_tokens=20, estimated_cost_usd=0,
            accounting_source="provider")
        return job

    def exchange(self, *, model=A, prompt="Consulta ficticia A", answer="Respuesta ficticia A", **kwargs):
        job = self.job(model=model, prompt=prompt, **kwargs)
        user = Message.objects.create(event=self.event, role="user", content=prompt, request_key=str(job.pk))
        assistant = Message.objects.create(event=self.event, role="assistant", content=answer, job=job)
        job.result = {"message_id": str(assistant.pk)}
        job.save(update_fields=["result"])
        return job, user, assistant

    def freeze(self, *, model=A, action="chat", conversation=None, snapshot=True):
        frozen = provider.freeze_free_context(event=self.event, prompt="Nueva consulta ficticia",
            action=action, conversation=conversation, snapshot=self.profile(model) if snapshot else None)
        self.event._free_context_snapshot = frozen
        return frozen

    def approve(self, *, model=A, manual=False, source="opencode", actor=None, account=None):
        actor = actor or self.owner
        payload = valid_plan()
        payload["summary"] = "Texto exclusivo del modelo " + model
        candidate = create_candidate(event=self.event, actor=self.owner, payload=payload,
            base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)
        if not manual:
            job = self.job(model=model, kind="plan", source=source, actor=actor, account=account)
            job.result = {"candidate_id": str(candidate.pk)}
            job.save(update_fields=["result"])
        plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return plan

    def test_switching_a_to_b_excludes_a_assistant_and_user_messages(self):
        self.exchange()
        self.exchange(model=B, prompt="Consulta B", answer="Respuesta B")
        a_history = self.freeze(model=A)["context"]["history"]
        b_history = self.freeze(model=B)["context"]["history"]
        self.assertEqual(a_history, [{"role": "user", "content": "Consulta ficticia A"},
                                     {"role": "assistant", "content": "Respuesta ficticia A"}])
        self.assertEqual(b_history, [{"role": "user", "content": "Consulta B"},
                                     {"role": "assistant", "content": "Respuesta B"}])

    def test_unknown_manual_and_local_messages_are_not_remote_history(self):
        self.exchange()
        Message.objects.create(event=self.event, role="user", content="Usuario manual sin Job", request_key="remote-legacy")
        Message.objects.create(event=self.event, role="assistant", content="Respuesta manual sin Job")
        _, _, local = self.exchange(prompt="Consulta local", answer="Respuesta local")
        local.request_key = "local:" + str(uuid4())
        local.save(update_fields=["request_key"])
        Message.objects.create(event=self.event, role="assistant", content="Local privado", request_key="local:" + str(uuid4()))
        history = self.freeze()["context"]["history"]
        self.assertEqual([item["content"] for item in history], ["Consulta ficticia A", "Respuesta ficticia A", "Consulta local"])
        self.assertNotIn("manual", json.dumps(history))

    def test_user_message_needs_canonical_job_key_and_exact_normalized_prompt(self):
        _, user, _ = self.exchange()
        user.content = "Contenido manual alterado después del Job"
        user.save(update_fields=["content"])
        other_job = self.job(prompt="Clave sin guiones")
        Message.objects.create(event=self.event, role="user", content=other_job.prompt, request_key=other_job.pk.hex)
        self.assertEqual(self.freeze()["context"]["history"], [{"role": "assistant", "content": "Respuesta ficticia A"}])

    def test_foreign_actor_account_event_and_provider_cannot_supply_history(self):
        self.exchange()
        self.exchange(prompt="Actor ajeno", answer="Respuesta actor ajeno", actor=self.other, account=self.other_account)
        self.exchange(prompt="Cuenta ajena", answer="Respuesta cuenta ajena", account=self.other_account)
        foreign = Event.objects.create(owner=self.other, title="Evento ajeno", brief="Otro contexto", is_synthetic=True)
        self.exchange(prompt="Evento ajeno", answer="Respuesta evento ajeno", event=foreign, actor=self.other, account=self.other_account)
        self.exchange(prompt="Otro proveedor", answer="Respuesta otro proveedor", source="openai")
        self.exchange(prompt="Job fallido", answer="Respuesta no publicada", status="failed")
        self.assertEqual([item["content"] for item in self.freeze()["context"]["history"]],
                         ["Consulta ficticia A", "Respuesta ficticia A"])

    def test_filtering_precedes_eight_message_limit_with_one_history_query(self):
        for index in range(6):
            self.exchange(prompt=f"Consulta A {index}", answer=f"Respuesta A {index}")
        for index in range(12):
            self.exchange(model=B, prompt=f"Consulta B {index}", answer=f"Respuesta B {index}")
            Message.objects.create(event=self.event, role="assistant", content="Manual reciente")
        with self.assertNumQueries(1):
            history = provider._free_history(self.event, {"provider": "opencode", "model": A})
        self.assertEqual(len(history), 8)
        self.assertEqual(history[0]["content"], "Consulta A 2")
        self.assertEqual(history[-1]["content"], "Respuesta A 5")

    def test_only_same_model_job_candidate_revision_chain_includes_approved_plan(self):
        plan = self.approve()
        TaskProgress.objects.create(plan=plan, task_id="t1", status="completed", updated_by=self.owner,
                                    note="Nota privada que nunca se envía")
        a_context = self.freeze(model=A)["context"]["context"]
        self.assertEqual(a_context["approved_plan"], plan.payload)
        self.assertEqual(a_context["task_progress"]["summary"]["completed"], 1)
        b_context = self.freeze(model=B)["context"]["context"]
        self.assertIsNone(b_context["approved_plan"])
        self.assertIsNone(b_context["task_progress"])
        self.assertTrue(a_context["approved_plan_visibility"]["included"])
        self.assertFalse(b_context["approved_plan_visibility"]["included"])
        self.assertNotIn(plan.payload["summary"], json.dumps(b_context, ensure_ascii=False))
        self.assertNotIn("Nota privada", json.dumps(a_context, ensure_ascii=False))

    def test_manual_or_unknown_plan_is_not_attributed_by_human_approval(self):
        self.approve(manual=True)
        frozen = self.freeze(action="plan")
        self.assertIsNone(frozen["context"]["context"]["approved_plan"])
        self.assertIn("su texto se ha omitido", frozen["instructions"])
        self.assertNotIn("Texto exclusivo", json.dumps(frozen["context"], ensure_ascii=False))

    def test_same_candidate_referenced_by_another_actor_does_not_prove_model_source(self):
        self.approve(actor=self.other, account=self.other_account)
        self.assertIsNone(self.freeze()["context"]["context"]["approved_plan"])

    def test_unknown_identity_omits_history_and_plan_even_when_generic_conversation_is_supplied(self):
        self.exchange()
        self.approve()
        supplied = provider.chat_context(self.event)
        self.assertIn("Respuesta ficticia A", json.dumps(supplied))
        frozen = self.freeze(snapshot=False, conversation=supplied)
        self.assertEqual(frozen["context"]["history"], [])
        self.assertIsNone(frozen["context"]["context"]["approved_plan"])

    def test_supplied_conversation_cannot_smuggle_other_model_prose(self):
        self.exchange()
        supplied = {"context": {"event": {"brief": "Texto ajeno inyectado"}, "approved_plan": {"summary": "Otro modelo"}},
                    "history": [{"role": "assistant", "content": "Otro modelo"}]}
        frozen = self.freeze(conversation=supplied)
        self.assertEqual(frozen["context"]["context"]["event"]["brief"], self.event.brief)
        self.assertNotIn("Texto ajeno inyectado", json.dumps(frozen))
        self.assertNotIn("Otro modelo", json.dumps(frozen))

    def test_declared_constraints_and_owned_synthetic_speakers_remain_without_foreign_plan_prose(self):
        self.approve(model=B)
        self.event.interview_answers = {"objective": {"status": "confirmed", "value": "Objetivo declarado por el organizador"}}
        self.event.planning_constraints = {"version": 1,
            "window": {"start": "2026-11-14T09:00:00-05:00", "end": "2026-11-14T10:00:00-05:00"},
            "max_duration_minutes": 60, "speakers": [], "resources": [],
            "sessions": [{"session_id": "s1", "allowed_speakers": [], "allowed_resources": []}], "fixed": []}
        person = Person.objects.create(owner=self.owner, full_name="Ponente ficticio declarado", category="speaker", is_synthetic=True)
        EventPerson.objects.create(event=self.event, person=person, role="speaker")
        frozen = self.freeze(action="plan")
        context = frozen["context"]["context"]
        self.assertIsNone(context["approved_plan"])
        self.assertEqual(context["event"]["planning_constraints"]["window"], self.event.planning_constraints["window"])
        self.assertIn("Objetivo declarado", json.dumps(context, ensure_ascii=False))
        self.assertEqual(context["speaker_candidates"][0]["name"], person.full_name)
        self.assertNotIn("Texto exclusivo del modelo", json.dumps(context, ensure_ascii=False))

    def test_frozen_a_context_cannot_be_reused_for_b_and_dispatch_never_reads_orm(self):
        self.exchange()
        frozen = self.freeze()
        expected = deepcopy(frozen["context"])
        with provider.use_profile(self.profile(A)), patch("apps.assistant.free_harness.run_free_harness") as remote:
            remote.return_value = {"text": "Respuesta nueva", "usage": {}}
            with self.assertNumQueries(0):
                provider.ensure_input_fits(event=self.event, kind="chat", prompt=frozen["prompt"], snapshot=self.profile(A))
                self.assertEqual(provider.answer_question(event=self.event, prompt=frozen["prompt"]), "Respuesta nueva")
            self.assertEqual(remote.call_args.kwargs["context"], expected)
        with provider.use_profile(self.profile(B)), patch("apps.assistant.free_harness.run_free_harness") as remote:
            with self.assertNumQueries(0), self.assertRaises(provider.ProviderError):
                provider.answer_question(event=self.event, prompt=frozen["prompt"])
            remote.assert_not_called()

    def test_generic_api_chat_behavior_is_unchanged(self):
        self.approve(manual=True)
        Message.objects.create(event=self.event, role="assistant", content="Historial legado para API habitual")
        generic = provider.chat_context(self.event)
        self.assertIsNotNone(generic["context"]["approved_plan"])
        self.assertEqual(generic["history"], [{"role": "assistant", "content": "Historial legado para API habitual"}])
