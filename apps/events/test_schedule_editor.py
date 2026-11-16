"""Manual time changes retain the approved history and require fresh approval."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.assistant.execution import agent_execution
from apps.assistant.pilot_workflow import build_pilot_plan
from apps.directory.services import upsert_person
from apps.jobs.models import Job, UIAction
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate, create_candidate
from .services import create_event, update_event


class ScheduleEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(username="schedule-owner")
        cls.other = users.create_user(username="schedule-other")
        cls.reviewer = users.create_user(username="schedule-reviewer")
        for user, role in ((cls.owner, "organizer"), (cls.other, "organizer"), (cls.reviewer, "reviewer")):
            PortalAccount.objects.create(user=user, role=role)
        cls.speaker = upsert_person(actor=cls.owner, full_name="Jorge Gayoso Ugas", category="speaker")

    def event_with_plan(self, *, start=None, zone="America/Lima"):
        start = start or datetime(2026, 11, 26, 19, 30, tzinfo=ZoneInfo(zone))
        event = create_event(actor=self.owner, title="Piloto de mantenimiento", brief="Seminario piloto con agenda revisada.",
                             starts_at=start, timezone=zone, scheduled_dates=[start.date().isoformat()], speaker_id=self.speaker.pk,
                             interview_answers={"duration_minutes": {"status": "confirmed", "value": "90"}})
        candidate = create_candidate(event=event, actor=self.owner, payload=build_pilot_plan(event), base_revision=event.revision, base_plan_id=None)
        self.assertFalse(candidate.validation)
        approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        event.refresh_from_db()
        return event

    def setUp(self):
        self.event = self.event_with_plan()
        self.url = reverse("events:schedule_editor", args=[self.event.pk])
        self.client.force_login(self.owner)

    def tearDown(self):
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(UIAction.objects.count(), 0)
        self.assertEqual(AIUsage.objects.count(), 0)

    def data(self, event=None):
        event = event or self.event
        sessions = event.active_plan.payload["sessions"]
        result = {"expected_revision": str(event.revision), "expected_plan": str(event.active_plan_id),
                  "sessions-TOTAL_FORMS": str(len(sessions)), "sessions-INITIAL_FORMS": str(len(sessions)),
                  "sessions-MIN_NUM_FORMS": "1", "sessions-MAX_NUM_FORMS": "200"}
        for index, row in enumerate(sessions):
            result.update({f"sessions-{index}-session_id": row["id"],
                           f"sessions-{index}-start": datetime.fromisoformat(row["start"]).astimezone(ZoneInfo(event.timezone)).strftime("%Y-%m-%dT%H:%M"),
                           f"sessions-{index}-duration_minutes": str(row["duration_minutes"])})
        return result

    def test_get_displays_every_session_and_current_optimistic_snapshot(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-gica-schedule-form')
        self.assertContains(response, 'data-gica-session=', count=5)
        self.assertContains(response, 'name="expected_revision" value="2"')
        self.assertContains(response, f'name="expected_plan" value="{self.event.active_plan_id}"')

    def test_valid_adjustment_creates_reviewable_candidate_without_changing_active_plan(self):
        original = deepcopy(self.event.active_plan.payload)
        data = self.data() | {"sessions-0-duration_minutes": "10", "sessions-1-start": "2026-11-26T19:40", "sessions-1-duration_minutes": "15"}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("events:detail", args=[self.event.pk]) + "#candidate", fetch_redirect_response=False)
        candidate = PlanCandidate.objects.filter(event=self.event, status="pending").get()
        self.assertFalse(candidate.validation)
        self.assertEqual(candidate.payload["sessions"][0]["duration_minutes"], 10)
        self.assertEqual(candidate.payload["sessions"][1]["start"], "2026-11-26T19:40:00-05:00")
        self.assertEqual(candidate.payload["tasks"], original["tasks"])
        self.assertEqual(candidate.base_revision, self.event.revision)
        self.assertEqual(candidate.base_plan_id, self.event.active_plan_id)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan.payload, original)
        self.assertEqual(self.event.active_plan.version, 1)
        self.assertEqual(PlanRevision.objects.count(), 1)
        revision = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.payload["sessions"][0]["duration_minutes"], 10)

    def test_stale_event_revision_returns_conflict_without_creating_proposal(self):
        stale = self.data()
        update_event(event_id=self.event.pk, actor=self.owner, capacity=50)
        response = self.client.post(self.url, stale)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Recarga", status_code=409)
        self.assertEqual(PlanCandidate.objects.count(), 1)

    def test_stale_active_plan_returns_conflict_even_with_current_event_revision(self):
        old_plan = self.event.active_plan_id
        candidate = create_candidate(event=self.event, actor=self.owner, payload=self.event.active_plan.payload,
                                     base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)
        approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        response = self.client.post(self.url, self.data() | {"expected_plan": str(old_plan)})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(PlanCandidate.objects.count(), 2)

    def test_duplicate_foreign_or_missing_session_ids_are_not_saved(self):
        baseline = PlanCandidate.objects.count()
        variants = [self.data() | {"sessions-4-session_id": "apertura"}, self.data() | {"sessions-4-session_id": "foreign-session"},
                    {key: value for key, value in (self.data() | {"sessions-TOTAL_FORMS": "4", "sessions-INITIAL_FORMS": "4"}).items() if not key.startswith("sessions-4-")}]
        for data in variants:
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "conservar todas las sesiones")
                self.assertEqual(PlanCandidate.objects.count(), baseline)

    def test_overlap_is_visible_and_cannot_be_approved(self):
        original = deepcopy(self.event.active_plan.payload)
        response = self.client.post(self.url, self.data() | {"sessions-1-start": "2026-11-26T19:31"})
        self.assertEqual(response.status_code, 302)
        candidate = PlanCandidate.objects.get(event=self.event, status="pending")
        self.assertTrue(any("solapan" in error for error in candidate.validation))
        with self.assertRaises(ValidationError):
            approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan.payload, original)
        self.assertEqual(PlanRevision.objects.count(), 1)

    def test_outside_selected_day_or_duration_is_not_approved(self):
        for changes in ({"sessions-4-duration_minutes": "20"}, {"sessions-4-start": "2026-11-27T20:50"}):
            response = self.client.post(self.url, self.data() | changes)
            self.assertEqual(response.status_code, 302)
            candidate = PlanCandidate.objects.filter(event=self.event, status="pending").latest("created_at")
            self.assertTrue(candidate.validation)
            with self.assertRaises(ValidationError):
                approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.assertEqual(PlanRevision.objects.count(), 1)

    def test_invalid_local_input_and_malformed_formset_are_rejected_without_candidates(self):
        variants = [{"sessions-0-start": "2026-11-26"}, {"sessions-0-start": "2026-11-26T19:30-05:00"},
                    {"sessions-0-start": "2026-11-31T19:30"}, {"sessions-0-duration_minutes": "0"},
                    {"sessions-0-duration_minutes": "true"}, {"sessions-TOTAL_FORMS": "201"}]
        for changes in variants:
            with self.subTest(changes=changes):
                response = self.client.post(self.url, self.data() | changes)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(PlanCandidate.objects.count(), 1)
        self.assertEqual(self.client.post(self.url, {"expected_revision": "2"}).status_code, 200)
        self.assertEqual(PlanCandidate.objects.count(), 1)

    def test_ambiguous_or_nonexistent_dst_times_do_not_create_a_proposal(self):
        for start, invalid in ((datetime(2026, 11, 1, 2, 30, tzinfo=ZoneInfo("America/New_York")), "2026-11-01T01:30"),
                               (datetime(2026, 3, 8, 3, 30, tzinfo=ZoneInfo("America/New_York")), "2026-03-08T02:30")):
            with self.subTest(invalid=invalid):
                event = self.event_with_plan(start=start, zone="America/New_York")
                baseline = PlanCandidate.objects.count()
                response = self.client.post(reverse("events:schedule_editor", args=[event.pk]), self.data(event) | {"sessions-0-start": invalid})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "no existe o es ambiguo")
                self.assertEqual(PlanCandidate.objects.count(), baseline)

    def test_foreign_owner_reviewer_and_agent_cannot_change_schedule(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 404)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.client.force_login(self.owner)
        with agent_execution("gica-1"):
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.assertEqual(PlanCandidate.objects.count(), 1)

    def test_csrf_and_method_guards_are_preserved(self):
        self.assertEqual(self.client.put(self.url, "{}", content_type="application/json").status_code, 405)
        secured = Client(enforce_csrf_checks=True); secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url, self.data()).status_code, 403)
        secured.get(self.url)
        token = secured.cookies["csrftoken"].value
        self.assertEqual(secured.post(self.url, self.data(), HTTP_X_CSRFTOKEN=token).status_code, 302)

    def test_event_without_approved_plan_redirects_to_details(self):
        event = create_event(actor=self.owner, title="Plan por preparar", brief="Ficha sin agenda aprobada.")
        response = self.client.get(reverse("events:schedule_editor", args=[event.pk]))
        self.assertRedirects(response, reverse("events:detail", args=[event.pk]), fetch_redirect_response=False)
