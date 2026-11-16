"""Compact protocol and real HTTP/worker integration with mocked inference only."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import tempfile
from unittest.mock import patch
import uuid
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.ai_management.agent_access import update_agent_grant
from apps.ai_management.free_pool import configure_entry
from apps.ai_management.models import AIAccount, AIProfile, AIUsage, AgentPoolEntry, FreeGatewayState
from apps.directory.services import upsert_organization, upsert_person
from apps.events.models import Event
from apps.events.services import update_event
from apps.jobs.models import Job
from apps.jobs.services import enqueue, claim_next, prepare_claim, perform_inference, finish_inference, run_one
from apps.jobs.management.commands.runromeo import next_controlled_job
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate
from tools.opencode.catalog import policy_fingerprint
from apps.assistant.compact_contract import BASE_CONTEXT, validate_context, validate_response
from apps.assistant.compact_planning import enqueue_compact
from apps.assistant.execution import agent_execution
from apps.assistant.free_harness import FreeHarnessError, run_compact_harness, run_free_harness
from apps.assistant.models import CompactPlanRequest, CompactRequestCancellation
from apps.assistant.pilot_workflow import SESSION_KEY, PILOT_TITLE

PROPOSAL = {"v": 1, "state": "proposal", "agenda": [
    {"topic": "Planificación del mantenimiento", "min": 35, "speaker": "p1", "resource": "r1"},
    {"topic": "Caso práctico y preguntas", "min": 55, "speaker": "p1", "resource": "r1"}],
    "preparation": [{"task": "Preparar presentación", "after": []}, {"task": "Revisar el caso práctico", "after": [1]}],
    "communications": [{"type": "invitation", "text": "Participa en el seminario de mantenimiento."}]}
QUESTIONS = {"v": 1, "state": "questions", "questions": [
    {"id": "q1", "field": "focus", "options": ["planning", "assets", "performance"]},
    {"id": "q2", "field": "format", "options": ["talk", "case"]}]}

# Authored test output, never presented as a measured remote inference.
SEMINAR_PREPARATION = [
    {"task": "Acordar con el ponente el objetivo del seminario de mantenimiento", "after": []},
    {"task": "Preparar un caso anonimizado de planificación del mantenimiento", "after": [1]},
    {"task": "Preparar las diapositivas de estrategia y criticidad de activos", "after": [1]},
    {"task": "Completar la guía del caso con indicadores de mantenimiento", "after": [2]},
    {"task": "Revisar con el ponente contenido y tiempos del caso", "after": [3, 4]},
    {"task": "Comprobar el acceso y permisos de presentación de la sala virtual", "after": []},
    {"task": "Redactar la invitación con el objetivo y la dinámica del seminario", "after": [1]},
    {"task": "Revisar las instrucciones de acceso y participación", "after": [6]},
    {"task": "Ensayar audio y pantalla con los materiales revisados", "after": [5, 6]},
    {"task": "Revisar la pauta de moderación y turnos de preguntas tras el ensayo", "after": [9]},
]


class CompactContractTests(SimpleTestCase):
    def test_exact_contract_accepts_both_discriminated_results(self):
        self.assertEqual(validate_response(PROPOSAL), PROPOSAL)
        self.assertEqual(validate_response(QUESTIONS), QUESTIONS)
        self.assertEqual(validate_context(BASE_CONTEXT), BASE_CONTEXT)

    def test_expanded_preparation_preserves_legacy_rows_and_checks_new_dependencies(self):
        data = deepcopy(PROPOSAL)
        data["preparation"] = deepcopy(SEMINAR_PREPARATION[:3])
        self.assertEqual(validate_response(data), data)
        data["preparation"] = deepcopy(SEMINAR_PREPARATION)
        self.assertEqual(validate_response(data), data)
        for deps in ([10], [11], [True], [9, 9], [1, 2, 3, 4, 5, 6]):
            invalid = deepcopy(data)
            invalid["preparation"][-1]["after"] = deps
            with self.subTest(deps=deps), self.assertRaises(ValidationError):
                validate_response(invalid)
        data["preparation"].append({"task": "Tarea fuera del límite", "after": []})
        with self.assertRaises(ValidationError):
            validate_response(data)

    def test_new_generation_requires_substantive_preparation_without_a_larger_token_limit(self):
        from apps.assistant.compact_contract import OPENAI_SCHEMA, OPENAI_PROPOSAL_SCHEMA, instructions_for, MAX_OUTPUT_TOKENS
        for proposal_schema in (OPENAI_SCHEMA["properties"]["result"]["anyOf"][1],
                OPENAI_PROPOSAL_SCHEMA["properties"]["result"]):
            preparation = proposal_schema["properties"]["preparation"]
            self.assertEqual((preparation["minItems"], preparation["maxItems"]), (8, 10))
            self.assertEqual(preparation["items"]["properties"]["after"]["items"]["maximum"], 9)
            communications = proposal_schema["properties"]["communications"]
            self.assertEqual((communications["minItems"], communications["maxItems"]), (3, 3))
        for answers in ({}, {"focus": "planning", "material": "case"}):
            context = deepcopy(BASE_CONTEXT)
            context["answers"] = answers
            prompt = instructions_for(context, openai=True)
            self.assertIn("entre 8 y 10 tareas", prompt)
            self.assertIn("seminario virtual de mantenimiento", prompt)
            self.assertIn("material elegido en answers", prompt)
            self.assertIn("entregable o una comprobación observable", prompt)
            self.assertIn("dependencias reales", prompt)
            self.assertIn("Exactamente 3 comunicaciones", prompt)
            self.assertNotIn("De 1 a 6 tareas", prompt)
        self.assertEqual(MAX_OUTPUT_TOKENS, 1800)

    def test_change_context_exports_only_symbolic_roles_and_durations(self):
        from apps.assistant.compact_contract import instructions_for
        context = deepcopy(BASE_CONTEXT)
        context["change"] = {"kind": "more_case_time", "base_agenda": [
            {"min": 35, "role": "content"}, {"min": 35, "role": "case"}, {"min": 20, "role": "questions"}]}
        self.assertEqual(validate_context(context), context)
        prompt = instructions_for(context, openai=True)
        self.assertIn("Es la entrega final", prompt)
        self.assertIn("en 5 minutos respecto al original", prompt)
        self.assertNotIn('"state":"questions"', prompt)
        changes = [
            {"kind": "other"}, {"name": "Private person"},
            {"base_agenda": [{"min": 90, "role": "case"}]},
            {"base_agenda": [{"min": 45, "role": "case"}, {"min": 45, "role": "case"}]},
            {"base_agenda": [{"min": 40, "role": "case"}, {"min": 45, "role": "questions"}]},
            {"base_agenda": [{"min": True, "role": "case"}, {"min": 89, "role": "questions"}]},
            {"base_agenda": [{"min": 45, "role": "Private person"}, {"min": 45, "role": "questions"}]},
            {"base_agenda": [{"min": 45, "role": "case", "topic": "Private title"}, {"min": 45, "role": "questions"}]},
        ]
        for mutation in changes:
            invalid = deepcopy(context)
            invalid["change"].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                validate_context(invalid)

    def test_extra_fields_booleans_unknown_ids_wrong_sums_and_cycles_rejected(self):
        cases = []
        for mutation in ({"risks": []}, {"v": True}, {"state": "other"}):
            cases.append(PROPOSAL | mutation)
        for key, value in (("min", True), ("min", 34), ("speaker", "Robert"), ("resource", "Zoom"), ("topic", "x" * 91)):
            data = deepcopy(PROPOSAL); data["agenda"][0][key] = value; cases.append(data)
        for deps in ([1], [True], [2]):
            data = deepcopy(PROPOSAL); data["preparation"][0]["after"] = deps; cases.append(data)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValidationError): validate_response(data)

    def test_questions_are_catalogued_unique_and_second_round_cannot_ask_again(self):
        with self.assertRaises(ValidationError): validate_response(QUESTIONS, round_number=2)
        for field in ("email", "name", "open_question"):
            data = deepcopy(QUESTIONS); data["questions"][0]["field"] = field
            with self.assertRaises(ValidationError): validate_response(data)
        data = deepcopy(QUESTIONS); data["questions"] *= 3
        with self.assertRaises(ValidationError): validate_response(data)

    def test_closed_export_rejects_identity_free_text_and_arbitrary_preferences(self):
        for mutation in ({"name": "Private person"}, {"topic": "Other topic"}, {"answers": {"focus": "private free text"}}, {"speakers": ["real-uuid"]}):
            with self.assertRaises(ValidationError): validate_context(BASE_CONTEXT | mutation)

    def test_harness_never_relabels_real_context_as_synthetic(self):
        with patch("apps.assistant.free_harness._run_harness", return_value={}) as run:
            run_compact_harness(context=BASE_CONTEXT, model="glm-5.3-flash-free")
        self.assertFalse(run.call_args.kwargs["synthetic"])
        self.assertTrue(run.call_args.kwargs["minimized"])
        self.assertEqual(run.call_args.kwargs["max_output_tokens"], 1800)
        with patch("apps.assistant.free_harness._run_harness") as run:
            with self.assertRaises(FreeHarnessError): run_compact_harness(context=BASE_CONTEXT, model="big-pickle")
            with self.assertRaises(FreeHarnessError): run_free_harness(context=BASE_CONTEXT, instructions="test", action="plan", max_input_tokens=12000, max_output_tokens=1800, synthetic=False)
        run.assert_not_called()


class CompactWorkflowTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="compact-owner", is_superuser=True)
        self.other = users.create_user(username="compact-other")
        self.reviewer = users.create_user(username="compact-reviewer")
        for person, role in ((self.owner, "admin"), (self.other, "organizer"), (self.reviewer, "reviewer")):
            PortalAccount.objects.create(user=person, role=role)
        self.client.force_login(self.owner)
        bootstrap = self.client.post(reverse("assistant:pilot_control"), {"operation": "bootstrap"}, content_type="application/json")
        self.assertEqual(bootstrap.status_code, 200, bootstrap.content)
        self.bootstrap = bootstrap.json()
        org = upsert_organization(actor=self.owner, name="Gicaingenieros")
        upsert_person(actor=self.owner, full_name="Jorge Gayoso", category="speaker", organization_id=org.pk)
        self.bootstrap = self.client.post(reverse("assistant:pilot_control"), {"operation": "bootstrap"}, content_type="application/json").json()
        values = {key: value for key, value in self.bootstrap["fields"].items() if key not in {"date", "time"}}
        values.update(organization_id=str(org.pk), scheduled_dates="19/11/2026", starts_at="2026-11-19T19:30")
        created = self.client.post(reverse("assistant:pilot_control"), {"operation": "create", "run_id": self.bootstrap["run_id"], "fields": values}, content_type="application/json")
        self.assertEqual(created.status_code, 201, created.content)
        self.event = Event.objects.get(pk=created.json()["event_id"])
        self.profile = AIProfile.objects.create(owner=self.owner, name="Free fixture", provider="opencode", model="glm-5.3-flash-free",
            mode="free", free_tier_confirmed=True, max_input_tokens=24000, max_output_tokens=2048)
        self.account = AIAccount.objects.create(owner=self.owner, active_profile=self.profile, monthly_token_limit=1000000)
        self.grant = update_agent_grant(actor=self.owner, account=self.account, expected_version=0, name="Gica-1", enabled=True,
            budget_usd=0, primary_profile=self.profile, free_pool_enabled=True, free_pool_for_plans=True)
        self.entry = configure_entry(actor=self.owner, account=self.account, expected_grant_version=self.grant.version, preset="opencode_demo",
            enabled=True, roles="plan", priority=1, daily_request_limit=10, daily_token_limit=300000, accept_policy=True,
            expected_policy_fingerprint=policy_fingerprint(self.profile.model))
        ready = patch("apps.assistant.provider.profile_ready", return_value=True); ready.start(); self.addCleanup(ready.stop)
        self.remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No remote call")); mock = self.remote.start()
        self.addCleanup(self.remote.stop); self.addCleanup(mock.assert_not_called)
        self.url = reverse("assistant:pilot_ai")

    def post(self, operation="start", **changes):
        data = {"operation": operation, "run_id": self.bootstrap["run_id"], "event_id": str(self.event.pk),
            "expected_revision": self.event.revision, "request_key": str(uuid.uuid4())}
        data.update(changes)
        return self.client.post(self.url, data, content_type="application/json")

    def queue(self):
        response = self.post(); self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(response.json()["status"], "queued")
        return Job.objects.get(pk=response.json()["job_id"])

    def process(self, job, output=PROPOSAL):
        usage = {"input_tokens": 700, "output_tokens": 200, "total_tokens": 900}
        with patch("apps.assistant.free_harness.run_compact_harness", return_value={"payload": deepcopy(output), "usage": usage}) as mocked:
            result = run_one(job_id=job.pk)
        return result, mocked

    def poll(self, job):
        return self.client.get(self.url, {"job_id": str(job.pk), "run_id": self.bootstrap["run_id"]})

    def test_queued_real_event_no_call_no_paid_then_worker_proposes_with_mechanical_hours(self):
        job = self.queue()
        self.assertFalse(self.event.is_synthetic)
        self.assertEqual(job.ai_usage.reserved_usd, 0)
        self.assertEqual(job.ai_usage.snapshot["provider"], "opencode")
        self.assertEqual(job.ai_usage.reserved_output_tokens, 1800)
        self.assertEqual(job.ai_usage.reserved_input_tokens, 12000)
        self.assertIsNone(self.event.active_plan_id)
        result, mocked = self.process(job)
        self.assertEqual(result.status, "succeeded", result.error)
        self.assertEqual(mocked.call_count, 1)
        sent = mocked.call_args.kwargs
        self.assertEqual(sent["context"], BASE_CONTEXT)
        self.assertEqual(sent["max_output_tokens"], 1800)
        self.assertNotIn("Gicaingenieros", json.dumps(sent))
        self.assertNotIn("Castillo", json.dumps(sent))
        self.assertNotIn(str(self.event.pk), json.dumps(sent))
        candidate = PlanCandidate.objects.get()
        self.assertFalse(candidate.validation)
        self.assertEqual(candidate.payload["sessions"][0]["start"], "2026-11-19T19:30:00-05:00")
        self.assertEqual(candidate.payload["sessions"][1]["start"], "2026-11-19T20:05:00-05:00")
        self.assertEqual(candidate.payload["tasks"][1]["depends_on"], ["t1"])
        self.assertEqual(candidate.payload["risks"], [])
        self.assertEqual(PlanRevision.objects.count(), 0)
        polled = self.poll(job).json()
        self.assertEqual(polled["status"], "proposal")
        self.assertEqual(polled["communications"], PROPOSAL["communications"])
        job.ai_usage.refresh_from_db(); self.assertEqual(job.ai_usage.total_tokens, 900)

    def test_ten_task_seminar_preserves_model_content_and_all_tasks_begin_pending(self):
        proposal = deepcopy(PROPOSAL)
        proposal["preparation"] = deepcopy(SEMINAR_PREPARATION)
        result, _ = self.process(self.queue(), proposal)
        self.assertEqual(result.status, "succeeded", result.error)
        candidate = PlanCandidate.objects.get()
        tasks = candidate.payload["tasks"]
        self.assertEqual([task["title"] for task in tasks], [row["task"] for row in SEMINAR_PREPARATION])
        self.assertEqual({task["status"] for task in tasks}, {"pending"})
        self.assertEqual(tasks[5]["depends_on"], [])
        self.assertEqual(tasks[8]["depends_on"], ["t5", "t6"])
        self.assertEqual(tasks[9]["depends_on"], ["t9"])
        self.assertFalse(candidate.validation)

    def test_questions_are_persisted_then_all_answers_form_one_second_call(self):
        job = self.queue(); result, _ = self.process(job, QUESTIONS)
        self.assertEqual(result.status, "succeeded")
        questions = self.poll(job).json()
        self.assertEqual(questions["status"], "questions")
        self.assertEqual(len(questions["questions"]), 2)
        self.assertEqual(PlanCandidate.objects.count(), 0)
        response = self.post("answers", parent_job_id=str(job.pk), answers={"q1": "assets", "q2": "case"})
        self.assertEqual(response.status_code, 202, response.content)
        child = Job.objects.get(pk=response.json()["job_id"])
        result, mocked = self.process(child)
        self.assertEqual(result.status, "succeeded", result.error)
        self.assertEqual(mocked.call_args.kwargs["context"]["answers"], {"focus": "assets", "format": "case"})
        self.assertEqual(Job.objects.count(), 2)
        self.assertEqual(PlanCandidate.objects.count(), 1)

    def test_partial_answers_free_text_duplicate_or_third_round_never_dispatch(self):
        job = self.queue(); self.process(job, QUESTIONS)
        for answers in ({"q1": "assets"}, {"q1": "private text", "q2": "case"}, {"q1": "assets", "q2": "case", "q3": "other"}):
            self.assertEqual(self.post("answers", parent_job_id=str(job.pk), answers=answers).status_code, 400)
        response = self.post("answers", parent_job_id=str(job.pk), answers={"q1": "assets", "q2": "case"})
        child = Job.objects.get(pk=response.json()["job_id"])
        result, _ = self.process(child, QUESTIONS)
        self.assertEqual(result.status, "failed")
        self.assertEqual(self.post("answers", parent_job_id=str(child.pk), answers={}).status_code, 400)
        self.assertEqual(Job.objects.count(), 2)

    def test_repeated_start_even_new_key_reuses_same_request_and_worker_cannot_send_twice(self):
        job = self.queue(); duplicate = self.post()
        self.assertEqual(duplicate.json()["job_id"], str(job.pk))
        self.process(job)
        with patch("apps.assistant.free_harness.run_compact_harness") as remote:
            self.assertIsNone(run_one(job_id=job.pk))
        remote.assert_not_called(); self.assertEqual(Job.objects.count(), 1)

    def test_consent_revocation_before_dispatch_releases_reservation(self):
        job = self.queue(); AgentPoolEntry.objects.filter(pk=self.entry.pk).update(enabled=False)
        with patch("apps.assistant.free_harness.run_compact_harness") as remote:
            result = run_one(job_id=job.pk)
        remote.assert_not_called(); self.assertEqual(result.status, "failed")
        job.ai_usage.refresh_from_db(); self.assertEqual(job.ai_usage.status, "released")

    def test_stale_edit_before_dispatch_never_calls_and_stale_result_cannot_publish(self):
        job = self.queue()
        self.event = update_event(event_id=self.event.pk, actor=self.owner, brief="Organizador actualizó la ficha.")
        with patch("apps.assistant.free_harness.run_compact_harness") as remote:
            result = run_one(job_id=job.pk)
        remote.assert_not_called(); self.assertEqual(result.status, "stale")
        self.assertEqual(self.poll(job).json()["status"], "stale")

    def test_cancel_and_late_result_preserve_plan_and_account_consumed_usage(self):
        job = self.queue(); claim = claim_next(job_id=job.pk); prepared = prepare_claim(claim)
        with patch("apps.assistant.free_harness.run_compact_harness", return_value={"payload": PROPOSAL, "usage": {"input_tokens": 600, "output_tokens": 100, "total_tokens": 700}}):
            result = perform_inference(prepared, observer=lambda _: None)
        response = self.client.post(self.url, {"operation": "cancel", "run_id": self.bootstrap["run_id"], "event_id": str(self.event.pk), "job_id": str(job.pk)}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        finished = finish_inference(prepared, result)
        self.assertEqual(finished.status, "cancelled"); self.assertFalse(PlanCandidate.objects.exists())
        job.ai_usage.refresh_from_db(); self.assertEqual(job.ai_usage.total_tokens, 700)

    def test_stop_before_enqueue_records_tombstone_and_prevents_future_call(self):
        key = str(uuid.uuid4())
        stopped = self.client.post(self.url, {"operation": "cancel", "run_id": self.bootstrap["run_id"],
            "event_id": str(self.event.pk), "request_key": key}, content_type="application/json")
        self.assertEqual(stopped.status_code, 200, stopped.content)
        self.assertEqual(stopped.json()["status"], "cancelled")
        self.assertIsNone(stopped.json()["job_id"])
        self.assertEqual(CompactRequestCancellation.objects.count(), 1)
        response = self.post(request_key=key)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "compact_cancelled")
        self.assertFalse(Job.objects.exists())

    def test_stop_answer_by_new_request_key_cancels_child_not_completed_parent(self):
        job = self.queue(); self.process(job, QUESTIONS)
        key = str(uuid.uuid4())
        response = self.post("answers", request_key=key, parent_job_id=str(job.pk), answers={"q1": "assets", "q2": "case"})
        child = Job.objects.get(pk=response.json()["job_id"])
        stopped = self.client.post(self.url, {"operation": "cancel", "run_id": self.bootstrap["run_id"],
            "event_id": str(self.event.pk), "request_key": key}, content_type="application/json")
        self.assertEqual(stopped.status_code, 200, stopped.content)
        self.assertEqual(stopped.json()["job_id"], str(child.pk))
        self.assertEqual(stopped.json()["status"], "cancelled")
        job.refresh_from_db(); self.assertEqual(job.status, "succeeded")
        with patch("apps.assistant.free_harness.run_compact_harness") as remote:
            self.assertIsNone(run_one(job_id=child.pk))
        remote.assert_not_called()

    def test_429_pauses_shared_gateway_without_fallback_and_usage_stays_unknown(self):
        job = self.queue()
        with patch("apps.assistant.free_harness.run_compact_harness", side_effect=FreeHarnessError("quota", http_status=429, phase="inference")) as remote:
            result = run_one(job_id=job.pk)
        self.assertEqual(remote.call_count, 1); self.assertEqual(result.status, "failed")
        self.assertTrue(FreeGatewayState.objects.get(account=self.account).cooldown_until)
        job.ai_usage.refresh_from_db(); self.assertIsNone(job.ai_usage.total_tokens)
        self.assertEqual(job.ai_usage.status, "uncertain")
        self.assertIsNone(self.poll(job).json()["usage"])

    def test_unknown_invalid_and_truncated_outputs_do_not_create_candidate(self):
        job = self.queue(); invalid = deepcopy(PROPOSAL); invalid["agenda"][0]["min"] = 1
        result, mocked = self.process(job, invalid)
        self.assertEqual(mocked.call_count, 1); self.assertEqual(result.status, "failed")
        self.assertEqual(PlanCandidate.objects.count(), 0)

    def test_human_role_owner_csrf_session_and_agent_context_are_required(self):
        for user in (self.other, self.reviewer):
            self.client.force_login(user); self.assertEqual(self.post().status_code, 403 if user == self.reviewer else 409)
        self.client.force_login(self.owner)
        with agent_execution(): self.assertEqual(self.post().status_code, 403)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url, {}, content_type="application/json").status_code, 403)
        self.assertEqual(self.post(run_id=str(uuid.uuid4())).status_code, 409)
        self.assertEqual(self.post(expected_revision=0).status_code, 409)
        self.assertEqual(Job.objects.count(), 0)

    def test_old_generic_free_route_still_rejects_real_events(self):
        with self.assertRaises(ValidationError): enqueue(event=self.event, actor=self.owner, kind="plan", prompt="Prepare a plan", idempotency_key=str(uuid.uuid4()))
        self.assertFalse(Job.objects.exists())

    def test_unapproved_or_synthetic_only_pool_does_not_escalate_to_primary(self):
        AgentPoolEntry.objects.filter(pk=self.entry.pk).update(enabled=False)
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(Job.objects.exists())

    def test_integrated_worker_selects_only_authorized_compact_real_event(self):
        job = self.queue()
        self.assertEqual(next_controlled_job(self.owner.pk), job.pk)
        AIUsage.objects.filter(job=job).update(snapshot={**job.ai_usage.snapshot, "compact_contract": 2})
        self.assertIsNone(next_controlled_job(self.owner.pk))

    def test_parallel_context_is_detached_and_contains_only_closed_projection(self):
        job = self.queue(); prepared = prepare_claim(claim_next(job_id=job.pk), for_parallel=True)
        self.assertTrue(prepared.parallel_safe)
        self.assertFalse(hasattr(prepared.event, "save"))
        self.assertEqual(prepared.event._compact_context_snapshot["context"], BASE_CONTEXT)
        self.assertFalse(hasattr(prepared.event, "title"))

    def test_local_replacement_keeps_ai_content_hours_and_history(self):
        job = self.queue(); self.process(job)
        first = approve_candidate(candidate_id=PlanCandidate.objects.get().pk, actor=self.owner)
        snapshot = deepcopy(first.payload)
        self.event.refresh_from_db()
        self.event = update_event(event_id=self.event.pk, actor=self.owner, speaker_id=self.bootstrap["speakers"]["jorge"])
        response = self.client.post(reverse("assistant:pilot_control"), {"operation": "replan", "run_id": self.bootstrap["run_id"],
            "event_id": str(self.event.pk), "expected_revision": self.event.revision}, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        replacement = PlanCandidate.objects.get(pk=response.json()["candidate_id"])
        before = deepcopy(snapshot); after = deepcopy(replacement.payload)
        for row in before["sessions"]: row.pop("speaker")
        for row in after["sessions"]: row.pop("speaker")
        self.assertEqual(before, after)
        self.assertEqual({row["speaker"] for row in replacement.payload["sessions"]}, {"Jorge Gayoso"})
        self.assertEqual(Job.objects.count(), 1)

    def test_http_strictness_private_poll_and_unknown_job(self):
        for body in ('[]', '{"operation":"start","operation":"start"}', '{"operation":NaN}', '[' * 2000 + '0' + ']' * 2000):
            self.assertEqual(self.client.post(self.url, body, content_type="application/json").status_code, 400)
        job = self.queue(); self.assertIn("no-store", self.poll(job)["Cache-Control"])
        self.client.force_login(self.other); self.assertEqual(self.poll(job).status_code, 409)

    def preview(self, **changes):
        return self.client.post(self.url, {"operation": "preview", "run_id": self.bootstrap["run_id"],
            "event_id": str(self.event.pk), "expected_revision": self.event.revision, **changes}, content_type="application/json")

    def archive(self, job, **changes):
        return self.client.post(self.url, {"operation": "archive", "run_id": self.bootstrap["run_id"],
            "event_id": str(self.event.pk), "job_id": str(job.pk), **changes}, content_type="application/json")

    def private_job(self):
        response = self.post(review_only=True)
        self.assertEqual(response.status_code, 202, response.content)
        job = Job.objects.get(pk=response.json()["job_id"])
        processed, _ = self.process(job)
        self.assertEqual(processed.result["compact_state"], "private_ready")
        job.refresh_from_db()
        return job

    def test_preview_is_exact_wire_prompt_and_has_no_job_reservation_or_network(self):
        from apps.assistant.free_harness import _request
        from apps.assistant.compact_contract import instructions_for, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS
        before = (Job.objects.count(), AIUsage.objects.count(), AIAccount.objects.count(), CompactPlanRequest.objects.count())
        with patch("apps.assistant.free_harness.run_compact_harness") as remote:
            result = self.preview()
        remote.assert_not_called()
        self.assertEqual(result.status_code, 200, result.content)
        data = result.json()
        user, system, bound = _request(context=BASE_CONTEXT, instructions=instructions_for(BASE_CONTEXT), action="plan",
            max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS, synthetic=False, schema=None, minimized=True)
        self.assertEqual(data["system_prompt"], system)
        self.assertEqual(data["instructions"], system)
        self.assertEqual(data["user_prompt"], user)
        self.assertEqual(data["input_bound"], bound)
        self.assertEqual(data["prompt_text"], "SISTEMA\n" + system + "\n\nENTRADA\n" + user)
        self.assertNotIn("job_id", data)
        self.assertIsNone(data["model"])
        self.assertEqual(before, (Job.objects.count(), AIUsage.objects.count(), AIAccount.objects.count(), CompactPlanRequest.objects.count()))

    def test_private_proposal_has_no_candidate_no_public_content_or_approval(self):
        job = self.private_job()
        polled = self.poll(job).json()
        self.assertEqual(polled["status"], "private_ready")
        self.assertEqual(polled["model"], "glm-5.3-flash-free")
        self.assertEqual(polled["provider"], "opencode")
        self.assertTrue(polled["review_only"])
        for key in ("candidate_id", "candidate_url", "approve_url", "agenda", "communications", "response"):
            self.assertNotIn(key, polled)
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertFalse(PlanRevision.objects.exists())
        self.event.refresh_from_db(); self.assertIsNone(self.event.active_plan_id)
        detail = self.client.get(reverse("events:detail", args=[self.event.pk]))
        self.assertEqual(detail.status_code, 200)
        for row in PROPOSAL["agenda"]:
            self.assertNotContains(detail, row["topic"])
        self.assertNotContains(detail, PROPOSAL["communications"][0]["text"])
        self.assertContains(detail, "Agenda reservada para revisión privada.")
        self.assertNotContains(detail, "Revisar propuesta")

    def test_answers_preview_matches_real_child_context_and_private_mode_is_inherited(self):
        initial = self.post(review_only=True); parent = Job.objects.get(pk=initial.json()["job_id"])
        self.process(parent, QUESTIONS)
        batch = {"q1": "assets", "q2": "case"}
        preview = self.preview(parent_job_id=str(parent.pk), answers=batch)
        self.assertEqual(preview.status_code, 200, preview.content)
        submitted = self.post("answers", parent_job_id=str(parent.pk), answers=batch)
        child = Job.objects.get(pk=submitted.json()["job_id"])
        result, remote = self.process(child)
        self.assertTrue(child.compact_request.review_only)
        self.assertEqual(remote.call_args.kwargs["context"], preview.json()["context"])
        self.assertEqual(result.result["compact_state"], "private_ready")
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertEqual(self.preview(parent_job_id=str(parent.pk), answers={"q1": "assets"}).status_code, 400)

    def test_review_mode_cannot_change_by_reusing_request_or_answers_flags(self):
        key = str(uuid.uuid4())
        self.assertEqual(self.post(request_key=key, review_only=True).status_code, 202)
        self.assertEqual(self.post(request_key=key, review_only=False).status_code, 400)
        self.assertEqual(self.post(review_only="true").status_code, 400)
        self.assertEqual(self.post("answers", parent_job_id=str(uuid.uuid4()), answers={}, review_only=True).status_code, 400)
        self.assertEqual(Job.objects.count(), 1)

    def test_archive_private_output_is_idempotent_local_and_does_not_return_agenda(self):
        job = self.private_job()
        temporal = Path(settings.BASE_DIR) / "Temporal" / "qa-gica-compact"
        temporal.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="archive-test-", dir=temporal) as base, override_settings(BASE_DIR=Path(base)):
            result = self.archive(job)
            self.assertEqual(result.status_code, 200, result.content)
            self.assertEqual(result.json(), {"run_id": self.bootstrap["run_id"], "event_id": str(self.event.pk),
                "job_id": str(job.pk), "status": "archived", "saved": True})
            files = list(Path(base).rglob("*.json"))
            self.assertEqual(len(files), 1)
            path = Path(base) / "Temporal" / "gica-agenda-review" / str(self.owner.pk) / (str(job.pk) + ".json")
            self.assertEqual(files[0], path)
            content = path.read_bytes(); stamp = path.stat().st_mtime_ns
            stored = json.loads(content)
            self.assertEqual(stored["response"], PROPOSAL)
            self.assertEqual(stored["agenda"]["sessions"][0]["start"], "2026-11-19T19:30:00-05:00")
            self.assertEqual(stored["model"], "glm-5.3-flash-free")
            self.assertEqual(stored["usage"]["total_tokens"], 900)
            self.assertNotIn("credential_ref", content.decode())
            self.assertNotIn("model_policy_consent", content.decode())
            self.assertEqual(self.archive(job).status_code, 200)
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mtime_ns, stamp)
            self.assertFalse(PlanCandidate.objects.exists())
            self.assertEqual(Job.objects.count(), 1)
            self.assertEqual(AIUsage.objects.count(), 1)

    def test_archive_rejects_stale_unfinished_or_approved_outputs(self):
        queued = self.queue()
        self.assertEqual(self.archive(queued).status_code, 400)
        self.process(queued)
        approved = approve_candidate(candidate_id=PlanCandidate.objects.get().pk, actor=self.owner)
        self.assertEqual(self.archive(queued).status_code, 409)

    def test_archive_and_preview_require_human_owner_current_run_and_closed_identifiers(self):
        job = self.private_job()
        with agent_execution():
            self.assertEqual(self.preview().status_code, 403)
            self.assertEqual(self.archive(job).status_code, 403)
        self.assertEqual(self.archive(job, job_id="../../outside").status_code, 400)
        self.assertEqual(self.archive(job, path="../../outside").status_code, 400)
        self.assertEqual(self.preview(expected_revision=0).status_code, 409)
        self.client.force_login(self.other)
        self.assertEqual(self.preview().status_code, 409)
        self.assertEqual(self.archive(job).status_code, 409)

    def test_archive_io_failure_and_symlink_guard_are_clear_and_leave_no_partial_file(self):
        job = self.private_job()
        temporal = Path(settings.BASE_DIR) / "Temporal" / "qa-gica-compact"
        with tempfile.TemporaryDirectory(prefix="archive-test-", dir=temporal) as base, override_settings(BASE_DIR=Path(base)):
            with patch("apps.assistant.compact_archive.os.replace", side_effect=OSError("private OS detail")):
                result = self.archive(job)
            self.assertEqual(result.status_code, 400)
            self.assertEqual(result.json()["code"], "compact_archive_failed")
            self.assertNotIn("private OS detail", result.content.decode())
            self.assertEqual(list(Path(base).rglob("*.json")), [])
            self.assertEqual(list(Path(base).rglob("*.tmp")), [])
            original = Path.is_symlink
            with patch.object(Path, "is_symlink", lambda path: path.name == "gica-agenda-review" or original(path)):
                self.assertEqual(self.archive(job).status_code, 400)
            self.assertEqual(list(Path(base).rglob("*.json")), [])
