"""Closed pilot changes, mocked provider, immutable base and human approval."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.ai_management.models import AIUsage, AgentGrant
from apps.assistant.compact_changes import project_change, validate_change_response
from apps.assistant.compact_contract import BASE_CONTEXT, OPENAI_PROPOSAL_SCHEMA, validate_context
from apps.assistant.models import CompactPlanRequest
from apps.jobs.models import Job
from apps.jobs.services import claim_next, prepare_claim, run_one
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate, create_candidate
from . import test_compact_openai as fixtures
from .test_compact_planning import QUESTIONS


BASE_PROPOSAL = {"v": 1, "state": "proposal", "agenda": [
    {"topic": "Planificación con Jorge Gayoso", "min": 35, "speaker": "p1", "resource": "r1"},
    {"topic": "Caso aplicado de mantenimiento", "min": 35, "speaker": "p1", "resource": "r1"},
    {"topic": "Preguntas del público", "min": 20, "speaker": "p1", "resource": "r1"}],
    "preparation": [
        {"task": "Confirmar temario del expositor", "after": []},
        {"task": "Preparar presentación de mantenimiento", "after": [1]},
        {"task": "Diseñar el caso práctico de activos", "after": [2]},
        {"task": "Revisar material de apoyo", "after": [3]},
        {"task": "Configurar sala virtual", "after": []},
        {"task": "Preparar registro de participantes", "after": [5]},
        {"task": "Coordinar moderación de preguntas", "after": [1]},
        {"task": "Ensayar acceso, audio y pantalla", "after": [4, 5, 7]}],
    "communications": [{"type": "invitation", "text": "Participa en el seminario de mantenimiento."}]}


def changed_proposal():
    value = deepcopy(BASE_PROPOSAL)
    value["agenda"][0].update(topic="Contenido público propuesto", min=30)
    value["agenda"][1]["min"] = 40
    return value


class ClosedChangeProjectionTests(SimpleTestCase):
    def event(self, rows=None):
        payload = {"sessions": rows or [{"title": row["topic"], "duration_minutes": row["min"]} for row in BASE_PROPOSAL["agenda"]]}
        return SimpleNamespace(active_plan_id="local-only-id", active_plan=SimpleNamespace(payload=payload))

    def test_projection_exports_only_minutes_and_roles(self):
        projected = project_change(self.event(), "more_case_time")
        self.assertEqual(projected, {"kind": "more_case_time", "base_agenda": [
            {"min": 35, "role": "content"}, {"min": 35, "role": "case"}, {"min": 20, "role": "questions"}]})
        self.assertNotIn("Jorge", json.dumps(projected))
        self.assertEqual(validate_context(BASE_CONTEXT | {"change": projected})["change"], projected)

    def test_unknown_combined_ambiguous_and_impossible_changes_fail_closed(self):
        for kind in ("other", True, {"kind": "more_case_time"}):
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                project_change(self.event(), kind)
        invalid = [
            [{"title": "Caso y preguntas", "duration_minutes": 90}],
            [{"title": "Caso aplicado", "duration_minutes": 80}, {"title": "Preguntas", "duration_minutes": 10}],
            [{"title": "Caso aplicado", "duration_minutes": 40}, {"title": "Otro caso", "duration_minutes": 30}, {"title": "Preguntas", "duration_minutes": 20}],
        ]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValidationError):
                project_change(self.event(rows), "more_case_time")

    def test_delta_questions_and_structure_are_validated_mechanically(self):
        event = self.event()
        context = BASE_CONTEXT | {"change": project_change(event, "more_case_time")}
        validate_change_response(event, context, changed_proposal())
        invalid = [deepcopy(BASE_PROPOSAL), deepcopy(QUESTIONS)]
        too_few_questions = changed_proposal()
        too_few_questions["agenda"][0]["min"] = 41
        too_few_questions["agenda"][2]["min"] = 9
        invalid.append(too_few_questions)
        wrong_structure = changed_proposal()
        wrong_structure["agenda"].reverse()
        invalid.append(wrong_structure)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_change_response(event, context, value)


class CompactChangeWorkflowTests(TestCase):
    setUp = fixtures.CompactOpenAITests.setUp
    post = fixtures.CompactOpenAITests.post
    preview = fixtures.CompactOpenAITests.preview
    poll = fixtures.CompactOpenAITests.poll
    queue = fixtures.CompactOpenAITests.queue
    process = fixtures.CompactOpenAITests.process

    def approve_base(self, *, preferences=False):
        job = self.queue()
        if preferences:
            self.process(job, QUESTIONS)
            response = self.post("answers", parent_job_id=str(job.pk), answers={"q1": "planning", "q2": "case"})
            self.assertEqual(response.status_code, 202, response.content)
            job = Job.objects.get(pk=response.json()["job_id"])
        processed, _ = self.process(job, BASE_PROPOSAL)
        self.assertEqual(processed.status, "succeeded", processed.error)
        candidate = PlanCandidate.objects.get(pk=processed.result["candidate_id"])
        self.base = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return job

    def test_no_active_plan_unknown_or_mixed_request_never_reserve(self):
        for response in (
            self.post(provider="openai", change_request="more_case_time"),
            self.preview(provider="openai", change_request="unknown"),
            self.preview(provider="openai", change_request=None),
            self.preview(provider="openai", change_request=True),
            self.post(provider="openai", change_request="more_case_time", answers={}),
        ):
            self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_non_owner_and_stale_revision_cannot_request_change(self):
        self.approve_base()
        before = (Job.objects.count(), AIUsage.objects.count())
        stale = self.post(provider="openai", change_request="more_case_time", expected_revision=self.event.revision - 1)
        self.assertEqual(stale.status_code, 409)
        self.client.force_login(self.other)
        denied = self.post(provider="openai", change_request="more_case_time")
        self.assertIn(denied.status_code, (400, 403, 409))
        self.assertEqual(before, (Job.objects.count(), AIUsage.objects.count()))

    def test_unapproved_date_or_speaker_change_never_becomes_part_of_timing_change(self):
        from apps.events.services import update_event
        self.approve_base()
        self.event = update_event(event_id=self.event.pk, actor=self.owner,
            starts_at=self.event.starts_at + timedelta(days=7), scheduled_dates=["2026-11-26"])
        response = self.post(provider="openai", change_request="more_case_time")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["code"], "compact_change_invalid")
        self.assertEqual(Job.objects.count(), 1)

    def test_preview_uses_minimized_base_and_preferences_without_reservation(self):
        self.approve_base(preferences=True)
        before = (Job.objects.count(), AIUsage.objects.count())
        response = self.preview(provider="openai", change_request="more_case_time")
        self.assertEqual(response.status_code, 200, response.content)
        public = response.json()
        self.assertEqual(public["context"]["answers"], {"focus": "planning", "format": "case"})
        self.assertEqual(public["response_schema"], OPENAI_PROPOSAL_SCHEMA)
        self.assertEqual(public["context"]["change"]["base_agenda"][1], {"min": 35, "role": "case"})
        self.assertNotIn("Jorge Gayoso", public["prompt_text"])
        self.assertNotIn(str(self.event.pk), public["prompt_text"])
        self.assertNotIn(str(self.base.pk), public["prompt_text"])
        self.assertEqual(before, (Job.objects.count(), AIUsage.objects.count()))

    def test_confirmed_preferences_survive_a_local_approved_plan_revision(self):
        self.approve_base(preferences=True)
        local = create_candidate(event=self.event, actor=self.owner, payload=self.base.payload,
            base_revision=self.event.revision, base_plan_id=self.base.pk)
        approve_candidate(candidate_id=local.pk, actor=self.owner)
        self.event.refresh_from_db()
        response = self.preview(provider="openai", change_request="more_case_time")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["context"]["answers"], {"focus": "planning", "format": "case"})

    def test_change_stays_pending_preserves_content_and_requires_human_approval(self):
        self.approve_base()
        original = deepcopy(self.base.payload)
        preview = self.preview(provider="openai", change_request="more_case_time").json()
        job = self.queue(change_request="more_case_time")
        duplicate = self.post(provider="openai", change_request="more_case_time")
        self.assertEqual(duplicate.json()["job_id"], str(job.pk))
        self.assertEqual(job.ai_usage.reserved_usd, Decimal(".017100"))
        result, remote = self.process(job, changed_proposal())
        self.assertEqual(result.status, "succeeded", result.error)
        self.assertEqual(remote.call_count, 1)
        body = json.loads(remote.call_args.args[0].data)
        self.assertEqual(body["input"][0]["content"], preview["system_prompt"])
        candidate = PlanCandidate.objects.get(pk=result.result["candidate_id"])
        self.assertEqual(candidate.status, "pending")
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, self.base.pk)
        self.assertEqual(candidate.payload["tasks"], original["tasks"])
        self.assertEqual(candidate.payload["risks"], original["risks"])
        self.assertEqual([row["title"] for row in candidate.payload["sessions"]], [row["title"] for row in original["sessions"]])
        self.assertEqual([row["duration_minutes"] for row in candidate.payload["sessions"]], [30, 40, 20])
        self.assertEqual(candidate.payload["sessions"][1]["start"], "2026-11-19T20:00:00-05:00")
        approved = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, approved.pk)
        self.base.refresh_from_db()
        self.assertEqual(self.base.payload, original)
        self.assertEqual(PlanRevision.objects.count(), 2)

    def test_invalid_delta_or_new_questions_never_create_an_applicable_candidate(self):
        self.approve_base()
        job = self.queue(change_request="more_case_time")
        failed, remote = self.process(job, BASE_PROPOSAL)
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(PlanCandidate.objects.count(), 1)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, self.base.pk)

    def test_change_obeys_budget_and_does_not_fall_back_or_dispatch(self):
        self.approve_base()
        before = list(AIUsage.objects.order_by("pk").values())
        AgentGrant.objects.filter(pk=self.grant.pk).update(budget_usd=Decimal(".001"))
        response = self.post(provider="openai", change_request="more_case_time")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(before, list(AIUsage.objects.order_by("pk").values()))
        self.assertEqual(Job.objects.count(), 1)

    def test_stale_change_is_rejected_before_provider_and_base_is_untouched(self):
        self.approve_base()
        job = self.queue(change_request="more_case_time")
        candidate = create_candidate(event=self.event, actor=self.owner, payload=self.base.payload,
            base_revision=self.event.revision, base_plan_id=self.base.pk)
        next_plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        with patch("apps.assistant.provider._opener.open") as remote:
            result = run_one(job_id=job.pk)
        remote.assert_not_called()
        self.assertEqual(result.status, "stale")
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, next_plan.pk)

    def test_changed_base_projection_cannot_be_used_as_free_text_export(self):
        self.approve_base()
        job = self.queue(change_request="more_case_time")
        record = CompactPlanRequest.objects.get(job=job)
        record.context["change"]["base_agenda"][0]["topic"] = "private text"
        record.save(update_fields=["context"])
        with patch("apps.assistant.provider._opener.open") as remote:
            result = run_one(job_id=job.pk)
        remote.assert_not_called()
        self.assertEqual(result.status, "failed")
