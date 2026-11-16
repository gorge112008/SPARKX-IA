"""The demonstration command writes only inside Django's isolated test database."""

from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.directory.management.commands.seed_synthetic_directory import TITLES, synthetic_id
from apps.directory.models import DirectoryAudit, EventPerson, Organization, Person
from apps.events.models import Event
from apps.events.services import create_event, update_event
from apps.planning.domain import validate_plan
from apps.planning.models import PlanCandidate, PlanRevision, TaskProgress
from apps.planning.services import approve_candidate


class SyntheticDirectorySeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="adminjorge", password="synthetic-test-password")

    def seed(self, **options):
        output = StringIO()
        call_command("seed_synthetic_directory", owner=self.owner.get_username(), stdout=output, **options)
        return output.getvalue()

    def snapshot(self):
        return {
            model.__name__: list(model.objects.order_by("pk").values())
            for model in (Organization, Person, Event, EventPerson, DirectoryAudit, PlanCandidate, PlanRevision, TaskProgress)
        }

    def test_creates_six_navigable_events_with_fictional_directory_and_pending_proposals(self):
        output = self.seed()
        self.assertIn("eventos creados: 6", output)
        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(Person.objects.count(), 45)
        self.assertEqual(EventPerson.objects.count(), 60)
        self.assertEqual(PlanCandidate.objects.count(), 6)
        self.assertEqual(PlanRevision.objects.count(), 0)
        self.assertEqual(TaskProgress.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(Person.objects.exclude(email__endswith=".invalid").exists())
        self.assertFalse(Person.objects.filter(is_synthetic=False).exists())
        self.assertFalse(Organization.objects.filter(is_synthetic=False).exists())
        self.assertFalse(Event.objects.filter(is_synthetic=False).exists())
        self.assertFalse(EventPerson.objects.exclude(status="planned").exists())
        self.assertEqual(Person.objects.filter(category="speaker").count(), 3)
        self.assertEqual(Person.objects.filter(category="participant").count(), 30)
        self.assertEqual(Person.objects.filter(category="guest").count(), 12)
        events = list(Event.objects.order_by("starts_at"))
        self.assertEqual([event.title for event in events], list(TITLES))
        for day, event in enumerate(events):
            with self.subTest(day=day):
                local = event.starts_at.astimezone(ZoneInfo("America/Lima"))
                self.assertEqual(local.date().isoformat(), f"2026-11-{16 + day}")
                self.assertEqual(event.timezone, "America/Lima")
                self.assertIn("GICA" if day == 5 else "UNAC", event.organization.name)
                self.assertEqual(event.owner_id, self.owner.pk)
                self.assertIsNone(event.active_plan_id)
                self.assertEqual(EventPerson.objects.filter(event=event, role="speaker").count(), 3)
                self.assertEqual(EventPerson.objects.filter(event=event, role="participant").count(), 5)
                self.assertEqual(EventPerson.objects.filter(event=event, role="guest").count(), 2)
                candidate = event.candidates.get()
                self.assertEqual(candidate.status, "pending")
                self.assertEqual(candidate.validation, [])
                self.assertEqual(validate_plan(candidate.payload), [])
                self.assertEqual(len(candidate.payload["sessions"]), 3)
                self.assertEqual([session["duration_minutes"] for session in candidate.payload["sessions"]], [30, 30, 30])
                self.assertEqual(len(candidate.payload["tasks"]), 3)
                self.assertEqual({task["status"] for task in candidate.payload["tasks"]}, {"pending"})
                self.assertIn("Supuestos:", candidate.payload["summary"])
        for speaker in Person.objects.filter(category="speaker"):
            self.assertEqual(EventPerson.objects.filter(person=speaker).count(), 6)
        self.client.force_login(self.owner)
        for event in events:
            self.assertEqual(self.client.get(f"/events/{event.pk}/").status_code, 200)

    def test_second_run_does_not_change_any_existing_row_or_audit(self):
        self.seed()
        before = self.snapshot()
        output = self.seed()
        self.assertEqual(self.snapshot(), before)
        self.assertIn("eventos reutilizados: 6", output)
        self.assertIn("personas reutilizadas: 45", output)
        self.assertNotIn("creadas", output)

    def test_preserves_human_edits_approved_plan_and_task_progress(self):
        self.seed()
        event = Event.objects.order_by("starts_at").first()
        revision = approve_candidate(candidate_id=event.candidates.get().pk, actor=self.owner)
        TaskProgress.objects.create(plan=revision, task_id="t1", status="in_progress", updated_by=self.owner, note="Estado de prueba declarado por organizador")
        update_event(event_id=event.pk, actor=self.owner, title="Título editado por el organizador")
        Person.objects.filter(category="participant").update(full_name="Nombre ficticio editado")
        EventPerson.objects.filter(event=event, role="speaker").update(status="cancelled")
        before = self.snapshot()
        self.seed()
        self.assertEqual(self.snapshot(), before)

    def test_late_collision_rolls_back_new_directory_and_proposals(self):
        existing = create_event(
            actor=self.owner, title="Evento real que debe conservarse", brief="Datos previos",
            event_id=synthetic_id(self.owner.pk, "event:6"),
        )
        before = self.snapshot()
        with self.assertRaisesMessage(CommandError, "Colisión"):
            self.seed()
        self.assertEqual(self.snapshot(), before)
        existing.refresh_from_db()
        self.assertFalse(existing.is_synthetic)

    def test_foreign_synthetic_identity_is_a_collision(self):
        other = get_user_model().objects.create_user(username="other-owner", password="synthetic-test-password")
        create_event(
            actor=other, title="Demostración ajena", brief="Conservar",
            event_id=synthetic_id(self.owner.pk, "event:1"), is_synthetic=True,
        )
        before = self.snapshot()
        with self.assertRaisesMessage(CommandError, "Colisión"):
            self.seed()
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_validates_everything_and_leaves_no_rows(self):
        before = self.snapshot()
        output = self.seed(dry_run=True)
        self.assertIn("Simulación revertida", output)
        self.assertIn("eventos creados: 6", output)
        self.assertEqual(self.snapshot(), before)

    def test_failure_during_candidate_creation_rolls_back_everything(self):
        before = self.snapshot()
        with patch("apps.directory.management.commands.seed_synthetic_directory.create_candidate", side_effect=CommandError("Fallo de prueba")):
            with self.assertRaisesMessage(CommandError, "Fallo de prueba"):
                self.seed()
        self.assertEqual(self.snapshot(), before)

    def test_owner_is_required_existing_and_active(self):
        with self.assertRaises(CommandError):
            call_command("seed_synthetic_directory", stdout=StringIO())
        with self.assertRaisesMessage(CommandError, "usuario existente"):
            call_command("seed_synthetic_directory", owner="missing-owner", stdout=StringIO())
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaisesMessage(CommandError, "organizador activo"):
            self.seed()
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), 1)
