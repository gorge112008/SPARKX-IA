"""Business permissions, stale writes, minimal reads and plan preservation."""
import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.events.forms import EventForm
from apps.events.models import Event
from apps.jobs.models import Job
from .models import DirectoryAudit, EventPerson, Organization, Person
from .normalization import search_key
from .queries import event_people, organizations_for, search_people
from .services import assign_person, upsert_organization, upsert_person
from .tools import execute_tool


class DirectoryTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="directory-owner")
        self.other = users.objects.create_user(username="directory-other")
        self.admin = users.objects.create_user(username="directory-admin", is_staff=True)
        self.reviewer = users.objects.create_user(username="directory-reviewer")
        PortalAccount.objects.create(user=self.reviewer, role="reviewer")
        self.org = upsert_organization(actor=self.owner, name="Institución de Prueba")
        self.foreign_org = upsert_organization(actor=self.other, name="Empresa privada ajena")
        self.person = upsert_person(actor=self.owner, full_name="José Pérez", category="speaker",
            email="jose@example.invalid", organization_id=self.org.pk, expertise="Metodología")
        self.foreign_person = upsert_person(actor=self.other, full_name="Persona privada ajena", category="guest",
            email="private@example.invalid", organization_id=self.foreign_org.pk)
        self.event = Event.objects.create(owner=self.owner, title="Evento propio", brief="Contenido local", organization=self.org)
        self.foreign_event = Event.objects.create(owner=self.other, title="Evento privado ajeno", brief="Otro contexto", organization=self.foreign_org)
        self.client.force_login(self.owner)

    def test_normalization_is_shared_but_homonyms_are_not_merged(self):
        self.assertEqual(search_key("  JOSÉ  Pérez "), "jose perez")
        second = upsert_person(actor=self.owner, full_name="JOSE PEREZ", category="participant")
        self.assertNotEqual(second.pk, self.person.pk)
        self.assertEqual(search_people(self.owner, query="jose").count(), 2)

    def test_duplicate_email_and_organization_rejected_only_within_owner(self):
        with self.assertRaises(ValidationError):
            upsert_person(actor=self.owner, full_name="Otro nombre", category="guest", email="JOSE@EXAMPLE.INVALID")
        with self.assertRaises(ValidationError):
            upsert_organization(actor=self.owner, name="  INSTITUCION de prueba ")
        other = upsert_person(actor=self.other, full_name="José Pérez", category="speaker", email="jose@example.invalid")
        self.assertNotEqual(other.pk, self.person.pk)

    def test_unicode_expansion_rejected_before_database_save(self):
        text = "\ufdfa" * 160
        self.assertGreater(len(search_key(text)), 320)
        for operation in (
            lambda: upsert_organization(actor=self.owner, name=text),
            lambda: upsert_person(actor=self.owner, full_name=text, category="guest"),
        ):
            with self.assertRaises(ValidationError):
                operation()

    def test_form_does_not_offer_or_accept_foreign_organization(self):
        form = EventForm(actor=self.owner)
        self.assertNotIn(self.foreign_org, form.fields["organization_id"].queryset)
        form = EventForm({"title": "Prueba", "brief": "Descripción", "timezone": "America/Lima", "capacity": "20",
                          "organization_id": str(self.foreign_org.pk)}, actor=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn("organization_id", form.errors)

    def test_person_cannot_reference_foreign_organization(self):
        with self.assertRaises(ValidationError):
            upsert_person(actor=self.owner, full_name="Prueba", category="speaker", organization_id=self.foreign_org.pk)

    def test_services_require_current_role_and_active_user(self):
        for actor in (self.reviewer,):
            with self.assertRaises(PermissionDenied):
                upsert_organization(actor=actor, name="No permitido")
            with self.assertRaises(PermissionDenied):
                execute_tool(actor=actor, name="search_people", arguments={})
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            upsert_organization(actor=self.owner, name="Actor desactivado con objeto obsoleto")
        with self.assertRaises(PermissionDenied):
            execute_tool(actor=self.owner, name="search_events", arguments={})

    def test_admin_does_not_inherit_other_owners_directory(self):
        self.assertEqual(search_people(self.admin).count(), 0)
        self.assertEqual(organizations_for(self.admin).count(), 0)
        with self.assertRaises(PermissionDenied):
            upsert_person(actor=self.admin, object_id=self.person.pk, expected_version=1, full_name="Cambio ajeno", category="guest")

    def test_stale_or_missing_version_does_not_overwrite(self):
        for version in (None, 0, True, 2):
            with self.subTest(version=version), self.assertRaises(ValidationError) as caught:
                upsert_person(actor=self.owner, object_id=self.person.pk, expected_version=version,
                              full_name="Sobrescritura", category="speaker")
            self.assertEqual(caught.exception.code, "stale_directory")
        self.person.refresh_from_db()
        self.assertEqual(self.person.full_name, "José Pérez")

    def test_identical_save_keeps_version_and_audit_unchanged(self):
        before = DirectoryAudit.objects.count()
        record = upsert_person(actor=self.owner, object_id=self.person.pk, expected_version=1,
            full_name=self.person.full_name, category=self.person.category, email=self.person.email,
            expertise=self.person.expertise, organization_id=self.org.pk)
        self.assertEqual(record.version, 1)
        self.assertEqual(DirectoryAudit.objects.count(), before)

    def test_archival_keeps_history_and_requires_reactivation_for_assignment(self):
        link = assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker")
        upsert_person(actor=self.owner, object_id=self.person.pk, expected_version=1, full_name=self.person.full_name,
                      category="speaker", email=self.person.email, is_active=False)
        self.assertEqual(search_people(self.owner).count(), 0)
        self.assertEqual(search_people(self.owner, include_inactive=True).count(), 1)
        self.assertTrue(EventPerson.objects.filter(pk=link.pk).exists())
        with self.assertRaises(ValidationError):
            assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="guest")

    def test_link_preserves_plan_revision_and_does_not_claim_attendance(self):
        before = self.event.revision
        link = assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="participant")
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, before)
        self.assertIsNone(self.event.active_plan_id)
        self.assertEqual(link.status, "planned")

    def test_link_cross_owner_and_stale_status_are_rejected(self):
        for event, person in ((self.event, self.foreign_person), (self.foreign_event, self.person)):
            with self.assertRaises(PermissionDenied):
                assign_person(actor=self.owner, event_id=event.pk, person_id=person.pk, role="speaker")
        assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker")
        with self.assertRaises(ValidationError):
            assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role="speaker", status="confirmed", expected_version=0)

    def test_same_person_can_have_distinct_event_roles(self):
        for role in ("speaker", "guest"):
            assign_person(actor=self.owner, event_id=self.event.pk, person_id=self.person.pk, role=role)
        self.assertEqual(event_people(self.owner, self.event.pk).count(), 2)

    def test_corrupt_affiliation_and_link_do_not_disclose_foreign_data(self):
        Person.objects.filter(pk=self.person.pk).update(organization=self.foreign_org)
        EventPerson.objects.create(event=self.event, person=self.foreign_person, role="guest")
        self.assertEqual(search_people(self.owner).count(), 0)
        self.assertEqual(event_people(self.owner, self.event.pk).count(), 0)
        result = execute_tool(actor=self.owner, name="search_people", arguments={})
        self.assertNotIn("Empresa privada ajena", json.dumps(result))

    def test_tool_allowlist_types_bounds_and_argument_names(self):
        for name, arguments in (("delete_person", {}), ("search_people", {"owner": self.other.pk}),
             ("search_people", {"limit": True}), ("search_people", {"limit": 21}),
             ("search_people", {"q": "x" * 201}), ("search_people", {"category": "admin"}),
             ("search_people", {"organization": "bad-uuid"}), ("event_people", {"event": str(uuid4())})):
            with self.subTest(name=name, arguments=arguments), self.assertRaises(ValidationError):
                execute_tool(actor=self.owner, name=name, arguments=arguments)

    def test_tool_returns_minimal_fields_and_no_model_or_job(self):
        before = (Job.objects.count(), AIUsage.objects.count(), DirectoryAudit.objects.count())
        result = execute_tool(actor=self.owner, name="search_people", arguments={"q": "jose"})
        self.assertEqual(result["total"], 1)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["model_invoked"])
        self.assertNotIn(self.person.email, json.dumps(result))
        self.assertNotIn("expertise", result["items"][0])
        self.assertEqual(before, (Job.objects.count(), AIUsage.objects.count(), DirectoryAudit.objects.count()))

    def test_tool_event_search_matches_calendar_scope_and_limits(self):
        for i in range(3):
            Event.objects.create(owner=self.owner, title=f"Taller {i}", brief="Datos", organization=self.org)
        result = execute_tool(actor=self.owner, name="search_events", arguments={"q": "taller", "limit": 2})
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(result["has_more"])
        self.assertNotIn("brief", result["items"][0])
        self.assertNotIn("Evento privado ajeno", json.dumps(result))

    def test_tool_endpoint_read_only_and_unknown_fields_rejected(self):
        url = reverse("directory:tools")
        self.assertEqual(self.client.post(url, {}).status_code, 405)
        self.assertEqual(self.client.get(url, {"tool": "search_people", "owner_id": self.other.pk}).status_code, 400)
        response = self.client.get(url, {"tool": "search_people", "q": "jose"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_directory_http_isolation_escaping_and_reviewer_block(self):
        self.person.full_name = "<script>directory</script>"
        self.person.save(update_fields=["full_name"])
        response = self.client.get(reverse("directory:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Persona privada ajena")
        self.assertContains(response, "&lt;script&gt;directory&lt;/script&gt;")
        self.assertNotContains(response, "<script>directory</script>")
        self.assertEqual(self.client.get(reverse("directory:person_edit", args=[self.foreign_person.pk])).status_code, 404)
        self.client.force_login(self.reviewer)
        for url in (reverse("directory:index"), reverse("directory:roster", args=[self.event.pk]), reverse("directory:tools")):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_create_contact_never_creates_login_account(self):
        before = get_user_model().objects.count()
        upsert_person(actor=self.owner, full_name="Contacto sin acceso", category="guest")
        self.assertEqual(get_user_model().objects.count(), before)

    def test_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("directory:organization_create"), {"name": "Sin token"}).status_code, 403)

    def test_audit_does_not_store_personal_values(self):
        content = json.dumps(list(DirectoryAudit.objects.values("entity_type", "action", "changed_fields")))
        self.assertNotIn(self.person.email, content)
        self.assertNotIn(self.person.full_name, content)

    def test_roster_authorization_queries_do_not_grow_per_row(self):
        url = reverse("directory:roster", args=[self.event.pk])
        with CaptureQueriesContext(connection) as empty:
            self.assertEqual(self.client.get(url).status_code, 200)
        for index in range(5):
            person = upsert_person(actor=self.owner, full_name=f"Contacto {index}", category="guest")
            assign_person(actor=self.owner, event_id=self.event.pk, person_id=person.pk, role="guest")
        with CaptureQueriesContext(connection) as populated:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertLessEqual(len(populated), len(empty) + 1)

