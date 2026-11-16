"""Behavioral tests; PostgreSQL concurrency still needs a dedicated run."""

from datetime import timedelta
from io import StringIO
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from apps.events.models import Event
from apps.events.services import update_event
from apps.ai_management.testing import configure_test_account
from apps.planning.models import PlanCandidate
from apps.jobs.models import Job
from apps.jobs.services import IdempotencyConflict, cancel, claim_next, enqueue, process_claim, run_one


def valid_plan():
    return {"title": "Seminario", "summary": "Propuesta para revisar", "sessions": [], "tasks": [], "risks": []}


@override_settings(OPENAI_API_KEY="test-key-never-used", AI_DAILY_JOB_LIMIT=20, AI_MAX_PENDING_PER_EVENT=5, JOB_LEASE_SECONDS=120)
class JobServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="organizador", password="test-pass-unique")
        self.other = get_user_model().objects.create_user(username="otro", password="test-pass-other")
        configure_test_account(self.owner)
        self.event = Event.objects.create(owner=self.owner, title="Seminario", brief="Evento académico", is_synthetic=True)
        self.usage = patch("apps.assistant.provider.pop_usage", return_value={})
        self.usage.start()
        self.addCleanup(self.usage.stop)

    def enqueue(self, **kwargs):
        params = {"event": self.event, "actor": self.owner, "kind": Job.Kind.PLAN,
                  "prompt": "Prepara un plan de seminario", "idempotency_key": str(uuid.uuid4())}
        params.update(kwargs)
        return enqueue(**params)

    def test_enqueue_captures_snapshot_and_normalizes_prompt(self):
        job = self.enqueue(prompt="  Prepara un seminario  ")
        self.assertEqual(job.prompt, "Prepara un seminario")
        self.assertEqual(job.base_revision, self.event.revision)
        self.assertIsNone(job.base_plan_id)
        self.assertEqual(job.status, Job.Status.QUEUED)
        self.assertEqual(job.attempt, 0)

    @override_settings(AI_DAILY_JOB_LIMIT=1, AI_MAX_PENDING_PER_EVENT=1)
    def test_idempotent_retry_does_not_reconsume_budget_or_change_snapshot(self):
        first = self.enqueue(idempotency_key="retry")
        update_event(event_id=self.event.pk, actor=self.owner, title="Título corregido")
        second = self.enqueue(idempotency_key="retry")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.base_revision, 1)
        self.assertEqual(Job.objects.count(), 1)

    def test_key_cannot_be_reused_with_different_content(self):
        self.enqueue(idempotency_key="same-key")
        with self.assertRaises(IdempotencyConflict):
            self.enqueue(idempotency_key="same-key", prompt="Otro contenido de solicitud")
        with self.assertRaises(IdempotencyConflict):
            self.enqueue(idempotency_key="same-key", kind=Job.Kind.CHAT)
        self.assertEqual(Job.objects.count(), 1)

    def test_other_event_owner_cannot_enqueue_or_cancel(self):
        with self.assertRaises(PermissionDenied):
            self.enqueue(actor=self.other)
        job = self.enqueue()
        with self.assertRaises(PermissionDenied):
            cancel(job_id=job.pk, actor=self.other)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.QUEUED)

    def test_inactive_actor_cannot_enqueue(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.enqueue()
        self.assertFalse(Job.objects.exists())

    def test_deactivated_owner_cannot_cancel_using_stale_authenticated_object(self):
        job = self.enqueue()
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertTrue(self.owner.is_active)
        with self.assertRaises(PermissionDenied):
            cancel(job_id=job.pk, actor=self.owner)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.QUEUED)

    @override_settings(OPENAI_API_KEY="")
    def test_missing_provider_configuration_rejects_without_job(self):
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "ai_not_configured")
        self.assertFalse(Job.objects.exists())

    def test_invalid_requests_are_rejected(self):
        cases = [{"prompt": "ab"}, {"prompt": "x" * 6001}, {"prompt": None},
                 {"idempotency_key": ""}, {"idempotency_key": "x" * 129}, {"kind": "approval"}]
        for values in cases:
            with self.subTest(values=list(values)):
                with self.assertRaises(ValidationError):
                    self.enqueue(**values)
        self.assertFalse(Job.objects.exists())

    @override_settings(AI_DAILY_JOB_LIMIT=1)
    def test_daily_quota_applies_across_events(self):
        self.enqueue()
        second = Event.objects.create(owner=self.owner, title="Segundo", brief="Otro evento", is_synthetic=True)
        with self.assertRaises(ValidationError) as caught:
            self.enqueue(event=second)
        self.assertEqual(caught.exception.code, "daily_budget")

    @override_settings(AI_MAX_PENDING_PER_EVENT=1)
    def test_cancel_releases_pending_capacity_but_not_daily_count(self):
        first = self.enqueue()
        with self.assertRaises(ValidationError) as caught:
            self.enqueue()
        self.assertEqual(caught.exception.code, "pending_budget")
        cancelled = cancel(job_id=first.pk, actor=self.owner)
        self.assertEqual(cancelled.status, Job.Status.CANCELLED)
        second = self.enqueue()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Job.objects.filter(actor=self.owner).count(), 2)

    @patch("apps.assistant.provider.generate_plan", side_effect=lambda **kwargs: valid_plan())
    def test_plan_success_creates_candidate_without_approving(self, generate):
        job = self.enqueue()
        result = run_one()
        self.assertEqual(result.pk, job.pk)
        self.assertEqual(result.status, Job.Status.SUCCEEDED)
        self.assertEqual(PlanCandidate.objects.count(), 1)
        self.assertEqual(str(PlanCandidate.objects.get().pk), result.result["candidate_id"])
        self.event.refresh_from_db()
        self.assertIsNone(self.event.active_plan_id)
        generate.assert_called_once()

    @patch("apps.assistant.provider.answer_question", return_value="Falta confirmar el horario.")
    def test_chat_success_persists_one_message_and_usage(self, answer):
        from apps.assistant.models import Message
        with patch("apps.assistant.provider.pop_usage", return_value={"input_tokens": 40, "output_tokens": 7, "total_tokens": 47, "raw": "discard"}):
            job = self.enqueue(kind=Job.Kind.CHAT)
            result = run_one()
        message = Message.objects.get(job=job)
        self.assertEqual(message.role, "assistant")
        self.assertEqual(message.content, "Falta confirmar el horario.")
        self.assertEqual(result.result["usage"], {"input_tokens": 40, "output_tokens": 7, "total_tokens": 47})
        self.assertEqual(result.result["message_id"], str(message.pk))
        answer.assert_called_once()

    @patch("apps.assistant.provider.generate_plan")
    def test_stale_job_is_stopped_before_provider_call(self, generate):
        job = self.enqueue()
        update_event(event_id=self.event.pk, actor=self.owner, title="Nueva versión")
        result = run_one()
        self.assertEqual(result.status, Job.Status.STALE)
        generate.assert_not_called()
        self.assertFalse(PlanCandidate.objects.exists())

    def test_change_during_generation_discards_result(self):
        self.enqueue()
        def change_event(**kwargs):
            update_event(event_id=self.event.pk, actor=self.owner, title="Cambió durante la llamada")
            return valid_plan()
        with patch("apps.assistant.provider.generate_plan", side_effect=change_event):
            result = run_one()
        self.assertEqual(result.status, Job.Status.STALE)
        self.assertFalse(PlanCandidate.objects.exists())

    def test_cancel_during_generation_revokes_late_result(self):
        from apps.assistant.models import Message
        job = self.enqueue(kind=Job.Kind.CHAT)
        def cancel_call(**kwargs):
            cancel(job_id=job.pk, actor=self.owner)
            return "Esta respuesta llega después de cancelar."
        with patch("apps.assistant.provider.answer_question", side_effect=cancel_call):
            result = run_one()
        self.assertEqual(result.status, Job.Status.CANCELLED)
        self.assertIsNone(result.claim_token)
        self.assertFalse(Message.objects.filter(job=job).exists())

    @patch("apps.assistant.provider.generate_plan")
    def test_inactive_requester_is_stopped_before_call(self, generate):
        self.enqueue()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        generate.assert_not_called()

    def test_owner_change_during_generation_blocks_publication(self):
        self.enqueue()
        def change_owner(**kwargs):
            Event.objects.filter(pk=self.event.pk).update(owner=self.other)
            return valid_plan()
        with patch("apps.assistant.provider.generate_plan", side_effect=change_owner):
            result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertFalse(PlanCandidate.objects.exists())

    @patch("apps.assistant.provider.generate_plan")
    def test_expired_attempt_is_failed_without_auto_retry(self, generate):
        self.enqueue()
        claim = claim_next()
        Job.objects.filter(pk=claim.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(claim_next())
        claim.refresh_from_db()
        self.assertEqual(claim.status, Job.Status.FAILED)
        self.assertEqual(claim.attempt, 1)
        self.assertIsNone(claim.claim_token)
        generate.assert_not_called()

    def test_lease_expiry_during_call_blocks_result(self):
        job = self.enqueue()
        def expire(**kwargs):
            Job.objects.filter(pk=job.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
            return valid_plan()
        with patch("apps.assistant.provider.generate_plan", side_effect=expire):
            result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertFalse(PlanCandidate.objects.exists())

    @patch("apps.assistant.provider.generate_plan", side_effect=lambda **kwargs: valid_plan())
    def test_reprocessing_old_claim_does_not_duplicate_effect(self, generate):
        self.enqueue()
        claim = claim_next()
        process_claim(claim)
        result = process_claim(claim)
        self.assertEqual(result.status, Job.Status.SUCCEEDED)
        self.assertEqual(PlanCandidate.objects.count(), 1)
        generate.assert_called_once()

    @patch("apps.assistant.provider.generate_plan")
    def test_revoked_claim_token_cannot_execute_or_change_running_job(self, generate):
        self.enqueue()
        claim = claim_next()
        replacement_token = uuid.uuid4()
        Job.objects.filter(pk=claim.pk).update(claim_token=replacement_token)
        result = process_claim(claim)
        self.assertEqual(result.status, Job.Status.RUNNING)
        self.assertEqual(result.claim_token, replacement_token)
        self.assertFalse(PlanCandidate.objects.exists())
        generate.assert_not_called()

    def test_sequential_claims_do_not_take_the_same_job(self):
        self.enqueue()
        self.enqueue()
        first, second = claim_next(), claim_next()
        self.assertNotEqual(first.pk, second.pk)
        self.assertNotEqual(first.claim_token, second.claim_token)
        self.assertIsNone(claim_next())
        # This is a sequential behavior test, not a concurrency benchmark.

    @patch("apps.assistant.provider.generate_plan", side_effect=RuntimeError("Bearer private-secret-and-input"))
    def test_provider_failure_is_sanitized_and_usage_can_be_recorded(self, generate):
        self.enqueue()
        with patch("apps.assistant.provider.pop_usage", return_value={"input_tokens": 15, "output_tokens": 0, "total_tokens": 15}):
            result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertNotIn("private-secret", result.error)
        self.assertNotIn("Bearer", result.error)
        self.assertEqual(result.result["usage"]["total_tokens"], 15)
        self.assertFalse(PlanCandidate.objects.exists())

    @patch("apps.assistant.provider.generate_plan", return_value=["unexpected payload"])
    def test_invalid_output_type_does_not_publish(self, generate):
        self.enqueue()
        result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertFalse(PlanCandidate.objects.exists())

    @patch("apps.assistant.provider.generate_plan", side_effect=lambda **kwargs: valid_plan())
    def test_failed_publication_rolls_back_candidate_and_job_result(self, generate):
        from apps.planning.services import create_candidate
        self.enqueue()
        def fail_after_write(**kwargs):
            create_candidate(**kwargs)
            raise ValidationError("Fallo controlado después de guardar")
        with patch("apps.planning.services.create_candidate", side_effect=fail_after_write):
            result = run_one()
        self.assertEqual(result.status, Job.Status.FAILED)
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertNotIn("candidate_id", result.result)

    def test_cancel_is_idempotent_and_terminal_success_cannot_be_cancelled(self):
        job = self.enqueue()
        cancel(job_id=job.pk, actor=self.owner)
        again = cancel(job_id=job.pk, actor=self.owner)
        self.assertEqual(again.status, Job.Status.CANCELLED)
        second = self.enqueue()
        with patch("apps.assistant.provider.generate_plan", return_value=valid_plan()):
            done = run_one()
        with self.assertRaises(ValidationError):
            cancel(job_id=done.pk, actor=self.owner)
        self.assertEqual(second.pk, done.pk)

    @override_settings(JOB_MAX_ATTEMPTS=2)
    def test_exhausted_queued_job_is_failed_not_left_pending(self):
        job = self.enqueue()
        Job.objects.filter(pk=job.pk).update(attempt=2)
        self.assertIsNone(claim_next())
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.FAILED)

    def test_command_once_terminates_with_no_jobs(self):
        stdout, stderr = StringIO(), StringIO()
        call_command("runjobs", once=True, stdout=stdout, stderr=stderr)
        self.assertEqual(stdout.getvalue(), "")
        if connection.vendor == "sqlite":
            self.assertIn("un solo worker", stderr.getvalue())


@override_settings(OPENAI_API_KEY="test-key-never-used", AI_DAILY_JOB_LIMIT=20, AI_MAX_PENDING_PER_EVENT=5)
class ProviderTransactionBoundaryTests(TransactionTestCase):
    def test_provider_call_is_outside_database_transaction(self):
        owner = get_user_model().objects.create_user(username="boundary-owner", password="boundary-password")
        configure_test_account(owner)
        event = Event.objects.create(owner=owner, title="Evento", brief="Evento de prueba", is_synthetic=True)
        enqueue(event=event, actor=owner, kind=Job.Kind.PLAN, prompt="Prepara una propuesta", idempotency_key="boundary")
        def check_boundary(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            return valid_plan()
        with patch("apps.assistant.provider.generate_plan", side_effect=check_boundary), patch("apps.assistant.provider.pop_usage", return_value={}):
            result = run_one()
        self.assertEqual(result.status, Job.Status.SUCCEEDED)


@skipUnlessDBFeature("has_select_for_update_skip_locked")
@override_settings(OPENAI_API_KEY="test-key-never-used", AI_DAILY_JOB_LIMIT=1, AI_MAX_PENDING_PER_EVENT=5)
class PostgreSQLJobConcurrencyTests(TransactionTestCase):
    """Skipped on SQLite: exercise row locks with independent connections."""

    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="postgres-owner", password="postgres-password")
        configure_test_account(self.owner)
        self.first_event = Event.objects.create(owner=self.owner, title="Primero", brief="Prueba concurrente", is_synthetic=True)
        self.second_event = Event.objects.create(owner=self.owner, title="Segundo", brief="Prueba concurrente", is_synthetic=True)

    @override_settings(AI_DAILY_JOB_LIMIT=20)
    def test_worker_skips_a_queued_row_locked_by_another_connection(self):
        from concurrent.futures import ThreadPoolExecutor
        first = enqueue(event=self.first_event, actor=self.owner, kind=Job.Kind.PLAN, prompt="Prepara una propuesta", idempotency_key="locked")
        second = enqueue(event=self.second_event, actor=self.owner, kind=Job.Kind.PLAN, prompt="Prepara otra propuesta", idempotency_key="unlocked")
        def independent_claim():
            try:
                claim = claim_next()
                return None if claim is None else claim.pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic():
                Job.objects.select_for_update().get(pk=first.pk)
                claimed_id = executor.submit(independent_claim).result(timeout=10)
                self.assertEqual(claimed_id, second.pk)
        first.refresh_from_db()
        self.assertEqual(first.status, Job.Status.QUEUED)

    def test_daily_limit_serializes_concurrent_requests_across_events(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        start = Barrier(2)
        def independent_enqueue(event_id):
            try:
                actor = get_user_model().objects.get(pk=self.owner.pk)
                event = Event.objects.get(pk=event_id)
                start.wait(timeout=10)
                try:
                    enqueue(event=event, actor=actor, kind=Job.Kind.PLAN,
                            prompt="Genera un seminario", idempotency_key=str(event_id))
                    return "accepted"
                except ValidationError as exc:
                    return exc.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(independent_enqueue, event.pk) for event in (self.first_event, self.second_event)]
            outcomes = [future.result(timeout=15) for future in futures]
        self.assertCountEqual(outcomes, ["accepted", "daily_budget"])
        self.assertEqual(Job.objects.count(), 1)
