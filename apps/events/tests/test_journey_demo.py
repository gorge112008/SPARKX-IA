"""An explicitly manual second demo exercises the real, owner-approved workflow.

These tests use Django's isolated test database. Provider calls are forbidden;
synthetic planning examples must never be presented as inference or execution.
"""

from copy import deepcopy
from io import StringIO
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.assistant.models import Message
from apps.jobs.models import Job
from apps.planning.domain import plan_impact, validate_plan
from apps.planning.models import PlanCandidate, PlanRevision, TaskProgress, TaskProgressChange
from apps.planning.progress_ui import task_tracking_context
from apps.planning.services import approve_candidate, StalePlanError
from apps.planning.task_progress import update_task_progress

from apps.events.demo import DEMO_EVENT_ID, seed_demo_event
from apps.events.journey_demo import (
    JOURNEY_EVENT_ID,
    ensure_journey_proposal,
    journey_baseline_payload,
    journey_change_payload,
    journey_conflict_payload,
    seed_journey_demo,
)
from apps.events.models import Event
from apps.events.services import create_event, update_event, update_interview


class _ManualJourneyCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="journey-owner")
        cls.other = User.objects.create_user(username="journey-other")
        cls.reviewer = User.objects.create_user(username="journey-reviewer")
        PortalAccount.objects.create(user=cls.reviewer, role=PortalAccount.Role.REVIEWER)

    def setUp(self):
        super().setUp()
        provider_patch = patch(
            "apps.assistant.provider._opener.open",
            side_effect=AssertionError("A manual demo must not contact an AI provider."),
        )
        self.provider = provider_patch.start()
        self.addCleanup(provider_patch.stop)

    def tearDown(self):
        self.provider.assert_not_called()
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(Message.objects.exists())
        super().tearDown()

    def make_demo(self):
        self.event = seed_journey_demo(actor=self.owner).event
        return self.event

    def candidate(self, scenario="baseline", **overrides):
        self.event.refresh_from_db()
        command = {
            "actor": self.owner,
            "event_id": self.event.pk,
            "scenario": scenario,
            "expected_revision": self.event.revision,
            "expected_plan_id": self.event.active_plan_id,
        }
        command.update(overrides)
        return ensure_journey_proposal(**command)

    def approve(self, candidate=None):
        candidate = candidate or self.candidate()
        plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return plan

    def counts(self):
        return (
            Event.objects.count(), PlanCandidate.objects.count(), PlanRevision.objects.count(),
            TaskProgress.objects.count(), TaskProgressChange.objects.count(),
        )

    def stable_root_task(self):
        before = journey_baseline_payload()["tasks"]
        after = {task["id"]: task for task in journey_change_payload()["tasks"]}
        return next(task for task in before if not task["depends_on"] and after.get(task["id"]) == task)


class JourneyDemoSeedTests(_ManualJourneyCase):
    def test_seed_leaves_first_plan_pending_for_explicit_human_approval(self):
        result = seed_journey_demo(actor=self.owner)
        event = Event.objects.get(pk=JOURNEY_EVENT_ID)
        self.assertTrue(result.created)
        self.assertEqual(event.owner_id, self.owner.pk)
        self.assertIsNone(event.active_plan_id)
        self.assertEqual(event.plan_revisions.count(), 0)
        self.assertFalse(TaskProgress.objects.exists())
        candidate = event.candidates.get()
        self.assertEqual(candidate.status, PlanCandidate.Status.PENDING)
        self.assertEqual(candidate.created_by_id, self.owner.pk)
        self.assertEqual(candidate.base_revision, event.revision)
        self.assertIsNone(candidate.base_plan_id)
        self.assertEqual(validate_plan(candidate.payload), [])
        self.assertEqual(candidate.validation, [])
        self.assertTrue(all(task["status"] == "pending" for task in candidate.payload["tasks"]))

    def test_payload_factories_return_independent_valid_plans_and_a_real_conflict(self):
        baseline = journey_baseline_payload()
        change = journey_change_payload()
        conflict = journey_conflict_payload()
        self.assertEqual(validate_plan(baseline), [])
        self.assertEqual(validate_plan(change), [])
        self.assertTrue(validate_plan(conflict))
        impact = plan_impact(baseline, change)
        self.assertTrue(impact["sessions"]["changed"] or impact["sessions"]["added"])
        self.assertEqual(impact["tasks"]["added"], [])
        self.assertEqual(impact["tasks"]["changed"], ["ensayar"])
        original = deepcopy(baseline)
        baseline["sessions"][0]["title"] = "An edit in this test only"
        baseline["tasks"][0]["title"] = "A separate edit"
        self.assertEqual(journey_baseline_payload(), original)
        self.assertNotEqual(change["sessions"][0]["title"], "An edit in this test only")

    def test_reload_preserves_approval_manual_edits_and_task_evidence(self):
        self.make_demo()
        plan = self.approve()
        task = self.stable_root_task()
        progress = update_task_progress(
            event=self.event, actor=self.owner, plan_id=plan.pk, task_id=task["id"],
            status=TaskProgress.Status.COMPLETED, expected_version=0,
            request_key=uuid.uuid4(), note="Ensayo sintético: revisión manual de la tarea.",
        )
        changed = update_event(
            event_id=self.event.pk, actor=self.owner, title="Título editado por el organizador",
            capacity=37,
        )
        counts = self.counts()
        result = seed_journey_demo(actor=self.owner)
        self.assertFalse(result.created)
        self.assertEqual(result.event.title, changed.title)
        self.assertEqual(result.event.capacity, 37)
        self.assertEqual(result.event.revision, changed.revision)
        self.assertEqual(result.event.active_plan_id, plan.pk)
        progress.refresh_from_db()
        self.assertEqual(progress.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(progress.note, "Ensayo sintético: revisión manual de la tarea.")
        self.assertEqual(self.counts(), counts)

    def test_other_owner_cannot_claim_the_same_fixed_demo(self):
        self.make_demo()
        counts = self.counts()
        with self.assertRaises(PermissionDenied):
            seed_journey_demo(actor=self.other)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(Event.objects.get(pk=JOURNEY_EVENT_ID).owner_id, self.owner.pk)

    def test_reviewer_cannot_create_a_demo_or_modify_an_existing_one(self):
        with self.assertRaises(PermissionDenied):
            seed_journey_demo(actor=self.reviewer)
        self.assertFalse(Event.objects.exists())
        self.make_demo()
        with self.assertRaises(PermissionDenied):
            seed_journey_demo(actor=self.reviewer)
        self.assertEqual(Event.objects.count(), 1)

    def test_inactive_owner_cannot_create_a_demo(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            seed_journey_demo(actor=self.owner)
        self.assertFalse(Event.objects.exists())

    def test_second_demo_does_not_change_the_existing_gica_demo(self):
        gica = seed_demo_event(actor=self.owner).event
        before = Event.objects.values().get(pk=DEMO_EVENT_ID)
        candidates = list(PlanCandidate.objects.filter(event=gica).values())
        revisions = list(PlanRevision.objects.filter(event=gica).values())
        self.make_demo()
        seed_journey_demo(actor=self.owner)
        self.assertNotEqual(JOURNEY_EVENT_ID, DEMO_EVENT_ID)
        self.assertEqual(Event.objects.values().get(pk=DEMO_EVENT_ID), before)
        self.assertEqual(list(PlanCandidate.objects.filter(event=gica).values()), candidates)
        self.assertEqual(list(PlanRevision.objects.filter(event=gica).values()), revisions)

    def test_command_requires_existing_active_owner_and_does_not_create_accounts(self):
        count = get_user_model().objects.count()
        password = self.owner.password
        with self.assertRaises(CommandError):
            call_command("seed_journey_demo", owner="absent-owner", stdout=StringIO())
        output = StringIO()
        call_command("seed_journey_demo", owner=self.owner.username, stdout=output)
        call_command("seed_journey_demo", owner=self.owner.username, stdout=output)
        self.owner.refresh_from_db()
        self.assertEqual(get_user_model().objects.count(), count)
        self.assertEqual(self.owner.password, password)
        self.assertIn(str(JOURNEY_EVENT_ID), output.getvalue())
        self.assertEqual(PlanCandidate.objects.count(), 1)
        self.assertFalse(PlanRevision.objects.exists())


class JourneyProposalTests(_ManualJourneyCase):
    def setUp(self):
        super().setUp()
        self.make_demo()

    def test_pending_baseline_is_reused_without_activation(self):
        pending = self.event.candidates.get()
        self.assertEqual(self.candidate().pk, pending.pk)
        self.assertEqual(self.candidate().pk, pending.pk)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.active_plan_id)
        self.assertEqual(self.event.candidates.count(), 1)

    def test_change_requires_a_plan_and_cannot_approve_itself(self):
        with self.assertRaises(ValidationError):
            self.candidate("change")
        self.assertEqual(self.event.candidates.count(), 1)
        self.assertFalse(PlanRevision.objects.exists())
        plan = self.approve()
        change = self.candidate("change")
        self.assertEqual(change.status, PlanCandidate.Status.PENDING)
        self.assertEqual(change.base_plan_id, plan.pk)
        self.assertEqual(change.base_revision, self.event.revision)
        self.assertEqual(self.candidate("change").pk, change.pk)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, plan.pk)
        self.assertEqual(self.event.plan_revisions.count(), 1)

    def test_baseline_cannot_be_prepared_after_plan_approval(self):
        self.approve()
        counts = self.counts()
        with self.assertRaises(ValidationError):
            self.candidate("baseline")
        self.assertEqual(self.counts(), counts)

    def test_conflicting_schedule_is_rejected_before_persistence(self):
        self.approve()
        counts = self.counts()
        before = Event.objects.values().get(pk=self.event.pk)
        with self.assertRaises(ValidationError) as caught:
            self.candidate("conflict")
        self.assertTrue(caught.exception.messages)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(Event.objects.values().get(pk=self.event.pk), before)

    def test_stale_revision_and_plan_do_not_persist_any_candidate(self):
        stale_revision = self.event.revision
        self.approve()
        counts = self.counts()
        with self.assertRaises(StalePlanError):
            self.candidate("change", expected_revision=stale_revision)
        with self.assertRaises(StalePlanError):
            self.candidate("change", expected_plan_id=None)
        self.assertEqual(self.counts(), counts)

    def test_no_scenario_can_bypass_owner_or_event_scope(self):
        foreign = create_event(actor=self.other, title="Evento ajeno", brief="Privado")
        counts = self.counts()
        for actor, event in ((self.other, self.event), (self.reviewer, self.event), (self.owner, foreign)):
            with self.subTest(actor=actor.pk, event=event.pk), self.assertRaises(PermissionDenied):
                ensure_journey_proposal(
                    actor=actor, event_id=event.pk, scenario="baseline",
                    expected_revision=event.revision, expected_plan_id=event.active_plan_id,
                )
        self.assertEqual(self.counts(), counts)

    def test_scenario_must_be_one_of_the_three_explicit_values(self):
        counts = self.counts()
        for scenario in ("", "auto_approve", "paid", "CHANGE", None):
            with self.subTest(scenario=scenario), self.assertRaises(ValidationError):
                self.candidate(scenario)
        self.assertEqual(self.counts(), counts)

    def test_fixed_examples_cannot_ignore_customized_event_requirements(self):
        self.approve()
        updated = update_event(event_id=self.event.pk, actor=self.owner, capacity=45)
        counts = self.counts()
        with self.assertRaises(ValidationError):
            self.candidate("change")
        self.assertEqual(self.counts(), counts)
        self.event.refresh_from_db()
        self.assertEqual(self.event.capacity, updated.capacity)
        self.assertEqual(self.event.revision, updated.revision)
        self.assertEqual(seed_journey_demo(actor=self.owner).event.capacity, 45)

    def test_fixed_examples_cannot_ignore_customized_interview_answers(self):
        updated = update_interview(
            event_id=self.event.pk, actor=self.owner, expected_revision=self.event.revision,
            question_key="duration_minutes", status="confirmed", value="60",
        )
        counts = self.counts()
        with self.assertRaises(ValidationError):
            self.candidate("baseline")
        self.assertEqual(self.counts(), counts)
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers, updated.interview_answers)
        self.assertEqual(self.event.interview_answers["duration_minutes"]["value"], "60")

    def test_schedule_change_invalidates_rehearsal_and_dependent_closure_only(self):
        plan1 = self.approve()
        for task in plan1.payload["tasks"]:
            update_task_progress(
                event=self.event, actor=self.owner, plan_id=plan1.pk, task_id=task["id"],
                status=TaskProgress.Status.COMPLETED, expected_version=0, request_key=uuid.uuid4(),
                note=f"Ensayo sintético del horario base: revisé {task['id']} en el software.",
            )
        before_records = list(TaskProgress.objects.filter(plan=plan1).order_by("task_id").values())
        before_receipts = list(TaskProgressChange.objects.filter(progress__plan=plan1).order_by("pk").values())
        self.assertEqual(task_tracking_context(self.event)["percentage"], 100)
        plan2 = self.approve(self.candidate("change"))
        progress = task_tracking_context(self.event)
        self.assertEqual(progress["total"], 6)
        self.assertEqual(progress["completed"], 4)
        self.assertEqual(progress["not_started"], 2)
        self.assertEqual(progress["percentage"], 66)
        reset = {"ensayar", "preparar-cierre"}
        displayed_pending = {row["id"] for row in progress["rows"]
                             if row["tracking"]["status"] == TaskProgress.Status.NOT_STARTED}
        self.assertEqual(displayed_pending, reset)
        self.assertFalse(TaskProgress.objects.filter(plan=plan2, task_id__in=reset).exists())
        inherited = list(TaskProgress.objects.filter(plan=plan2).select_related("carried_from"))
        self.assertEqual(len(inherited), 4)
        for record in inherited:
            original = record.carried_from
            self.assertIsNotNone(original)
            self.assertEqual(original.plan_id, plan1.pk)
            self.assertNotIn(record.task_id, reset)
            self.assertEqual(record.status, original.status)
            self.assertEqual(record.note, original.note)
            self.assertEqual(record.updated_by_id, original.updated_by_id)
            self.assertEqual(record.updated_at, original.updated_at)
            self.assertEqual(record.changes.count(), 0)
        self.client.force_login(self.owner)
        guide = reverse("events:journey_demo", kwargs={"event_id": self.event.pk})
        response = self.client.get(guide)
        self.assertEqual(response.context["journey"]["stage"], "tracking")
        self.assertEqual(response.context["progress"]["percentage"], 66)
        for identifier in sorted(reset):
            update_task_progress(
                event=self.event, actor=self.owner, plan_id=plan2.pk, task_id=identifier,
                status=TaskProgress.Status.COMPLETED, expected_version=0, request_key=uuid.uuid4(),
                note="Ensayo sintético: revisé de nuevo la preparación del horario ampliado a 105 minutos.",
            )
        progress = task_tracking_context(self.event)
        self.assertEqual(progress["completed"], 6)
        self.assertEqual(progress["percentage"], 100)
        self.assertEqual(TaskProgressChange.objects.filter(progress__plan=plan2).count(), 2)
        self.assertEqual(list(TaskProgress.objects.filter(plan=plan1).order_by("task_id").values()), before_records)
        self.assertEqual(
            list(TaskProgressChange.objects.filter(progress__plan=plan1).order_by("pk").values()),
            before_receipts,
        )
        response = self.client.get(guide)
        self.assertEqual(response.context["journey"]["stage"], "complete")
        self.assertEqual(response.context["progress"]["percentage"], 100)


class JourneyDemoViewTests(_ManualJourneyCase):
    def setUp(self):
        super().setUp()
        self.make_demo()
        self.client.force_login(self.owner)

    def url(self, event=None):
        return reverse("events:journey_demo", kwargs={"event_id": (event or self.event).pk})

    def scenario_data(self, scenario, **overrides):
        self.event.refresh_from_db()
        data = {
            "action": "scenario", "scenario": scenario,
            "expected_revision": str(self.event.revision),
            "expected_plan_id": str(self.event.active_plan_id or ""),
        }
        data.update(overrides)
        return data

    def approve_over_http(self, candidate):
        response = self.client.post(
            reverse("events:approve", kwargs={"event_id": self.event.pk, "candidate_id": candidate.pk}),
            {"expected_revision": candidate.base_revision,
             "expected_plan": str(candidate.base_plan_id or ""),
             "idempotency_key": str(candidate.pk)},
        )
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, PlanCandidate.Status.APPROVED)
        return self.event.active_plan

    def test_get_is_read_only_and_does_not_claim_an_approved_or_executed_plan(self):
        counts = self.counts()
        for _ in range(2):
            response = self.client.get(self.url())
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, self.event.title)
        self.assertEqual(self.counts(), counts)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.active_plan_id)

    def test_anonymous_foreign_and_reviewer_access_are_denied(self):
        self.client.logout()
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.post(self.url(), self.scenario_data("baseline")).status_code, 404)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(self.client.post(self.url(), self.scenario_data("baseline")).status_code, 403)

    def test_guide_cannot_be_used_to_change_an_unrelated_event(self):
        unrelated = create_event(actor=self.owner, title="Evento normal", brief="Fuera de la demo")
        counts = self.counts()
        self.assertEqual(self.client.get(self.url(unrelated)).status_code, 404)
        self.assertEqual(self.client.post(self.url(unrelated), self.scenario_data("baseline")).status_code, 404)
        self.assertEqual(self.counts(), counts)

    def test_scenario_requires_post_and_csrf(self):
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        counts = self.counts()
        self.assertEqual(secured.post(self.url(), self.scenario_data("baseline")).status_code, 403)
        for method in ("put", "patch", "delete"):
            self.assertEqual(getattr(self.client, method)(self.url()).status_code, 405)
        self.assertEqual(self.counts(), counts)
        secured.get(self.url())
        response = secured.post(
            self.url(), self.scenario_data("baseline"),
            HTTP_X_CSRFTOKEN=secured.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 302)

    def test_stale_post_is_a_visible_conflict_and_creates_nothing(self):
        counts = self.counts()
        response = self.client.post(self.url(), self.scenario_data("baseline", expected_revision="999"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.counts(), counts)
        self.assertContains(response, "camb", status_code=409)

    def test_unknown_and_malformed_scenarios_are_not_saved(self):
        counts = self.counts()
        for data in (
            self.scenario_data("other"),
            self.scenario_data("baseline", action="approve"),
            self.scenario_data("baseline", expected_revision="x"),
            self.scenario_data("baseline", expected_plan_id="invalid"),
        ):
            with self.subTest(data=data):
                self.assertEqual(self.client.post(self.url(), data).status_code, 400)
        self.assertEqual(self.counts(), counts)

    def test_explicit_approval_returns_to_guide_and_replay_has_one_effect(self):
        candidate = self.event.candidates.get()
        url = reverse("events:approve", kwargs={"event_id": self.event.pk, "candidate_id": candidate.pk})
        data = {
            "expected_revision": candidate.base_revision,
            "expected_plan": "", "return_to_demo": "1", "idempotency_key": str(candidate.pk),
        }
        self.assertRedirects(self.client.post(url, data), self.url())
        self.event.refresh_from_db()
        snapshot = self.event.revision, self.event.active_plan_id, self.counts()
        self.assertRedirects(self.client.post(url, data), self.url())
        self.event.refresh_from_db()
        self.assertEqual((self.event.revision, self.event.active_plan_id, self.counts()), snapshot)
        self.assertEqual(self.event.plan_revisions.count(), 1)
        self.assertFalse(TaskProgress.objects.exists())

    def test_discard_remains_discarded_after_reload_until_explicit_preparation(self):
        candidate = self.event.candidates.get()
        url = reverse("events:reject", kwargs={"event_id": self.event.pk, "candidate_id": candidate.pk})
        self.assertRedirects(self.client.post(url, {"return_to_demo": "1"}), self.url())
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, PlanCandidate.Status.REJECTED)
        counts = self.counts()
        seed_journey_demo(actor=self.owner)
        self.client.get(self.url())
        self.assertEqual(self.counts(), counts)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.active_plan_id)
        self.assertEqual(self.client.post(self.url(), self.scenario_data("baseline")).status_code, 302)
        fresh = self.event.candidates.get(status=PlanCandidate.Status.PENDING)
        self.assertNotEqual(fresh.pk, candidate.pk)
        self.assertEqual(fresh.payload, candidate.payload)
        self.assertFalse(PlanRevision.objects.exists())

    def test_complete_manual_journey_preserves_progress_and_rejects_conflict(self):
        response = self.client.post(self.url(), self.scenario_data("baseline"))
        self.assertRedirects(response, self.url())
        baseline = self.event.candidates.get(status=PlanCandidate.Status.PENDING)
        self.assertFalse(PlanRevision.objects.exists())
        plan1 = self.approve_over_http(baseline)
        task = self.stable_root_task()
        note = "Ensayo sintético: revisé localmente esta preparación; sin acciones externas."
        response = self.client.post(
            reverse("events:task_progress", kwargs={"event_id": self.event.pk}),
            {"expected_plan": str(plan1.pk), "task_id": task["id"], "expected_version": 0,
             "request_key": str(uuid.uuid4()), "status": TaskProgress.Status.COMPLETED, "note": note},
        )
        self.assertEqual(response.status_code, 302)
        original = TaskProgress.objects.get(plan=plan1, task_id=task["id"])
        self.assertEqual(original.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(original.note, note)
        before_payload = deepcopy(plan1.payload)
        self.assertEqual(self.client.post(self.url(), self.scenario_data("change")).status_code, 302)
        change = self.event.candidates.get(status=PlanCandidate.Status.PENDING)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, plan1.pk)
        plan2 = self.approve_over_http(change)
        self.assertEqual(plan2.version, 2)
        inherited = TaskProgress.objects.get(plan=plan2, task_id=task["id"])
        self.assertEqual(inherited.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(inherited.carried_from_id, original.pk)
        self.assertEqual(inherited.note, original.note)
        self.assertEqual(inherited.updated_by_id, original.updated_by_id)
        self.assertEqual(inherited.updated_at, original.updated_at)
        self.assertEqual(inherited.changes.count(), 0)
        self.assertEqual(original.changes.count(), 1)
        added = {item["id"] for item in plan2.payload["tasks"]} - {item["id"] for item in plan1.payload["tasks"]}
        self.assertFalse(TaskProgress.objects.filter(plan=plan2, task_id__in=added).exists())
        tracking = task_tracking_context(self.event)
        self.assertEqual(tracking["completed"], 1)
        self.assertEqual(tracking["percentage"], 100 // len(plan2.payload["tasks"]))
        counts = self.counts()
        response = self.client.post(self.url(), self.scenario_data("conflict"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.counts(), counts)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, plan2.pk)
        plan1.refresh_from_db()
        self.assertEqual(plan1.payload, before_payload)
        fresh = Client()
        fresh.force_login(self.owner)
        response = fresh.get(reverse("events:detail", kwargs={"event_id": self.event.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["task_tracking"]["completed"], 1)
        self.assertEqual(response.context["task_tracking"]["percentage"], tracking["percentage"])
        self.assertContains(response, f'data-task-percentage="{tracking["percentage"]}"')
        self.assertEqual(fresh.get(self.url()).status_code, 200)

