"""Real local scheduler, fake transport: no provider, secret or active DB use."""
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
import json
import threading
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.backends.utils import CursorWrapper
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.ai_management.models import AIAccount, AIProfile, AIUsage, OpenAIPilotLock
from apps.ai_management.testing import configure_test_account
from apps.ai_management.agent_access import update_agent_grant
from apps.ai_management.free_pool import configure_entry, gateway_state, record_quota_failure
from apps.ai_management.catalog import catalog_entry
from apps.assistant import provider
from apps.assistant.models import Message
from apps.assistant.execution import in_agent_execution
from apps.events.models import Event
from .management.commands import runromeo
from .models import Job
from .services import (InferenceResult, cancel, claim_next, enqueue, finish_inference,
                       perform_inference, prepare_claim)
from .trace import observe_stage


class _Receipt:
    def __init__(self, model): self.model = model
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, maximum):
        numbers = (11, 7) if self.model == "gpt-5.4-mini" else (23, 5)
        return json.dumps({"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": "Synthetic reply " + self.model}]}], "usage": {
            "input_tokens": numbers[0], "output_tokens": numbers[1], "total_tokens": sum(numbers),
            "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}).encode()


@override_settings(OPENAI_API_KEY="synthetic-key-no-network", AI_DAILY_JOB_LIMIT=100, AI_MAX_PENDING_PER_EVENT=10,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ParallelInferenceTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="parallel-fictitious-owner")
        self.account = configure_test_account(self.owner)
        self.luna = self.account.active_profile
        self.mini = AIProfile.objects.create(owner=self.owner, name="Synthetic mini", provider="openai", mode="paid",
            model="gpt-5.4-mini", input_rate="0.75", cached_rate="0.075", output_rate="4.50",
            max_input_tokens=24000, max_output_tokens=2500)
        OpenAIPilotLock.objects.get_or_create(pk=1)
        self.first_event = Event.objects.create(owner=self.owner, title="Fictional ALPHA context", brief="Synthetic ALPHA only", is_synthetic=True)
        self.second_event = Event.objects.create(owner=self.owner, title="Fictional BETA context", brief="Synthetic BETA only", is_synthetic=True)

    def queue(self, profile, event):
        self.account.active_profile = profile; self.account.save()
        return enqueue(event=event, actor=self.owner, kind="chat", prompt="Review this fictional event",
                       idempotency_key=str(uuid.uuid4()))

    @contextmanager
    def scheduler(self, transport, *, expected=2, stopped_after_first=None):
        """Coordinator uses the isolated shared-memory test DB; remote SQL fails."""
        command = runromeo.Command(stdout=StringIO(), stderr=StringIO())
        command.owner_id = self.owner.pk
        command.stop_worker = threading.Event(); command.worker = None
        phase_threads, phase_overlap, executions = [], [], []
        phase_lock = threading.Lock()
        active_phases = 0
        finished = threading.Event()
        blocked_selection = threading.Event()
        original_execute = CursorWrapper.execute
        original_prepare, original_finish = runromeo.prepare_claim, runromeo.finish_inference
        original_observe, original_next = runromeo.observe_stage, runromeo.next_controlled_job

        def execute(cursor, sql, params=None):
            if threading.current_thread().name.startswith("romeo-inference"):
                raise AssertionError("Remote inference thread attempted ORM/SQL")
            return original_execute(cursor, sql, params)

        def phase(function):
            def call(*args, **kwargs):
                nonlocal active_phases
                with phase_lock:
                    active_phases += 1
                    phase_threads.append(threading.get_ident())
                    if active_phases != 1: phase_overlap.append(active_phases)
                try:
                    result = function(*args, **kwargs)
                    if function is original_finish:
                        executions.append(result)
                        if stopped_after_first and len(executions) == 1: stopped_after_first.set()
                        if len(executions) == expected:
                            command.stop_worker.set(); finished.set()
                    return result
                finally:
                    with phase_lock: active_phases -= 1
            return call

        def choose(*args, **kwargs):
            result = original_next(*args, **kwargs)
            if kwargs.get("excluded_events") and result is None: blocked_selection.set()
            return result

        with (patch.object(CursorWrapper, "execute", execute),
              patch.object(runromeo, "prepare_claim", side_effect=phase(original_prepare)),
              patch.object(runromeo, "finish_inference", side_effect=phase(original_finish)),
              patch.object(runromeo, "observe_stage", side_effect=phase(original_observe)),
              patch.object(runromeo, "next_controlled_job", side_effect=choose),
              patch("apps.assistant.provider._opener.open", side_effect=transport)):
            command.on_server_started()
            try:
                yield command, finished, blocked_selection, executions
            finally:
                command.stop_worker.set()
                command.worker.join(timeout=15)
        self.assertFalse(command.worker.is_alive(), "Coordinator did not join its remote calls")
        self.assertFalse(phase_overlap)
        self.assertEqual(len(set(phase_threads)), 1, "DB phases ran on different worker threads")

    def two_calls(self, *, fail_mini=False, while_active=None):
        first = self.queue(self.mini, self.first_event)
        second = self.queue(self.luna, self.second_event)
        barrier = threading.Barrier(2)
        started = threading.Event(); release = threading.Event()
        lock = threading.Lock()
        observed = {}

        def transport(request, **kwargs):
            payload = json.loads(request.data)
            model = payload["model"]
            current = provider._configuration()
            self.assertTrue(in_agent_execution())
            self.assertEqual(current["model"], model)
            self.assertFalse(threading.current_thread().name == "romeo-1-coordinator")
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertIn("ALPHA" if model == "gpt-5.4-mini" else "BETA", serialized)
            self.assertNotIn("BETA" if model == "gpt-5.4-mini" else "ALPHA", serialized)
            with lock: observed[model] = threading.get_ident()
            barrier.wait(timeout=8)
            started.set()
            if not release.wait(8): raise AssertionError("Synthetic transport release missing")
            if fail_mini and model == "gpt-5.4-mini": raise TimeoutError
            return _Receipt(model)

        try:
            with self.scheduler(transport) as (command, finished, _, results):
                self.assertTrue(started.wait(8), "The two independent calls did not overlap")
                self.assertEqual(len(set(observed.values())), 2)
                if while_active: while_active(first, second)
                release.set()
                self.assertTrue(finished.wait(8), command.stderr.getvalue())
        finally: release.set()
        return Job.objects.get(pk=first.pk), Job.objects.get(pk=second.pk)

    def test_two_frozen_calls_overlap_but_all_db_phases_are_serial_and_contexts_private(self):
        first, second = self.two_calls()
        self.assertEqual((first.status, second.status), ("succeeded", "succeeded"))
        self.assertEqual((first.ai_usage.input_tokens, first.ai_usage.output_tokens), (11, 7))
        self.assertEqual((second.ai_usage.input_tokens, second.ai_usage.output_tokens), (23, 5))
        self.assertEqual(first.ai_usage.snapshot["model"], "gpt-5.4-mini")
        self.assertEqual(second.ai_usage.snapshot["model"], "gpt-6-luna")
        self.assertEqual(Message.objects.count(), 2)
        self.assertFalse(in_agent_execution())

    def test_one_parallel_failure_retains_unknown_usage_without_other_models_counters(self):
        first, second = self.two_calls(fail_mini=True)
        self.assertEqual(first.status, "failed")
        self.assertEqual(first.ai_usage.status, "uncertain")
        self.assertIsNone(first.ai_usage.total_tokens)
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(second.ai_usage.total_tokens, 28)
        self.assertEqual(AIUsage.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 1)

    def test_cancellation_during_parallel_call_accounts_late_usage_without_publication(self):
        first, second = self.two_calls(while_active=lambda first, second: cancel(job_id=first.pk, actor=self.owner))
        self.assertEqual(first.status, "cancelled")
        self.assertEqual(first.ai_usage.status, "settled")
        self.assertEqual(first.ai_usage.total_tokens, 18)
        self.assertEqual(second.status, "succeeded")
        self.assertFalse(Message.objects.filter(job=first).exists())

    def test_expired_parallel_claim_accounts_late_usage_and_does_not_retry(self):
        def expire(first, second):
            Job.objects.filter(pk=first.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        first, second = self.two_calls(while_active=expire)
        self.assertEqual(first.status, "failed")
        self.assertEqual(first.ai_usage.status, "settled")
        self.assertEqual(first.ai_usage.total_tokens, 18)
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(first.attempt, 1)

    def serial_slots(self, *, same_event=False):
        first = self.queue(self.mini, self.first_event)
        second = self.queue(self.luna if same_event else self.mini,
                            self.first_event if same_event else self.second_event)
        started = threading.Event(); release = threading.Event()
        calls = []
        def transport(request, **kwargs):
            calls.append(json.loads(request.data)["model"])
            if len(calls) == 1:
                started.set()
                if not release.wait(8): raise AssertionError("Missing release")
            return _Receipt(calls[-1])
        try:
            with self.scheduler(transport) as (command, finished, blocked, _):
                self.assertTrue(started.wait(8))
                self.assertTrue(blocked.wait(8), "Scheduler did not apply its local exclusion slot")
                self.assertEqual(len(calls), 1)
                release.set()
                self.assertTrue(finished.wait(8), command.stderr.getvalue())
        finally: release.set()
        self.assertEqual(len(calls), 2)
        self.assertEqual(Job.objects.get(pk=first.pk).status, "succeeded")
        self.assertEqual(Job.objects.get(pk=second.pk).status, "succeeded")

    def test_same_provider_model_waits_for_its_local_slot(self): self.serial_slots()
    def test_same_event_waits_even_when_models_differ(self): self.serial_slots(same_event=True)

    def test_shutdown_waits_for_both_remote_calls_and_their_settlement(self):
        self.queue(self.mini, self.first_event); self.queue(self.luna, self.second_event)
        barrier = threading.Barrier(2)
        both_started = threading.Event(); first_release = threading.Event(); second_release = threading.Event()
        first_settled = threading.Event(); stopped = threading.Event()
        def transport(request, **kwargs):
            model = json.loads(request.data)["model"]
            barrier.wait(timeout=8); both_started.set()
            release = first_release if model == "gpt-5.4-mini" else second_release
            if not release.wait(8): raise AssertionError("Synthetic shutdown release missing")
            return _Receipt(model)
        stopper = None
        try:
            with self.scheduler(transport, stopped_after_first=first_settled) as (command, finished, _, _):
                self.assertTrue(both_started.wait(8))
                def stop():
                    command.on_server_stopping(); stopped.set()
                stopper = threading.Thread(target=stop)
                stopper.start()
                self.assertTrue(command.stop_worker.wait(2))
                self.assertFalse(stopped.is_set())
                first_release.set()
                self.assertTrue(first_settled.wait(8))
                self.assertFalse(stopped.is_set(), "Shutdown returned while the second call was still active")
                second_release.set()
                self.assertTrue(stopped.wait(8))
                self.assertTrue(finished.is_set())
        finally:
            first_release.set(); second_release.set()
            if stopper: stopper.join(timeout=10)
        self.assertEqual(AIUsage.objects.filter(status="settled").count(), 2)

    def test_result_cannot_be_settled_against_another_prepared_claim(self):
        job = self.queue(self.mini, self.first_event)
        prepared = prepare_claim(claim_next(job_id=job.pk), for_parallel=True)
        wrong = InferenceResult(uuid.uuid4(), prepared.token, usage={"input_tokens": 11, "output_tokens": 7})
        with self.assertRaises(ValidationError): finish_inference(prepared, wrong)
        self.assertEqual(AIUsage.objects.get(job=job).status, "dispatched")
        self.assertIsNone(AIUsage.objects.get(job=job).total_tokens)

    def test_cancellation_before_remote_phase_prevents_call_via_fenced_observer(self):
        job = self.queue(self.mini, self.first_event)
        prepared = prepare_claim(claim_next(job_id=job.pk), for_parallel=True)
        cancel(job_id=job.pk, actor=self.owner)
        with patch("apps.assistant.provider._opener.open") as transport:
            result = perform_inference(prepared, observer=lambda stage: observe_stage(prepared.job_id, prepared.token, stage))
        transport.assert_not_called()
        final = finish_inference(prepared, result)
        self.assertEqual(final.status, "cancelled")
        self.assertEqual(final.ai_usage.status, "uncertain")

    def free_calls(self, *, quota_failure=False):
        """Exercise the actual approved pool and adapter with only its CLI mocked."""
        from apps.assistant.free_harness import FreeHarnessError
        admin = get_user_model().objects.create_user(username="parallel-pool-human", is_superuser=True)
        grant = update_agent_grant(actor=admin, account=self.account, expected_version=0, name="Romeo-1",
            enabled=True, budget_usd=1, primary_profile=self.mini, free_pool_enabled=True)
        for preset in ("opencode_demo", "opencode_deepseek"):
            grant.refresh_from_db()
            configure_entry(actor=admin, account=self.account, expected_grant_version=grant.version, preset=preset,
                enabled=True, roles="chat", priority=10, daily_request_limit=5, daily_token_limit=100000, accept_policy=True,
                expected_policy_fingerprint=catalog_entry(preset)["model_policy_version"])
        barrier = threading.Barrier(2)
        models = []
        def free_transport(**kwargs):
            model = kwargs["model"]
            self.assertEqual(provider._configuration()["model"], model)
            self.assertTrue(in_agent_execution())
            context = json.dumps(kwargs["context"], ensure_ascii=False)
            self.assertIn("ALPHA" if model == "glm-5.3-flash-free" else "BETA", context)
            self.assertNotIn("BETA" if model == "glm-5.3-flash-free" else "ALPHA", context)
            models.append(model)
            barrier.wait(timeout=8)
            if quota_failure and model == "glm-5.3-flash-free":
                raise FreeHarnessError("Synthetic quota only", phase="inference", code="quota_or_rate_limit", http_status=429)
            return {"text": "Synthetic free reply " + model, "payload": None,
                    "usage": {"input_tokens": 14, "output_tokens": 6, "total_tokens": 20}}
        def forbidden_http(*args, **kwargs):
            raise AssertionError("No HTTP transport is allowed in this synthetic free test")
        with (patch("apps.assistant.provider.profile_ready", return_value=True),
              patch("apps.assistant.free_harness.run_free_harness", side_effect=free_transport)):
            first = self.queue(self.mini, self.first_event)
            second = self.queue(self.mini, self.second_event)
            with self.scheduler(forbidden_http) as (command, finished, _, _):
                self.assertTrue(finished.wait(10), command.stderr.getvalue())
        self.assertCountEqual(models, ["glm-5.3-flash-free", "deepseek-v4.1-flash-free"])
        self.assertEqual(len(models), 2)
        return Job.objects.get(pk=first.pk), Job.objects.get(pk=second.pk)

    def test_two_approved_free_models_overlap_without_remote_orm_or_context_mixture(self):
        first, second = self.free_calls()
        self.assertEqual((first.status, second.status), ("succeeded", "succeeded"))
        self.assertEqual((first.ai_usage.total_tokens, second.ai_usage.total_tokens), (20, 20))
        self.assertEqual((first.ai_usage.reserved_usd, second.ai_usage.reserved_usd), (0, 0))

    def test_parallel_free_429_sets_cooldown_and_keeps_own_unknown_hold_without_retry(self):
        first, second = self.free_calls(quota_failure=True)
        self.assertEqual(first.status, "failed")
        self.assertIn("429", first.error)
        self.assertEqual(first.ai_usage.status, "uncertain")
        self.assertIsNone(first.ai_usage.total_tokens)
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(second.ai_usage.total_tokens, 20)
        self.assertTrue(gateway_state(self.account)[1])
        self.assertEqual(AIUsage.objects.count(), 2)

    def test_persisted_gateway_cooldown_blocks_legacy_opencode_after_memory_reload(self):
        free = AIProfile.objects.create(owner=self.owner, name="Synthetic legacy free", provider="opencode",
            model="glm-5.3-flash-free", mode="free", free_tier_confirmed=True,
            max_input_tokens=24000, max_output_tokens=2048)
        record_quota_failure(account_id=self.account.pk, snapshot={"provider": "opencode"})
        self.account = AIAccount.objects.get(pk=self.account.pk)
        self.assertTrue(gateway_state(self.account)[1])
        with patch("apps.assistant.provider.profile_ready", return_value=True):
            with self.assertRaises(ValidationError) as caught:
                self.queue(free, self.first_event)
        self.assertEqual(caught.exception.code, "free_gateway_cooldown")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
