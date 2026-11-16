"""Pilot visibility, financial-history retention and closed content requirements."""
from copy import deepcopy
from decimal import Decimal
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from apps.accounts.access import visible_events
from apps.ai_management.models import AIUsage
from apps.ai_management.pilot import openai_pilot_summary
from apps.events.services import archive_event, require_event_owner
from apps.jobs.models import Job
from apps.assistant.tests import test_compact_openai as fixtures
from apps.assistant.compact_contract import BASE_CONTEXT, validate_context, instructions_for
from apps.assistant.compact_planning import compact_wire


class RetiredPilotTests(TestCase):
    setUp = fixtures.CompactOpenAITests.setUp
    post = fixtures.CompactOpenAITests.post

    def test_retired_event_leaves_catalog_calendar_and_direct_pages(self):
        archived = archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=self.event.revision)
        self.assertIsNotNone(archived.archived_at)
        self.assertFalse(visible_events(self.owner).filter(pk=self.event.pk).exists())
        for name in ("events:index", "events:calendar"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, str(self.event.pk))
        for name in ("events:detail", "events:edit"):
            self.assertEqual(self.client.get(reverse(name, args=[self.event.pk])).status_code, 404)
        with self.assertRaises(PermissionDenied):
            require_event_owner(archived, self.owner)

    def test_retiring_keeps_ledger_job_and_lifetime_cap(self):
        job = fixtures.CompactOpenAITests.queue(self)
        AIUsage.objects.filter(job=job).update(status="settled", input_tokens=100, output_tokens=30,
            total_tokens=130, estimated_cost_usd=Decimal("0.000210"))
        Job.objects.filter(pk=job.pk).update(status="succeeded")
        before = openai_pilot_summary()
        archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=self.event.revision)
        self.assertEqual(openai_pilot_summary(), before)
        self.assertTrue(AIUsage.objects.filter(job=job, job__event_id=self.event.pk).exists())
        self.assertEqual(before["spent_usd"], Decimal("0.000210"))
        self.assertEqual(self.post(provider="openai").status_code, 403)

    def test_pending_work_or_stale_revision_prevents_retirement(self):
        with self.assertRaises(ValidationError):
            archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=0)
        fixtures.CompactOpenAITests.queue(self)
        with self.assertRaises(ValidationError):
            archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=self.event.revision)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.archived_at)


class RequiredContentTests(SimpleTestCase):
    def test_requirements_reach_exact_preview_without_private_data(self):
        wire = compact_wire(BASE_CONTEXT)
        self.assertIn('"applied_case"', wire["user_prompt"])
        self.assertIn('"technical_rehearsal"', wire["user_prompt"])
        self.assertIn("otra a preguntas", wire["system_prompt"])
        context = deepcopy(BASE_CONTEXT)
        context["answers"] = {"focus": "planning"}
        self.assertIn("otra a preguntas", instructions_for(context, openai=True))
        self.assertNotIn("Robert", json.dumps(context))

    def test_arbitrary_requirements_cannot_enter_public_export(self):
        context = deepcopy(BASE_CONTEXT)
        context["requirements"]["agenda"].append("private user data")
        with self.assertRaises(ValidationError):
            validate_context(context)
