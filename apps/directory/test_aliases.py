from io import StringIO
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assistant.models import EventCreationDraft
from apps.events.models import Event
from apps.planning.models import PlanCandidate, PlanRevision, TaskPreparation
from .forms import OrganizationForm, PersonForm
from .models import DirectoryAudit, EventPerson, Organization, Person
from .queries import exact_directory_matches, search_people
from .services import assign_person, upsert_organization, upsert_person


class DirectoryAliasTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="alias-owner")
        self.other = get_user_model().objects.create_user(username="alias-other")
        self.org = upsert_organization(actor=self.owner, name="Universidad Nacional del Callao - UNAC",
            aliases=["UNAC", "Universidad Nacional del Callao"])
        self.person = upsert_person(actor=self.owner, full_name="Dr. Robert Castillo Alva", category="speaker",
            aliases=["Robert", "Robert Castillo Alva"], organization_id=self.org.pk)

    def test_exact_alias_case_accents_spaces_and_owner_scope(self):
        self.assertEqual(list(exact_directory_matches(self.owner, "  unac  ")), [self.org])
        self.assertEqual(list(exact_directory_matches(self.owner, "Robert", kind="person")), [self.person])
        self.assertFalse(exact_directory_matches(self.other, "UNAC").exists())
        self.assertFalse(exact_directory_matches(self.owner, "UNA").exists())
        self.assertEqual(search_people(self.owner, query="Universidad Nacional del Callao").get(), self.person)

    def test_duplicate_aliases_normalized_but_ambiguous_names_not_merged(self):
        other = upsert_person(actor=self.owner, full_name="Otro Robert", category="speaker", aliases=["ROBERT", "Robert"])
        self.assertEqual(other.aliases, ["ROBERT"])
        self.assertEqual(exact_directory_matches(self.owner, "Robert", kind="person").count(), 2)
        self.assertEqual(Person.objects.count(), 2)

    def test_manual_forms_roundtrip_and_validation(self):
        form = OrganizationForm({"name": "Institución", "aliases": "ABC\nNombre largo\nabc", "is_active": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["aliases"], ["ABC", "Nombre largo"])
        self.assertIn("Robert\n", PersonForm(actor=self.owner, instance=self.person).initial["aliases"])
        for aliases in (["x"] * 13, ["x\nmal"], "UNAC", ["\ufdfa" * 160]):
            with self.subTest(aliases_type=type(aliases).__name__), self.assertRaises(ValidationError):
                upsert_organization(actor=self.owner, name="Inválida", aliases=aliases)

    def test_alias_omission_preserves_existing_and_archived_not_resolved(self):
        person = upsert_person(actor=self.owner, object_id=self.person.pk, expected_version=1,
            full_name=self.person.full_name, category="speaker", organization_id=self.org.pk)
        self.assertEqual(person.aliases, self.person.aliases)
        self.assertEqual(person.version, 1)
        Person.objects.filter(pk=person.pk).update(is_active=False)
        self.assertFalse(exact_directory_matches(self.owner, "Robert", kind="person").exists())

    def test_manual_organization_name_cannot_duplicate_an_existing_alias(self):
        with self.assertRaises(ValidationError):
            upsert_organization(actor=self.owner, name="unac")
        self.assertEqual(Organization.objects.filter(owner=self.owner).count(), 1)

    def test_http_manual_alias_edit_is_scoped_and_persisted(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("directory:organization_edit", args=[self.org.pk]),
            {"name": self.org.name, "aliases": "UNAC\nUniversidad Nacional del Callao", "is_active": "on", "expected_version": 1})
        self.assertEqual(response.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.version, 1)
        self.assertEqual(self.client.get(reverse("directory:index"), {"tab": "organizations", "q": "UNAC"}).status_code, 200)


class DirectoryResetTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="reset-owner")
        self.other = get_user_model().objects.create_user(username="reset-other")
        self.org = upsert_organization(actor=self.owner, name="Organización obsoleta")
        self.person = upsert_person(actor=self.owner, full_name="Persona obsoleta", category="speaker", organization_id=self.org.pk)
        self.event = Event.objects.create(owner=self.owner, title="Conservar", brief="Historia", organization=self.org)
        assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker")
        self.foreign_org = upsert_organization(actor=self.other, name="Ajena")

    def run_reset(self, **options):
        output = StringIO()
        call_command("reset_owner_directory", owner=self.owner.username, stdout=output, **options)
        return output.getvalue()

    def test_dry_run_is_read_only_apply_preserves_events_and_other_owners(self):
        before = DirectoryAudit.objects.count()
        self.run_reset(dry_run=True)
        self.assertEqual(DirectoryAudit.objects.count(), before)
        self.assertTrue(Person.objects.filter(pk=self.person.pk).exists())
        self.run_reset(apply=True)
        self.assertEqual(list(Organization.objects.filter(owner=self.owner).values_list("name", flat=True)), ["Universidad Nacional del Callao - UNAC"])
        self.assertEqual(list(Person.objects.filter(owner=self.owner).values_list("full_name", flat=True)), ["Dr. Robert Castillo Alva"])
        self.assertTrue(Organization.objects.filter(pk=self.foreign_org.pk).exists())
        self.event.refresh_from_db()
        self.assertIsNone(self.event.organization_id)
        self.assertEqual(self.event.revision, 2)
        self.assertEqual(self.event.brief, "Historia")
        self.assertEqual(EventPerson.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 1)

    def test_second_run_has_stable_identity_versions_and_audit(self):
        self.run_reset(apply=True)
        before = {model.__name__: list(model.objects.order_by("pk").values())
            for model in (Organization, Person, Event, DirectoryAudit)}
        self.run_reset(apply=True)
        self.assertEqual(before, {model.__name__: list(model.objects.order_by("pk").values())
            for model in (Organization, Person, Event, DirectoryAudit)})

    def test_foreign_references_abort_without_partial_deletion(self):
        foreign_event = Event.objects.create(owner=self.other, title="Ajeno", brief="Conservar", organization=self.org)
        before = DirectoryAudit.objects.count()
        with self.assertRaises(CommandError):
            self.run_reset(apply=True)
        self.assertTrue(Person.objects.filter(pk=self.person.pk).exists())
        self.assertTrue(EventPerson.objects.exists())
        self.assertEqual(DirectoryAudit.objects.count(), before)
        self.assertEqual(Event.objects.get(pk=foreign_event.pk).organization_id, self.org.pk)

    def test_preparation_responsibility_is_protected_without_deleting_evidence(self):
        candidate = PlanCandidate.objects.create(event=self.event, payload={}, base_revision=1, created_by=self.owner)
        plan = PlanRevision.objects.create(event=self.event, candidate=candidate, version=1, payload={}, approved_by=self.owner)
        preparation = TaskPreparation.objects.create(plan=plan, task_id="t1", responsible_person=self.person,
            responsible_person_version=1, updated_by=self.owner, evidence_note="Declaración conservada")
        with self.assertRaises(CommandError):
            self.run_reset(apply=True)
        self.assertEqual(TaskPreparation.objects.get(pk=preparation.pk).evidence_note, "Declaración conservada")
        self.assertTrue(Person.objects.filter(pk=self.person.pk).exists())

    def test_only_obsolete_draft_links_and_replay_are_cleared(self):
        draft = EventCreationDraft.objects.create(owner=self.owner, expires_at=timezone.now() + timedelta(hours=24),
            data={"title": "Guardar título", "organization_id": str(self.org.pk), "organization_name": self.org.name,
                  "directory_people": [{"id": str(self.person.pk), "name": self.person.full_name, "role": "speaker"}]},
            last_request_id=uuid4(), last_response={"old": True}, last_request_hash="old")
        self.run_reset(apply=True)
        draft.refresh_from_db()
        self.assertEqual(draft.data["title"], "Guardar título")
        self.assertIsNone(draft.data["organization_id"])
        self.assertEqual(draft.data["directory_people"], [])
        self.assertEqual(draft.revision, 2)
        self.assertIsNone(draft.last_request_id)
        self.assertEqual(draft.last_response, {})
