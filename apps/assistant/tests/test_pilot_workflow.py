"""Bounded pilot control and local replacement. Fixture plans are not inference."""
from copy import deepcopy
from datetime import datetime
import json
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.directory.models import DirectoryAudit, EventPerson, Organization, Person
from apps.directory.services import upsert_organization, upsert_person
from apps.events.models import Event
from apps.events.services import create_event, update_event
from apps.jobs.models import Job, UIAction
from apps.planning.models import PlanCandidate, PlanRevision, TaskProgress
from apps.planning.services import approve_candidate, create_candidate
from apps.assistant.demo_pilot import PILOT_EVENT_ID
from apps.assistant.execution import agent_execution
from apps.assistant.pilot_workflow import (
    ANSWER_KEYS, INITIAL_DATE, JORGE_NAME, ORGANIZATION_NAME, PILOT_TITLE,
    ROBERT_NAME, SESSION_KEY, build_pilot_plan,
)


class PilotControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(username="real-pilot-owner")
        cls.other = users.create_user(username="real-pilot-other")
        cls.reviewer = users.create_user(username="real-pilot-reviewer")
        for user, role in ((cls.owner, "organizer"), (cls.other, "organizer"), (cls.reviewer, "reviewer")):
            PortalAccount.objects.create(user=user, role=role)

    def setUp(self):
        self.url = reverse("assistant:pilot_control")
        self.client.force_login(self.owner)

    def tearDown(self):
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(UIAction.objects.count(), 0)
        self.assertEqual(AIUsage.objects.count(), 0)

    def post(self, operation, **values):
        return self.client.post(self.url, {"operation": operation, **values}, content_type="application/json")

    def bootstrap(self):
        response = self.post("bootstrap")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        return response.json()

    def fields(self, bootstrap):
        organization = upsert_organization(actor=self.owner, name=ORGANIZATION_NAME)
        upsert_person(actor=self.owner, full_name=JORGE_NAME, category="speaker", organization_id=organization.pk)
        bootstrap.update(self.bootstrap())
        values = {key: value for key, value in bootstrap["fields"].items() if key not in {"date", "time"}}
        return values | {"organization_id": str(organization.pk), "scheduled_dates": "19/11/2026", "starts_at": "2026-11-19T19:30"}

    def pilot(self):
        bootstrap = self.bootstrap()
        response = self.post("create", run_id=bootstrap["run_id"], fields=self.fields(bootstrap))
        self.assertEqual(response.status_code, 201, response.content)
        return bootstrap, Event.objects.get(pk=PILOT_EVENT_ID)

    def plan(self, bootstrap, event, operation="plan"):
        if operation == "plan":
            # The retired authored programme is only a test fixture for ordinary
            # approval/edit regressions. The UI must use compact inference.
            response = self.post(operation, run_id=bootstrap["run_id"], event_id=str(event.pk), expected_revision=event.revision)
            self.assertEqual(response.status_code, 410, response.content)
            payload = build_pilot_plan(event)
            candidate = PlanCandidate.objects.filter(event=event, payload=payload, status="pending", base_revision=event.revision).first()
            return candidate or create_candidate(event=event, actor=self.owner, payload=payload, base_revision=event.revision, base_plan_id=event.active_plan_id)
        response = self.post(operation, run_id=bootstrap["run_id"], event_id=str(event.pk), expected_revision=event.revision)
        self.assertEqual(response.status_code, 200, response.content)
        return PlanCandidate.objects.get(pk=response.json()["candidate_id"])

    def test_bootstrap_is_idempotent_without_creating_events_or_institutions(self):
        first, second = self.bootstrap(), self.bootstrap()
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["speakers"], second["speakers"])
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(set(Person.objects.values_list("full_name", flat=True)), {ROBERT_NAME})
        self.assertIsNone(first["speakers"]["jorge"])
        self.assertEqual(first["speaker_registration"]["full_name"], "Jorge Gayoso")
        self.assertFalse(Person.objects.filter(is_synthetic=True).exists())
        self.assertEqual(Organization.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 0)
        self.assertFalse(first["fields"]["is_synthetic"])
        self.assertEqual(first["next_date"], "2026-11-26")

    def test_existing_robert_keeps_unac_affiliation(self):
        unac = upsert_organization(actor=self.owner, name="Universidad Nacional del Callao", aliases=["UNAC"])
        robert = upsert_person(actor=self.owner, full_name=ROBERT_NAME, category="speaker", organization_id=unac.pk)
        bootstrap = self.bootstrap()
        self.assertEqual(bootstrap["speakers"]["robert"], str(robert.pk))
        robert.refresh_from_db()
        self.assertEqual(robert.organization_id, unac.pk)

    def test_bootstrap_does_not_select_or_modify_unregistered_replacement(self):
        replacement = upsert_person(actor=self.owner, full_name=JORGE_NAME, category="speaker", is_synthetic=True)
        result = self.bootstrap()
        self.assertIsNone(result["speakers"]["jorge"])
        replacement.refresh_from_db()
        self.assertTrue(replacement.is_synthetic)
        self.assertIsNone(replacement.organization_id)
        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(Organization.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 0)

    def test_failure_after_first_identity_creation_rolls_back_all_directory_writes(self):
        audits = DirectoryAudit.objects.count()
        with patch("apps.assistant.pilot_workflow._pilot", side_effect=ValidationError("Invalid pilot")):
            response = self.post("bootstrap")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Person.objects.count(), 0)
        self.assertFalse(Person.objects.filter(full_name=ROBERT_NAME).exists())
        self.assertEqual(DirectoryAudit.objects.count(), audits)

    def test_ambiguous_existing_identities_are_not_automatically_selected(self):
        for _ in range(2):
            upsert_person(actor=self.owner, full_name=ROBERT_NAME, category="speaker")
        response = self.post("bootstrap")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Person.objects.count(), 2)
        self.assertFalse(Person.objects.filter(full_name=JORGE_NAME).exists())

    def test_anonymous_reviewer_and_server_agent_are_denied(self):
        self.client.logout()
        self.assertEqual(self.post("bootstrap").status_code, 302)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("bootstrap").status_code, 403)
        self.client.force_login(self.owner)
        with agent_execution("gica-1"):
            self.assertEqual(self.post("bootstrap").status_code, 403)
        self.assertEqual(Person.objects.count(), 0)

    def test_http_method_csrf_and_strict_json_are_enforced(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url, {"operation": "bootstrap"}, content_type="application/json").status_code, 403)
        for body in ('[]', '{"operation":"bootstrap","operation":"bootstrap"}', '{"operation":NaN}', '{"operation":"bootstrap","extra":1}', '{'):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.url, body, content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(self.url, '{"operation":"bootstrap"}', content_type="text/plain").status_code, 400)
        self.assertEqual(Person.objects.count(), 0)

    def test_deep_and_oversized_json_fail_closed_without_side_effects(self):
        for body in ('{"operation":"' + 'a' * 30000 + '"}', '[' * 2000 + '0' + ']' * 2000):
            self.assertEqual(self.client.post(self.url, body, content_type="application/json").status_code, 400)
        self.assertEqual(Person.objects.count(), 0)

    def test_run_identifier_owner_and_expiry_are_required(self):
        self.assertEqual(self.post("create", run_id="missing", fields={}).status_code, 409)
        bootstrap = self.bootstrap()
        self.assertEqual(self.post("create", run_id="different", fields={}).status_code, 409)
        session = self.client.session
        session[SESSION_KEY] = {"id": bootstrap["run_id"], "owner": self.other.pk, "expires": 99999999999}
        session.save()
        self.assertEqual(self.post("create", run_id=bootstrap["run_id"], fields={}).status_code, 409)
        session = self.client.session
        session[SESSION_KEY] = {"id": bootstrap["run_id"], "owner": self.owner.pk, "expires": 1}
        session.save()
        self.assertEqual(self.post("create", run_id=bootstrap["run_id"], fields={}).status_code, 409)
        self.assertEqual(Event.objects.count(), 0)

    def test_real_complete_pilot_is_created_once_from_normal_form(self):
        bootstrap, event = self.pilot()
        self.assertEqual(event.title, PILOT_TITLE)
        self.assertEqual(event.scheduled_dates, [INITIAL_DATE])
        self.assertEqual(event.starts_at, datetime(2026, 11, 19, 19, 30, tzinfo=ZoneInfo("America/Lima")))
        self.assertFalse(event.is_synthetic)
        self.assertEqual(event.organization.name, ORGANIZATION_NAME)
        self.assertEqual(set(event.interview_answers), set(ANSWER_KEYS))
        self.assertEqual(event.directory_people.get(role="speaker").person_id, Person.objects.get(full_name=ROBERT_NAME).pk)
        self.assertEqual(event.directory_people.get(role="speaker").status, "planned")
        audits = DirectoryAudit.objects.count()
        retried = self.post("create", run_id=bootstrap["run_id"], fields={})
        self.assertEqual(retried.status_code, 200)
        self.assertFalse(retried.json()["created"])
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(DirectoryAudit.objects.count(), audits)

    def test_create_rejects_partial_fictional_foreign_and_changed_fixed_values(self):
        bootstrap = self.bootstrap()
        fields = self.fields(bootstrap)
        foreign = upsert_person(actor=self.other, full_name=ROBERT_NAME, category="speaker")
        variants = [{key: value for key, value in fields.items() if key != "objective"}]
        variants += [fields | change for change in ({"is_synthetic": True}, {"speaker_id": str(foreign.pk)}, {"capacity": "99"},
                    {"title": "Otro evento"}, {"duration_minutes": "45"}, {"starts_at": "2026-11-26T19:30", "scheduled_dates": "26/11/2026"})]
        for values in variants:
            with self.subTest(values=values):
                self.assertEqual(self.post("create", run_id=bootstrap["run_id"], fields=values).status_code, 400)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(EventPerson.objects.count(), 0)

    def test_another_owner_occupying_fixed_uuid_is_never_modified(self):
        bootstrap = self.bootstrap()
        other_event = create_event(actor=self.other, event_id=PILOT_EVENT_ID, title=PILOT_TITLE, brief="Piloto de otra cuenta")
        response = self.post("create", run_id=bootstrap["run_id"], fields={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.post("bootstrap").status_code, 403)
        other_event.refresh_from_db()
        self.assertEqual(other_event.owner_id, self.other.pk)
        self.assertEqual(other_event.revision, 1)

    def test_retired_plan_endpoint_rejects_generation_and_fixture_requires_manual_approval(self):
        bootstrap, event = self.pilot()
        candidate = self.plan(bootstrap, event)
        self.assertFalse(candidate.validation)
        self.assertEqual(len(candidate.payload["sessions"]), 5)
        self.assertEqual(sum(row["duration_minutes"] for row in candidate.payload["sessions"]), 90)
        self.assertEqual(len(candidate.payload["tasks"]), 11)
        self.assertEqual({row["status"] for row in candidate.payload["tasks"]}, {"pending"})
        event.refresh_from_db()
        self.assertIsNone(event.active_plan_id)
        self.assertEqual(PlanRevision.objects.count(), 0)
        retried = self.plan(bootstrap, event)
        self.assertEqual(retried.pk, candidate.pk)
        response = self.client.post(reverse("events:approve", args=[event.pk, candidate.pk]), {"expected_revision": "1", "expected_plan": ""})
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertIsNotNone(event.active_plan_id)
        self.assertEqual(event.active_plan.version, 1)
        self.assertEqual(event.revision, 2)

    def test_existing_manual_candidate_is_not_reused_or_overwritten_by_pilot(self):
        bootstrap, event = self.pilot()
        manual = build_pilot_plan(event); manual["summary"] = "Una propuesta redactada manualmente por el organizador."
        existing = create_candidate(event=event, actor=self.owner, payload=manual, base_revision=event.revision, base_plan_id=None)
        generated = self.plan(bootstrap, event)
        self.assertNotEqual(existing.pk, generated.pk)
        existing.refresh_from_db()
        self.assertEqual(existing.payload, manual)
        self.assertEqual(existing.status, "pending")

    def test_stale_or_foreign_event_reference_cannot_prepare_proposal(self):
        bootstrap, event = self.pilot()
        self.assertEqual(self.post("plan", run_id=bootstrap["run_id"], event_id=str(event.pk), expected_revision=0).status_code, 409)
        self.assertEqual(self.post("plan", run_id=bootstrap["run_id"], event_id=str(event.pk), expected_revision=True).status_code, 409)
        self.assertEqual(self.post("plan", run_id=bootstrap["run_id"], event_id="foreign", expected_revision=1).status_code, 404)
        self.assertEqual(PlanCandidate.objects.count(), 0)

    def test_change_to_jorge_keeps_hours_content_and_approved_history_until_second_approval(self):
        bootstrap, event = self.pilot()
        initial = self.plan(bootstrap, event)
        version_one = approve_candidate(candidate_id=initial.pk, actor=self.owner)
        snapshot = deepcopy(version_one.payload)
        event.refresh_from_db()
        event = update_event(event_id=event.pk, actor=self.owner, speaker_id=bootstrap["speakers"]["jorge"])
        revision_before = event.revision
        replanned = self.plan(bootstrap, event, operation="replan")
        event.refresh_from_db()
        self.assertEqual(event.active_plan_id, version_one.pk)
        self.assertEqual(event.revision, revision_before)
        self.assertEqual({row["speaker"] for row in replanned.payload["sessions"]}, {JORGE_NAME})
        self.assertEqual([row["start"] for row in replanned.payload["sessions"]], [row["start"] for row in snapshot["sessions"]])
        self.assertEqual(event.directory_people.get(person_id=bootstrap["speakers"]["robert"]).status, "cancelled")
        version_two = approve_candidate(candidate_id=replanned.pk, actor=self.owner)
        version_one.refresh_from_db()
        self.assertEqual(version_one.payload, snapshot)
        self.assertEqual(version_two.version, 2)
        self.assertEqual(PlanRevision.objects.count(), 2)
        self.assertEqual(TaskProgress.objects.count(), 0)
