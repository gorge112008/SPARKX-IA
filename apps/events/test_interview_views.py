"""Human-reviewed interview data stays local and never authorizes inference."""

import uuid
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.ai_management.models import AIAccount, AIUsage
from apps.assistant import provider
from apps.assistant.models import Message
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision, TaskProgress
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.task_progress import update_task_progress
from apps.planning.tests import valid_plan

from .models import Event
from .services import create_event, update_event


class EventInterviewEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="interview-owner")
        cls.other = get_user_model().objects.create_user(username="interview-other")

    def setUp(self):
        self.event = create_event(
            actor=self.owner, title="Seminario propio",
            brief="Objetivo y modalidad descritos por la persona organizadora.",
        )
        self.client.force_login(self.owner)
        boundary = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No network in interview"))
        self.remote = boundary.start()
        self.addCleanup(boundary.stop)

    def tearDown(self):
        self.remote.assert_not_called()
        super().tearDown()

    def url(self, name="interview", event=None, **kwargs):
        return reverse("events:" + name, kwargs={"event_id": (event or self.event).pk, **kwargs})

    def data(self, **changes):
        values = {
            "question_key": "objective", "expected_revision": self.event.revision,
            "status": "confirmed", "value": "Preparar un caso práctico de mantenimiento.",
            "action": "save",
        }
        values.update(changes)
        return values

    def candidate(self):
        self.event.refresh_from_db()
        return create_candidate(
            event=self.event, actor=self.owner, payload=valid_plan(),
            base_revision=self.event.revision, base_plan_id=self.event.active_plan_id,
        )

    def assert_no_ai_records(self):
        for model in (Job, AIUsage, AIAccount, Message):
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.exists())

    def test_detail_links_to_interview_and_get_is_read_only_without_api_account(self):
        detail = self.client.get(self.url("detail"))
        self.assertContains(detail, f'href="{self.url()}"')
        for suffix in ("", "?question=audience", "?view=summary"):
            with self.subTest(suffix=suffix):
                response = self.client.get(self.url() + suffix)
                self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers, {})
        self.assertEqual(self.event.revision, 1)
        self.assert_no_ai_records()

    def test_explicit_save_records_answer_without_rewriting_ficha_or_starting_ai(self):
        original = (self.event.title, self.event.brief, self.event.starts_at, self.event.capacity)
        response = self.client.post(self.url(), self.data(owner=self.other.pk, revision=999, active_plan=str(uuid.uuid4())))
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["objective"]["status"], "confirmed")
        self.assertEqual(self.event.interview_answers["objective"]["value"], self.data()["value"])
        self.assertEqual(self.event.revision, 2)
        self.assertEqual(self.event.owner_id, self.owner.pk)
        self.assertEqual((self.event.title, self.event.brief, self.event.starts_at, self.event.capacity), original)
        self.assertIsNone(self.event.active_plan_id)
        self.assert_no_ai_records()

    def test_save_then_summary_displays_saved_answer(self):
        response = self.client.post(self.url(), self.data(action="summary"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("view=summary", response.url)
        summary = self.client.get(response.url)
        self.assertContains(summary, self.data()["value"])
        self.assert_no_ai_records()

    def test_repeated_unchanged_save_keeps_revision(self):
        self.client.post(self.url(), self.data())
        self.event.refresh_from_db()
        original = deepcopy(self.event.interview_answers)
        response = self.client.post(self.url(), self.data())
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, 2)
        self.assertEqual(self.event.interview_answers, original)

    def test_unanswered_can_be_explicitly_pending_without_inventing_a_value(self):
        response = self.client.post(self.url(), self.data(question_key="duration_minutes", status="pending", value=""))
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["duration_minutes"]["status"], "pending")
        self.assertFalse(self.event.interview_answers["duration_minutes"].get("value"))
        self.assert_no_ai_records()

    def test_assumptions_are_not_promoted_to_confirmation(self):
        response = self.client.post(self.url(), self.data(question_key="audience", status="assumed", value="Estudiantes de ingeniería"))
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["audience"]["status"], "assumed")
        context = provider._context(self.event)
        self.assertIn("interview", context["event"])
        self.assertIn("assumed", str(context["event"]["interview"]))
        self.assertIn("Estudiantes de ingeniería", str(context["event"]["interview"]))
        self.assert_no_ai_records()

    def test_invalid_answer_never_changes_saved_event(self):
        cases = [
            {"question_key": "owner"},
            {"status": "approved_by_ai"},
            {"status": "confirmed", "value": ""},
            {"value": "a" * 1001},
            {"question_key": "objective", "status": "not_applicable", "value": ""},
            {"question_key": "duration_minutes", "status": "in_brief", "value": ""},
            {"question_key": "duration_minutes", "value": "0"},
            {"question_key": "duration_minutes", "value": "1441"},
            {"question_key": "duration_minutes", "value": "1.5"},
            {"question_key": "duration_minutes", "value": "noventa"},
            {"expected_revision": ""},
        ]
        for change in cases:
            with self.subTest(change=change):
                response = self.client.post(self.url(), self.data(**change))
                self.assertNotEqual(response.status_code, 302)
                self.assertLess(response.status_code, 500)
                self.event.refresh_from_db()
                self.assertEqual(self.event.interview_answers, {})
                self.assertEqual(self.event.revision, 1)
        self.assert_no_ai_records()

    def test_optional_location_can_be_not_applicable(self):
        response = self.client.post(self.url(), self.data(question_key="location", status="not_applicable", value=""))
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["location"]["status"], "not_applicable")

    def test_duration_boundaries_are_saved_and_exposed_as_structured_context(self):
        for duration in ("1", "1440"):
            with self.subTest(duration=duration):
                self.event.refresh_from_db()
                response = self.client.post(self.url(), self.data(question_key="duration_minutes", value=duration))
                self.assertEqual(response.status_code, 302)
                self.event.refresh_from_db()
                self.assertEqual(str(self.event.interview_answers["duration_minutes"]["value"]), duration)
        self.assert_no_ai_records()

    def test_stale_answer_preserves_submitted_text_and_requires_explicit_resave(self):
        stale = self.data(value="Mi respuesta conservada")
        update_event(event_id=self.event.pk, actor=self.owner, title="Ficha vigente cambiada")
        response = self.client.post(self.url(), stale)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Mi respuesta conservada", status_code=409)
        self.assertContains(response, 'name="expected_revision" value="2"', status_code=409)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers, {})
        self.assertEqual(self.event.revision, 2)
        stale["expected_revision"] = 2
        saved = self.client.post(self.url(), stale)
        self.assertEqual(saved.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["objective"]["value"], "Mi respuesta conservada")
        self.assertEqual(self.event.revision, 3)

    def test_foreign_event_is_hidden_on_get_and_post(self):
        foreign = create_event(actor=self.other, title="Privado ajeno", brief="Descripción ajena confidencial")
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url(event=foreign), self.data())
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, foreign.brief, status_code=404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.interview_answers, {})
        self.assertEqual(foreign.revision, 1)

    def test_anonymous_interview_requires_login_and_other_methods_are_rejected(self):
        self.assertEqual(self.client.put(self.url(), self.data()).status_code, 405)
        self.client.logout()
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url(), self.data())
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response.url)

    def test_csrf_is_required_for_save(self):
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url(), self.data()).status_code, 403)
        secured.get(self.url())
        values = self.data(csrfmiddlewaretoken=secured.cookies["csrftoken"].value)
        self.assertEqual(secured.post(self.url(), values).status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, 2)

    def test_interview_text_is_escaped_in_question_summary_and_conflict(self):
        unsafe = "<script>interview()</script>"
        self.client.post(self.url(), self.data(value=unsafe))
        self.event.refresh_from_db()
        for suffix in ("?question=objective", "?view=summary"):
            with self.subTest(suffix=suffix):
                response = self.client.get(self.url() + suffix)
                self.assertNotContains(response, unsafe)
                self.assertContains(response, "&lt;script&gt;interview()&lt;/script&gt;")
        response = self.client.post(self.url(), self.data(expected_revision=1, value="<script>retained()</script>"))
        self.assertEqual(response.status_code, 409)
        self.assertNotContains(response, "<script>retained()</script>", status_code=409)
        self.assertContains(response, "&lt;script&gt;retained()&lt;/script&gt;", status_code=409)

    def test_saved_answer_preserves_approved_plan_and_progress_and_invalidates_old_candidate(self):
        approved = approve_candidate(candidate_id=self.candidate().pk, actor=self.owner)
        self.event.refresh_from_db()
        progress = update_task_progress(
            event=self.event, actor=self.owner, plan_id=approved.pk, task_id="t1",
            status=TaskProgress.Status.COMPLETED, expected_version=0,
            request_key=str(uuid.uuid4()), note="Verificación manual del organizador.",
        )
        pending = self.candidate()
        original_payload = deepcopy(approved.payload)
        response = self.client.post(self.url(), self.data())
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, approved.pk)
        approved.refresh_from_db()
        self.assertEqual(approved.payload, original_payload)
        progress.refresh_from_db()
        self.assertEqual(progress.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(progress.version, 1)
        with self.assertRaises(ValidationError):
            approve_candidate(candidate_id=pending.pk, actor=self.owner)
        pending.refresh_from_db()
        self.assertEqual(pending.status, PlanCandidate.Status.PENDING)
        self.assertEqual(PlanRevision.objects.count(), 1)
        self.assert_no_ai_records()
        # New requirements require a fresh preparation review on a later plan.
        # The previous version remains completed in its own immutable history.
        next_plan = approve_candidate(candidate_id=self.candidate().pk, actor=self.owner)
        self.assertFalse(TaskProgress.objects.filter(plan=next_plan).exists())
        progress.refresh_from_db()
        self.assertEqual(progress.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(progress.plan_id, approved.pk)

    def test_description_edit_reopens_only_answers_that_referred_to_old_description(self):
        self.client.post(self.url(), self.data(status="in_brief", value=""))
        self.event.refresh_from_db()
        self.client.post(self.url(), self.data(question_key="audience", status="confirmed", value="Profesionales de mantenimiento"))
        self.event.refresh_from_db()
        before_audience = deepcopy(self.event.interview_answers["audience"])
        update_event(event_id=self.event.pk, actor=self.owner, brief="Descripción actualizada del evento.")
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["objective"]["status"], "pending")
        self.assertEqual(self.event.interview_answers["audience"], before_audience)
        self.assert_no_ai_records()

    def test_provider_and_chat_read_saved_answers_without_executing_inference(self):
        self.client.post(self.url(), self.data(status="assumed", value="Aprender mantenimiento estratégico"))
        self.event.refresh_from_db()
        plan_context = provider._context(self.event)
        chat_context = provider.chat_context(self.event)
        self.assertEqual(chat_context["context"]["event"]["interview"], plan_context["event"]["interview"])
        self.assertIn("Aprender mantenimiento estratégico", str(plan_context["event"]["interview"]))
        self.assertIsNone(plan_context["approved_plan"])
        self.assertIsNone(chat_context["context"]["task_progress"])
        self.assert_no_ai_records()
