"""Directory removal preserves event history and blocks reuse of retired IDs."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.events.models import Event
from apps.events.services import archive_event
from apps.directory.models import EventPerson, Organization, Person
from apps.directory.queries import organizations_for, search_people
from apps.directory.services import assign_person, retire_organization, retire_person, upsert_organization, upsert_person


class DirectoryRetirementTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="retirement-owner")
        self.other = get_user_model().objects.create_user(username="retirement-other")
        self.org = upsert_organization(actor=self.owner, name="Gicaingenieros", aliases=["GICA Ingenieros"])
        self.person = upsert_person(actor=self.owner, full_name="Jorge Gayoso", category="speaker",
            email="jorge@example.invalid", organization_id=self.org.pk)
        self.event = Event.objects.create(owner=self.owner, title="Historial", organization=self.org)
        assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker")
        self.client.force_login(self.owner)

    def retire(self):
        archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=self.event.revision)
        retire_person(actor=self.owner, person_id=self.person.pk, expected_version=1)
        retire_organization(actor=self.owner, organization_id=self.org.pk, expected_version=1)

    def test_active_assignments_and_affiliations_require_explicit_resolution(self):
        with self.assertRaises(ValidationError):
            retire_person(actor=self.owner, person_id=self.person.pk, expected_version=1)
        with self.assertRaises(ValidationError):
            retire_organization(actor=self.owner, organization_id=self.org.pk, expected_version=1)
        self.assertIsNone(Person.objects.get(pk=self.person.pk).archived_at)

    def test_retired_names_can_be_registered_again_without_rewriting_history(self):
        self.retire()
        new_org = upsert_organization(actor=self.owner, name="Gicaingenieros", aliases=["GICA Ingenieros"])
        new_person = upsert_person(actor=self.owner, full_name="Jorge Gayoso", category="speaker",
            email="jorge@example.invalid", organization_id=new_org.pk)
        self.assertNotEqual(new_org.pk, self.org.pk)
        self.assertNotEqual(new_person.pk, self.person.pk)
        self.event.refresh_from_db()
        self.assertEqual(self.event.organization_id, self.org.pk)
        self.assertEqual(EventPerson.objects.get(event=self.event).person_id, self.person.pk)
        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(get_user_model().objects.get(pk=self.owner.pk).username, "retirement-owner")

    def test_retired_ids_are_hidden_even_in_inactive_search_and_direct_forms(self):
        self.retire()
        self.assertFalse(organizations_for(self.owner).exists())
        self.assertFalse(search_people(self.owner, include_inactive=True).exists())
        for route, identifier in (("organization_edit", self.org.pk), ("person_edit", self.person.pk)):
            self.assertEqual(self.client.get(reverse("directory:" + route, args=[identifier])).status_code, 404)
        with self.assertRaises(PermissionDenied):
            upsert_person(actor=self.owner, object_id=self.person.pk, expected_version=2,
                full_name="Restaurado", category="speaker")
        with self.assertRaises(ValidationError):
            upsert_person(actor=self.owner, full_name="Otro", category="speaker", organization_id=self.org.pk)
        new_event = Event.objects.create(owner=self.owner, title="Actual")
        with self.assertRaises(PermissionDenied):
            assign_person(actor=self.owner, event_id=new_event.pk, person_id=self.person.pk, role="speaker")

    def test_owner_and_revision_are_required(self):
        for actor, version, expected in ((self.other, 1, PermissionDenied), (self.owner, 0, ValidationError),
                                         (self.owner, True, ValidationError)):
            with self.subTest(actor=actor.pk, version=version), self.assertRaises(expected):
                retire_person(actor=actor, person_id=self.person.pk, expected_version=version)
        self.assertIsNone(Person.objects.get(pk=self.person.pk).archived_at)
