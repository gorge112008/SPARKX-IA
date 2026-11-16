"""Demo guarantees: attributable data, real local state, and harmless repeated loads."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.assistant.models import Message
from apps.jobs.models import Job
from apps.planning.domain import plan_impact, validate_plan
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate

from .demo import DEMO_EVENT_ID, DEMO_MANUAL_NOTICE, get_demo_context, seed_demo_event
from .models import Event
from .services import create_event, update_event


class DemoEventTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="demo-owner")
        cls.other = get_user_model().objects.create_user(username="demo-other")

    def test_seed_creates_valid_baseline_and_reviewable_manual_alternative(self):
        result = seed_demo_event(actor=self.owner)
        event = Event.objects.select_related("active_plan").get(pk=DEMO_EVENT_ID)
        alternative = event.candidates.get(status=PlanCandidate.Status.PENDING)
        self.assertTrue(result.created)
        self.assertEqual(event.owner, self.owner)
        self.assertEqual(event.revision, 2)
        self.assertEqual(event.candidates.count(), 2)
        self.assertEqual(event.plan_revisions.count(), 1)
        for payload in (event.active_plan.payload, alternative.payload):
            self.assertEqual(validate_plan(payload), [])
            self.assertIn(DEMO_MANUAL_NOTICE, payload["summary"])
            self.assertTrue(all(task["status"] == "pending" for task in payload["tasks"]))
        self.assertEqual(alternative.base_revision, event.revision)
        self.assertEqual(alternative.base_plan_id, event.active_plan_id)
        self.assertEqual(sum(s["duration_minutes"] for s in event.active_plan.payload["sessions"]), 90)
        self.assertEqual(sum(s["duration_minutes"] for s in alternative.payload["sessions"]), 105)
        self.assertEqual(event.active_plan.payload["sessions"][0]["start"], alternative.payload["sessions"][0]["start"])
        impact = plan_impact(event.active_plan.payload, alternative.payload)
        self.assertEqual(impact["sessions"]["changed"], ["cierre", "preguntas", "rendimiento"])
        self.assertEqual(impact["tasks"]["added"], ["ampliacion"])
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_rerun_preserves_user_edits_and_approved_alternative(self):
        result = seed_demo_event(actor=self.owner)
        candidate = result.event.candidates.get(status=PlanCandidate.Status.PENDING)
        revision = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        updated = update_event(event_id=DEMO_EVENT_ID, actor=self.owner, title="Título ajustado por Jorge", capacity=75)
        counts = (Event.objects.count(), PlanCandidate.objects.count(), PlanRevision.objects.count())
        rerun = seed_demo_event(actor=self.owner)
        self.assertFalse(rerun.created)
        self.assertEqual(rerun.event.title, updated.title)
        self.assertEqual(rerun.event.capacity, 75)
        self.assertEqual(rerun.event.revision, updated.revision)
        self.assertEqual(rerun.event.active_plan_id, revision.pk)
        self.assertEqual(counts, (Event.objects.count(), PlanCandidate.objects.count(), PlanRevision.objects.count()))

    def test_other_owner_cannot_take_over_existing_demo(self):
        seed_demo_event(actor=self.owner)
        with self.assertRaises(PermissionDenied):
            seed_demo_event(actor=self.other)
        self.assertEqual(Event.objects.get(pk=DEMO_EVENT_ID).owner, self.owner)
        self.assertFalse(Event.objects.filter(owner=self.other).exists())

    def test_explicit_identity_cannot_overwrite_another_owners_event(self):
        existing = create_event(actor=self.other, title="Evento privado", brief="Datos originales")
        with self.assertRaises((ValidationError, IntegrityError)), transaction.atomic():
            create_event(
                actor=self.owner,
                event_id=existing.pk,
                title="Intento de sustitución",
                brief="No debe guardarse",
            )
        existing.refresh_from_db()
        self.assertEqual(existing.owner, self.other)
        self.assertEqual(existing.title, "Evento privado")
        self.assertEqual(existing.brief, "Datos originales")

    def test_failed_initialization_rolls_back_all_demo_content(self):
        with patch("apps.events.demo.create_candidate", side_effect=RuntimeError("Controlled failure")):
            with self.assertRaises(RuntimeError):
                seed_demo_event(actor=self.owner)
        self.assertFalse(Event.objects.exists())
        self.assertFalse(PlanCandidate.objects.exists())
        self.assertFalse(PlanRevision.objects.exists())

    def test_loader_requires_existing_active_owner_and_changes_no_credentials(self):
        original_password = self.owner.password
        with self.assertRaises(CommandError):
            call_command("seed_demo_event", owner="unknown-demo-owner", stdout=StringIO())
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        with self.assertRaises(CommandError):
            call_command("seed_demo_event", owner=self.other.username, stdout=StringIO())
        output = StringIO()
        call_command("seed_demo_event", owner=self.owner.username, stdout=output)
        call_command("seed_demo_event", owner=self.owner.username, stdout=output)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.password, original_password)
        self.assertEqual(get_user_model().objects.count(), 2)
        self.assertIn(str(DEMO_EVENT_ID), output.getvalue())
        self.assertIn("La demo ya existe", output.getvalue())

    def test_context_is_demo_scoped_and_attributes_facts_and_assumptions(self):
        other_event = create_event(actor=self.owner, title="Otro evento", brief="No es la demo")
        self.assertIsNone(get_demo_context(other_event))
        result = seed_demo_event(actor=self.owner)
        context = get_demo_context(result.event)
        self.assertIn("sin verificación externa", context["source"])
        self.assertIn("2026", context["assumptions"][0]["value"])
        self.assertEqual(context["agenda_overview"][0]["time"], "19:30")
        self.assertEqual(context["poster_static_path"], "img/demo-gica-evento.jpg")
        self.assertEqual(
            context["scenario_candidate_id"],
            result.event.candidates.get(status=PlanCandidate.Status.PENDING).pk,
        )

    def test_demo_page_keeps_owner_scope_and_escapes_user_edits(self):
        result = seed_demo_event(actor=self.owner)
        title = '<script>alert("demo")</script>'
        update_event(event_id=result.event.pk, actor=self.owner, title=title)
        url = reverse("events:detail", args=[result.event.pk])
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "Demo local · preparación manual")
        self.assertContains(response, "demo-gica-evento.jpg")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, title)
        self.assertIn("Afiche EVENTO1.jpg", response.context["demo"]["source"])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("events:index")), "Demo · GICA")
