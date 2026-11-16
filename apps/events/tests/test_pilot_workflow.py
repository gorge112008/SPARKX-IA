"""Real form persistence, private speaker selection and replacement safeguards."""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.directory.models import DirectoryAudit, EventPerson
from apps.directory.services import upsert_organization, upsert_person
from apps.events.forms import EventEditForm, EventForm
from apps.events.models import Event
from apps.events.services import create_event, update_event


class PilotWorkflowFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="pilot-organizer")
        cls.other = get_user_model().objects.create_user(username="other-pilot-organizer")
        cls.unac = upsert_organization(actor=cls.owner, name="Universidad Nacional del Callao", aliases=["UNAC"])
        cls.gica = upsert_organization(actor=cls.owner, name="Gicaingenieros")
        cls.robert = upsert_person(actor=cls.owner, full_name="Dr. Robert Castillo Alva", category="speaker", organization_id=cls.unac.pk)
        cls.jorge = upsert_person(actor=cls.owner, full_name="Jorge Gayoso Ugas", category="speaker")
        cls.foreign = upsert_person(actor=cls.other, full_name="Expositor de otro espacio", category="speaker")

    def data(self):
        return {
            "title": "Gestión estratégica del mantenimiento",
            "brief": "Seminario piloto de planificación del mantenimiento.",
            "organization_id": str(self.gica.pk), "speaker_id": str(self.robert.pk),
            "scheduled_dates": "19/11/2026", "starts_at": "2026-11-19T19:30",
            "timezone": "America/Lima", "capacity": "100",
            "objective": "Desarrollar una estrategia de mantenimiento.",
            "audience": "Profesionales de industria, minería y energía.",
            "modality": "Virtual", "duration_minutes": "90", "location": "Zoom · enlace por confirmar",
            "resources": "Expositor del directorio y material por confirmar.",
            "constraints": "Ingreso libre; sin pagos ni envíos automáticos.",
        }

    def event(self):
        form = EventForm(self.data(), actor=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        return create_event(actor=self.owner, **form.cleaned_data)

    def test_all_seven_inputs_and_speaker_are_persisted_atomically(self):
        event = self.event()
        self.assertEqual(event.organization, self.gica)
        self.assertEqual(event.interview_answers["duration_minutes"], {"status": "confirmed", "value": "90"})
        self.assertEqual(len(event.interview_answers), 7)
        self.assertFalse(event.is_synthetic)
        link = event.directory_people.get(role="speaker")
        self.assertEqual(link.person, self.robert)
        self.assertEqual(link.status, EventPerson.Status.PLANNED)
        self.robert.refresh_from_db()
        self.assertEqual(self.robert.organization, self.unac)
        self.assertIsNone(event.active_plan_id)

    def test_edit_replaces_speaker_and_moves_date_without_affiliation_or_plan_changes(self):
        event = self.event()
        data = self.data() | {"expected_revision": "1", "speaker_id": str(self.jorge.pk),
                              "scheduled_dates": "26/11/2026", "starts_at": "2026-11-26T19:30"}
        form = EventEditForm(data, instance=event, actor=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        values = {key: value for key, value in form.cleaned_data.items() if key != "expected_revision"}
        event = update_event(event_id=event.pk, actor=self.owner, **values)
        self.assertEqual(event.revision, 2)
        self.assertEqual(event.scheduled_dates, ["2026-11-26"])
        self.assertEqual(event.starts_at, datetime(2026, 11, 26, 19, 30, tzinfo=ZoneInfo("America/Lima")))
        self.assertEqual(event.directory_people.get(person=self.robert).status, "cancelled")
        self.assertEqual(event.directory_people.get(person=self.jorge).status, "planned")
        self.assertEqual(DirectoryAudit.objects.filter(entity_type="eventperson", action="assign").count(), 3)
        self.assertEqual(len(event.interview_answers), 7)
        self.assertIsNone(event.active_plan_id)
        self.robert.refresh_from_db()
        self.assertEqual(self.robert.organization, self.unac)

    def test_speaker_only_change_invalidates_old_event_snapshot_once(self):
        event = self.event()
        event = update_event(event_id=event.pk, actor=self.owner, speaker_id=self.jorge.pk)
        self.assertEqual(event.revision, 2)
        unchanged = update_event(event_id=event.pk, actor=self.owner, speaker_id=self.jorge.pk)
        self.assertEqual(unchanged.revision, 2)

    def test_explicitly_clearing_speaker_cancels_assignment(self):
        event = self.event()
        event = update_event(event_id=event.pk, actor=self.owner, speaker_id=None)
        self.assertEqual(event.directory_people.get(person=self.robert).status, "cancelled")
        self.assertEqual(event.revision, 2)

    def test_omitted_new_controls_do_not_clear_existing_data(self):
        event = self.event()
        event.interview_answers["objective"]["status"] = "assumed"
        event.save(update_fields=["interview_answers"])
        before = event.interview_answers
        data = {key: value for key, value in self.data().items()
                if key not in {"speaker_id", *before.keys()}}
        data.update(expected_revision="1", capacity="50")
        form = EventEditForm(data, instance=event, actor=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("speaker_id", form.cleaned_data)
        self.assertNotIn("interview_answers", form.cleaned_data)
        values = {key: value for key, value in form.cleaned_data.items() if key != "expected_revision"}
        updated = update_event(event_id=event.pk, actor=self.owner, **values)
        self.assertEqual(updated.interview_answers, before)
        self.assertEqual(updated.directory_people.get(person=self.robert).status, "planned")

    def test_unchanged_uncertainty_is_not_promoted_to_confirmed(self):
        event = self.event()
        event.interview_answers["objective"]["status"] = "assumed"
        event.interview_answers["constraints"] = {"status": "not_applicable", "value": ""}
        event.save(update_fields=["interview_answers"])
        data = self.data() | {"expected_revision": "1", "constraints": ""}
        form = EventEditForm(data, instance=event, actor=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["interview_answers"]["objective"]["status"], "assumed")
        self.assertEqual(form.cleaned_data["interview_answers"]["constraints"]["status"], "not_applicable")

    def test_preparation_allows_pending_values_and_rejects_invalid_duration(self):
        form = EventForm(self.data() | {"resources": ""}, actor=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["interview_answers"]["resources"], {"status": "pending", "value": ""})
        for duration in ("0", "1441", "90.5", "noventa", "090"):
            with self.subTest(duration=duration):
                invalid = EventForm(self.data() | {"duration_minutes": duration}, actor=self.owner)
                self.assertFalse(invalid.is_valid())
                self.assertIn("duration_minutes", invalid.errors)

    def test_private_and_inactive_speakers_are_rejected_without_writes(self):
        self.jorge.is_active = False
        self.jorge.save(update_fields=["is_active"])
        for identifier in (self.foreign.pk, self.jorge.pk):
            with self.subTest(identifier=identifier):
                form = EventForm(self.data() | {"speaker_id": str(identifier)}, actor=self.owner)
                self.assertFalse(form.is_valid())
                self.assertIn("speaker_id", form.errors)
                with self.assertRaises(ValidationError):
                    create_event(actor=self.owner, title="No guardar", brief="Sin cambios", speaker_id=identifier)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(EventPerson.objects.count(), 0)

    def test_failed_replacement_keeps_previous_assignment_and_revision(self):
        event = self.event()
        audits = DirectoryAudit.objects.count()
        with self.assertRaises(ValidationError):
            update_event(event_id=event.pk, actor=self.owner, title="No se aplica", speaker_id=self.foreign.pk)
        event.refresh_from_db()
        self.assertEqual(event.title, self.data()["title"])
        self.assertEqual(event.revision, 1)
        self.assertEqual(event.directory_people.get(person=self.robert).status, "planned")
        self.assertEqual(DirectoryAudit.objects.count(), audits)

    def test_other_owner_cannot_replace_private_speaker(self):
        event = self.event()
        with self.assertRaises(PermissionDenied):
            update_event(event_id=event.pk, actor=self.other, speaker_id=self.foreign.pk)
        self.assertEqual(event.directory_people.get(person=self.robert).status, "planned")

    def test_stale_http_form_never_applies_preparation_or_speaker(self):
        event = self.event()
        update_event(event_id=event.pk, actor=self.owner, capacity=50)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("events:edit", args=[event.pk]), self.data() | {
            "expected_revision": "1", "speaker_id": str(self.jorge.pk), "objective": "Reemplazo obsoleto",
        })
        self.assertEqual(response.status_code, 409)
        event.refresh_from_db()
        self.assertEqual(event.capacity, 50)
        self.assertEqual(event.interview_answers["objective"]["value"], self.data()["objective"])
        self.assertEqual(event.directory_people.get(person=self.robert).status, "planned")
        self.assertFalse(event.directory_people.filter(person=self.jorge).exists())

    def test_reviewer_cannot_create_events_through_new_inputs(self):
        reviewer = get_user_model().objects.create_user(username="pilot-reviewer")
        PortalAccount.objects.create(user=reviewer, role="reviewer")
        with self.assertRaises(PermissionDenied):
            create_event(actor=reviewer, title="Evento no autorizado", brief="Sin acceso", speaker_id=self.robert.pk)
