"""Real persisted task observations with a fake HTTP boundary; no live inference."""

import io
import json
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ai_management.models import AIUsage
from apps.ai_management.testing import configure_test_account
from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.services import cancel, enqueue, run_one
from apps.planning.models import TaskProgress, TaskProgressChange
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.task_progress import update_task_progress

from . import provider
from .models import Message


def task_plan(*, purpose="Preparar la demostración"):
    return {
        "title": "Plan aprobado", "summary": "Falta confirmar la fecha",
        "sessions": [], "risks": ["Fecha pendiente"],
        "tasks": [{
            "id": f"t{number}", "title": f"Tarea {number}", "purpose": purpose,
            "depends_on": [], "status": "pending",
        } for number in range(1, 4)],
    }


@override_settings(OPENAI_API_KEY="test-only-key", OPENAI_MODEL="gpt-6-luna")
class ChatTaskContextTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="task-chat-owner")
        self.other = users.objects.create_user(username="task-chat-other")
        self.account = configure_test_account(self.owner)
        self.event = Event.objects.create(
            owner=self.owner, title="Seminario", brief="Evento de demostración, fecha pendiente",
            is_synthetic=True,
        )
        self.plan = self.approve(self.event, self.owner)
        remote = patch("apps.assistant.provider._opener.open", side_effect=self.reply)
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(provider.pop_usage)

    def reply(self, *_args, **_kwargs):
        return io.BytesIO(json.dumps({
            "status": "completed", "output": [{
                "type": "message", "content": [{
                    "type": "output_text", "text": "Según la instantánea, revisa la preparación.",
                }],
            }], "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
        }).encode())

    def approve(self, event, actor, payload=None):
        candidate = create_candidate(
            event=event, actor=actor, payload=payload or task_plan(),
            base_revision=event.revision, base_plan_id=event.active_plan_id,
        )
        plan = approve_candidate(candidate_id=candidate.pk, actor=actor)
        event.refresh_from_db()
        return plan

    def progress(self, task_id, status, *, version=0, note=""):
        return update_task_progress(
            event=self.event, actor=self.owner, plan_id=self.plan.pk, task_id=task_id,
            status=status, expected_version=version, request_key=uuid.uuid4(), note=note,
        )

    def request_content(self):
        payload = json.loads(self.remote.call_args.args[0].data)
        self.assertNotIn("tools", payload)
        return json.loads(payload["input"][1]["content"]), payload["input"][0]["content"]

    def ask(self):
        provider.answer_question(event=self.event, prompt="¿Cómo va la preparación?")
        return self.request_content()

    def enqueue_chat(self):
        return enqueue(
            event=self.event, actor=self.owner, kind=Job.Kind.CHAT,
            prompt="¿Cómo va la preparación?", idempotency_key=str(uuid.uuid4()),
        )

    def test_chat_observes_states_versions_and_percentage_without_writing(self):
        running = self.progress("t1", "in_progress", note="Nota privada innecesaria")
        completed = self.progress("t2", "completed", note="Declaración humana de ejemplo")
        counts = (TaskProgress.objects.count(), TaskProgressChange.objects.count())

        content, instructions = self.ask()

        context = content["context"]
        progress = context["task_progress"]
        self.assertEqual(progress["plan_id"], str(self.plan.pk))
        self.assertEqual(progress["plan_version"], self.plan.version)
        self.assertEqual(progress["source"], "human_declaration")
        self.assertFalse(progress["independently_verified"])
        self.assertEqual(progress["summary"], {
            "total": 3, "not_started": 1, "in_progress": 1, "completed": 1, "percentage": 33,
        })
        self.assertEqual(progress["tasks"], [{
            "id": "t1", "status": "in_progress", "version": 1,
            "updated_at": running.updated_at.isoformat(), "recorded": True,
        }, {
            "id": "t2", "status": "completed", "version": 1,
            "updated_at": completed.updated_at.isoformat(), "recorded": True,
        }, {
            "id": "t3", "status": "not_started", "version": 0,
            "updated_at": None, "recorded": False,
        }])
        self.assertIsNone(context["event"]["starts_at"])
        self.assertEqual(context["approved_plan"]["tasks"][1]["status"], "pending")
        self.assertIn("instantánea tomada al preparar", instructions)
        self.assertIn("sin verificación independiente", instructions)
        self.assertIn("no modifica el plan ni los estados", instructions)
        encoded = json.dumps(content, ensure_ascii=False)
        self.assertNotIn("Nota privada innecesaria", encoded)
        self.assertNotIn(self.owner.username, encoded)
        self.assertEqual(counts, (TaskProgress.objects.count(), TaskProgressChange.objects.count()))

    def test_context_excludes_other_events_and_historical_progress(self):
        self.progress("t1", "completed", note="Sólo pertenece al plan anterior")
        self.plan = self.approve(self.event, self.owner, task_plan(purpose="Cambió el alcance"))
        foreign = Event.objects.create(owner=self.other, title="Evento ajeno", brief="Privado")
        foreign_plan = self.approve(foreign, self.other)
        update_task_progress(
            event=foreign, actor=self.other, plan_id=foreign_plan.pk, task_id="t1",
            status="completed", expected_version=0, request_key=uuid.uuid4(), note="Ajeno",
        )
        Message.objects.create(event=foreign, role="user", content="Historial privado ajeno")

        content, _instructions = self.ask()

        progress = content["context"]["task_progress"]
        self.assertEqual(progress["plan_id"], str(self.plan.pk))
        self.assertEqual(progress["summary"]["completed"], 0)
        self.assertTrue(all(not task["recorded"] for task in progress["tasks"]))
        self.assertNotIn("Historial privado ajeno", json.dumps(content))

    def test_unapproved_proposal_has_no_execution_progress(self):
        self.event = Event.objects.create(owner=self.owner, title="Nuevo evento", brief="Pendiente")
        candidate = create_candidate(
            event=self.event, actor=self.owner, payload=task_plan(purpose="Propuesta pendiente"),
            base_revision=self.event.revision,
        )

        content, instructions = self.ask()

        self.assertIsNone(content["context"]["approved_plan"])
        self.assertIsNone(content["context"]["task_progress"])
        self.assertNotIn(str(candidate.pk), json.dumps(content))
        self.assertNotIn("Propuesta pendiente", json.dumps(content))
        self.assertIn("sin plan aprobado no hay avance", instructions)

    def test_new_request_reads_saved_progress_and_does_not_trust_old_chat(self):
        Message.objects.create(event=self.event, role="assistant", content="Todo está completado")
        first, _instructions = self.ask()
        self.progress("t1", "completed", note="Preparación declarada")

        second, instructions = self.ask()

        self.assertEqual(first["context"]["task_progress"]["summary"]["completed"], 0)
        self.assertEqual(second["context"]["task_progress"]["summary"]["completed"], 1)
        self.assertIn("historial puede estar desactualizado", instructions)

    def test_worker_reuses_preflight_observation_when_task_changes(self):
        # Persist explicit same-model provenance. Human approval alone must not
        # make a manual plan eligible for a remote model's isolated context.
        source = Job.objects.create(
            event=self.event, actor=self.owner, kind=Job.Kind.PLAN,
            prompt="Propuesta sintética acreditada", status=Job.Status.SUCCEEDED,
            base_revision=self.event.revision, request_hash="a" * 64,
            idempotency_key=str(uuid.uuid4()), result={"candidate_id": str(self.plan.candidate_id)},
        )
        AIUsage.objects.create(
            job=source, account=self.account, month=date(2026, 11, 1),
            snapshot={"provider": "openai", "model": self.account.active_profile.model},
            reserved_input_tokens=100, reserved_output_tokens=100, reserved_usd=0,
            status=AIUsage.Status.SETTLED, input_tokens=10, output_tokens=10,
            total_tokens=20, estimated_cost_usd=0, accounting_source="provider",
        )
        self.progress("t1", "in_progress")
        job = self.enqueue_chat()
        original = provider.ensure_input_fits
        observed = []

        def after_preflight(**kwargs):
            result = original(**kwargs)
            frozen = kwargs["event"]._openai_context_snapshot["payload"]
            observed.append(json.loads(frozen["input"][1]["content"]))
            self.progress("t1", "completed", version=1, note="Completada tras preparar consulta")
            return result

        with patch("apps.assistant.provider.ensure_input_fits", side_effect=after_preflight):
            result = run_one()

        content, _instructions = self.request_content()
        self.assertEqual(result.pk, job.pk)
        self.assertEqual(result.status, Job.Status.SUCCEEDED)
        self.assertEqual(content["context"], observed[0]["context"])
        self.assertEqual(content["history"], observed[0]["history"])
        self.assertEqual(content["context"]["task_progress"]["tasks"][0]["status"], "in_progress")
        self.assertEqual(TaskProgress.objects.get(plan=self.plan, task_id="t1").status, "completed")
        self.assertTrue(Message.objects.filter(job=job).exists())
        self.assertEqual(self.remote.call_count, 1)
        latest, _instructions = self.ask()
        self.assertEqual(latest["context"]["task_progress"]["tasks"][0]["status"], "completed")

    def test_cancellation_fences_response_without_changing_progress(self):
        self.progress("t1", "in_progress")
        job = self.enqueue_chat()

        def cancel_during_call(*args, **kwargs):
            cancel(job_id=job.pk, actor=self.owner)
            return self.reply(*args, **kwargs)

        self.remote.side_effect = cancel_during_call
        result = run_one()

        self.assertEqual(result.status, Job.Status.CANCELLED)
        self.assertFalse(Message.objects.filter(job=job).exists())
        self.assertEqual(TaskProgress.objects.get(plan=self.plan, task_id="t1").status, "in_progress")
        self.assertEqual(self.remote.call_count, 1)

    def test_revoked_owner_stops_before_reading_chat_context_or_calling_provider(self):
        job = self.enqueue_chat()
        Event.objects.filter(pk=self.event.pk).update(owner=self.other)

        with patch("apps.assistant.provider.chat_context", wraps=provider.chat_context) as context:
            result = run_one()

        self.assertEqual(result.pk, job.pk)
        self.assertEqual(result.status, Job.Status.FAILED)
        context.assert_not_called()
        self.remote.assert_not_called()
        self.assertFalse(Message.objects.filter(job=job).exists())
