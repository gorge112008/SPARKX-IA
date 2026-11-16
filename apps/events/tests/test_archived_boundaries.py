"""Retirement blocks operational routes without erasing historical records.

All data and commands use the isolated test database, with no model/network.
"""
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.directory.models import DirectoryAudit, EventPerson
from apps.directory.queries import event_people
from apps.directory.services import assign_person, upsert_person
from apps.directory.tools import execute_tool
from apps.planning.event_rules import validate_event_plan
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan
from apps.registration.models import Registration, RegistrationPage, RegistrationSubmission
from apps.registration.services import RECEIPT_MESSAGE, set_registration_state, submission_token, submit_registration
from apps.events.models import Event
from apps.events.services import archive_event, create_event
from apps.events.tests import test_constraints_integration as constraint_fixtures


class ArchivedEventBoundaryTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="archive-boundary-owner")
        self.event = create_event(actor=self.owner, title="Evento retirado", brief="Ficha privada", capacity=5)
        self.payload = valid_plan()
        candidate = create_candidate(event=self.event, actor=self.owner, payload=self.payload, base_revision=self.event.revision)
        self.plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        self.page = set_registration_state(event_id=self.event.pk, actor=self.owner, action="open", expected_version=0,
            expected_revision=self.event.revision, expected_plan=self.plan.pk, confirmed=True)
        self.person = upsert_person(actor=self.owner, full_name="Expositor de prueba", category="speaker")
        self.link = assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker")
        self.client.force_login(self.owner)

    def retire(self):
        self.event = archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=self.event.revision)

    def test_public_urls_hide_retired_page_and_stale_form_cannot_add_a_seat(self):
        existing_key = submission_token(self.page)
        submit_registration(token=self.page.public_token, full_name="Participante existente", email="existing@example.test", form_token=existing_key)
        stale_key = submission_token(self.page)
        before = (Registration.objects.count(), RegistrationSubmission.objects.count())
        self.retire()
        public = Client()
        url = reverse("event_registration:public", args=[self.page.public_token])
        self.assertEqual(public.get(url).status_code, 404)
        self.assertEqual(public.post(url, {"full_name": "Otro participante", "email": "other@example.test", "form_token": stale_key}).status_code, 404)
        self.assertEqual(public.get(reverse("event_registration:received", args=[self.page.public_token])).status_code, 404)
        receipt = submit_registration(token=self.page.public_token, full_name="Otro participante", email="other@example.test", form_token=stale_key)
        self.assertEqual(receipt, RECEIPT_MESSAGE)
        self.assertEqual((Registration.objects.count(), RegistrationSubmission.objects.count()), before)
        self.assertEqual(Registration.objects.get().full_name, "Participante existente")
        self.assertTrue(RegistrationPage.objects.filter(pk=self.page.pk).exists())

    def test_owner_cannot_republish_or_manage_retired_registration(self):
        self.retire()
        for action in ("open", "closed"):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                set_registration_state(event_id=self.event.pk, actor=self.owner, action=action, expected_version=self.page.version,
                    expected_revision=self.event.revision, expected_plan=self.plan.pk, confirmed=True)
        self.assertEqual(self.client.get(reverse("event_registration:manage", args=[self.event.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("event_registration:change_state", args=[self.event.pk]), {}).status_code, 404)
        self.page.refresh_from_db()
        self.assertEqual((self.page.version, self.page.state), (1, "open"))

    def test_roster_get_post_and_service_cannot_mutate_retired_assignments(self):
        before = DirectoryAudit.objects.count()
        self.retire()
        url = reverse("directory:roster", args=[self.event.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"person": self.person.pk, "role": "speaker", "status": "cancelled", "expected_version": 1}).status_code, 404)
        with self.assertRaises(PermissionDenied):
            assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker", status="cancelled", expected_version=1)
        self.link.refresh_from_db()
        self.assertEqual((self.link.status, self.link.version), ("planned", 1))
        self.assertEqual(DirectoryAudit.objects.count(), before)
        self.assertEqual(EventPerson.objects.count(), 1)

    def test_schedule_direct_urls_are_retired_without_erasing_approved_history(self):
        self.retire()
        url = reverse("events:schedule_editor", args=[self.event.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.assertEqual(PlanCandidate.objects.count(), 1)
        self.assertEqual(PlanRevision.objects.count(), 1)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.payload, self.payload)
        self.assertEqual(self.event.active_plan_id, self.plan.pk)

    def test_mechanical_directory_tools_cannot_return_retired_event_people(self):
        self.assertEqual(event_people(self.owner, self.event.pk).count(), 1)
        self.assertEqual(execute_tool(actor=self.owner, name="event_people", arguments={"event": str(self.event.pk)})["total"], 1)
        self.retire()
        with self.assertRaises(Event.DoesNotExist):
            event_people(self.owner, self.event.pk)
        with self.assertRaises(ValidationError):
            execute_tool(actor=self.owner, name="event_people", arguments={"event": str(self.event.pk)})
        self.assertTrue(EventPerson.objects.filter(pk=self.link.pk).exists())


class ArchivedReservationTests(TestCase):
    setUp = constraint_fixtures.EventConstraintIntegrationTests.setUp
    approve = constraint_fixtures.EventConstraintIntegrationTests.approve
    save_constraints = constraint_fixtures.EventConstraintIntegrationTests.save_constraints

    def test_archived_approved_agenda_no_longer_reserves_speaker_or_resource(self):
        self.approve(); self.save_constraints()
        other = Event.objects.create(owner=self.owner, title="Reserva anterior", brief="Historial conservado")
        old_plan = self.approve(other)
        before = deepcopy(old_plan.payload)
        self.assertTrue(validate_event_plan(self.event, self.plan))
        archive_event(actor=self.owner, event_id=other.pk, expected_revision=other.revision)
        self.assertEqual(validate_event_plan(self.event, self.plan), [])
        old_plan.refresh_from_db()
        self.assertEqual(old_plan.payload, before)
        self.assertTrue(Event.objects.filter(pk=other.pk, active_plan=old_plan, archived_at__isnull=False).exists())
