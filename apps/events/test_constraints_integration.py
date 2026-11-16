from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.directory.models import Person
from apps.jobs.models import Job
from apps.jobs.services import enqueue, run_one
from apps.planning.event_rules import context_constraints, validate_event_plan
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import create_candidate, approve_candidate
from apps.planning.tests import valid_plan
from .models import Event


class EventConstraintIntegrationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="constraints-owner")
        self.other = get_user_model().objects.create_user(username="constraints-other")
        self.event = Event.objects.create(owner=self.owner, title="Demo", brief="Datos ficticios", is_synthetic=True)
        self.plan = valid_plan()
        for session in self.plan["sessions"]:
            session["speaker"] = "Expositor ficticio A"
        self.person = Person.objects.create(owner=self.owner, full_name="Expositor ficticio A", category="speaker", is_synthetic=True)
        self.client.force_login(self.owner)

    def approve(self, event=None):
        event = event or self.event
        candidate = create_candidate(event=event, actor=event.owner, payload=deepcopy(self.plan), base_revision=event.revision, base_plan_id=event.active_plan_id)
        revision = approve_candidate(candidate_id=candidate.pk, actor=event.owner)
        event.refresh_from_db()
        return revision

    def save_constraints(self):
        response = self.client.post(reverse("events:constraints", args=[self.event.pk]), {
            "expected_revision": self.event.revision, "start": "2026-11-14T09:00", "end": "2026-11-14T12:00",
            "speakers": [str(self.person.pk)], "fixed_0_speaker": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()

    def test_confirmed_duration_and_date_are_enforced_at_approval(self):
        self.event.starts_at = datetime.fromisoformat("2026-11-14T09:00:00-05:00")
        self.event.interview_answers = {"duration_minutes": {"status":"confirmed", "value":"30"}}
        self.event.save()
        candidate = create_candidate(event=self.event, actor=self.owner, payload=self.plan, base_revision=1)
        self.assertTrue(any("duración" in error for error in candidate.validation))
        with self.assertRaises(ValidationError):
            approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.assertEqual(PlanRevision.objects.count(), 0)

    def test_candidate_before_event_start_is_invalid(self):
        self.event.starts_at = datetime.fromisoformat("2026-11-14T09:15:00-05:00")
        self.assertTrue(any("antes" in error for error in validate_event_plan(self.event, self.plan)))

    def test_constraints_keep_plan_and_require_exact_revision(self):
        revision = self.approve()
        self.save_constraints()
        self.assertEqual(self.event.active_plan_id, revision.pk)
        response = self.client.post(reverse("events:constraints", args=[self.event.pk]), {
            "expected_revision": 1, "start":"2026-11-14T09:00", "end":"2026-11-14T12:00", "speakers":[str(self.person.pk)],
        })
        self.assertEqual(response.status_code, 409)

    def test_other_approved_agenda_blocks_speaker_and_local_repair_does_not_approve(self):
        self.approve()
        self.save_constraints()
        other_event = Event.objects.create(owner=self.owner, title="Otra demo", brief="Ficticio", is_synthetic=True)
        self.approve(other_event)
        errors = validate_event_plan(self.event, self.plan)
        self.assertTrue(errors)
        revisions = PlanRevision.objects.count()
        response = self.client.post(reverse("events:repair", args=[self.event.pk]), {"expected_revision":self.event.revision})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PlanRevision.objects.count(), revisions)
        candidate = PlanCandidate.objects.filter(event=self.event, status="pending").get()
        self.assertEqual(candidate.validation, [])
        self.assertNotEqual(candidate.payload["sessions"][0]["start"], self.plan["sessions"][0]["start"])

    def test_other_owner_agenda_is_not_included(self):
        self.approve()
        self.save_constraints()
        other_event = Event.objects.create(owner=self.other, title="Ajeno", brief="Privado")
        self.approve(other_event)
        self.assertEqual(validate_event_plan(self.event, self.plan), [])

    def test_changed_contact_requires_review_instead_of_silent_use(self):
        self.approve()
        self.save_constraints()
        self.person.version += 1
        self.person.save()
        with self.assertRaisesMessage(ValueError, "directorio"):
            context_constraints(self.event)
        self.assertTrue(validate_event_plan(self.event, self.plan))

    def test_foreign_contact_cannot_be_selected(self):
        self.approve()
        self.person.owner = self.other
        self.person.save()
        response = self.client.post(reverse("events:constraints", args=[self.event.pk]), {
            "expected_revision":self.event.revision,"start":"2026-11-14T09:00","end":"2026-11-14T12:00","speakers":[str(self.person.pk)],
        })
        self.assertEqual(response.status_code,400)

    def test_no_plan_configuration_does_not_write(self):
        response = self.client.get(reverse("events:constraints", args=[self.event.pk]))
        self.assertEqual(response.status_code,302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.planning_constraints,{})


@override_settings(FREE_DEMO_ENABLED=True)
class FreeProductIntegrationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="free-product-owner")
        self.event = Event.objects.create(owner=self.owner,title="Demo",brief="Datos ficticios",is_synthetic=True)
        self.profile = AIProfile.objects.create(owner=self.owner,name="Demo gratuita",provider="opencode",model="glm-5.3-flash-free",mode="free",free_tier_confirmed=True,max_output_tokens=2048)
        self.account = AIAccount.objects.create(owner=self.owner,active_profile=self.profile,paid_enabled=False,monthly_budget_usd=0)

    @patch("apps.assistant.free_harness.ready",return_value=True)
    @patch("apps.assistant.free_harness.run_free_harness")
    def test_worker_keeps_each_explicit_free_model_in_dispatch_and_ledger(self,remote,ready):
        remote.return_value = {"payload":valid_plan(),"text":"", "usage":{"input_tokens":100,"output_tokens":200,"total_tokens":300}}
        for model in ("deepseek-v4.1-flash-free","minimax-m3.1-flash-free","glm-5.3-flash-free"):
            with self.subTest(model=model):
                self.profile.model=model
                self.profile.save(update_fields=["model"])
                job=enqueue(event=self.event,actor=self.owner,kind="plan",prompt="Preparar demo",idempotency_key=model)
                result=run_one()
                self.assertEqual(result.status,"succeeded")
                self.assertEqual(remote.call_args.kwargs["model"],model)
                usage=AIUsage.objects.get(job=job)
                self.assertEqual(usage.snapshot["model"],model)
                self.assertEqual(usage.estimated_cost_usd,0)
                self.assertEqual(usage.total_tokens,300)

    @patch("apps.assistant.free_harness.ready",return_value=True)
    @patch("apps.assistant.free_harness.run_free_harness")
    def test_quota_failure_is_explained_without_fallback_or_invented_zero_usage(self,remote,ready):
        from apps.assistant.free_harness import FreeHarnessError
        remote.side_effect = FreeHarnessError("private native body",http_status=429,phase="inference",code="quota_or_rate_limit")
        job = enqueue(event=self.event,actor=self.owner,kind="plan",prompt="Preparar demo",idempotency_key="quota1")
        result = run_one()
        self.assertEqual(result.status,"failed")
        self.assertIn("429",result.error)
        self.assertNotIn("private",result.error)
        self.assertEqual(remote.call_count,1)
        self.assertFalse(PlanCandidate.objects.exists())
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.status,"uncertain")
        self.assertIsNone(usage.total_tokens)

    @patch("apps.assistant.free_harness.ready",return_value=True)
    def test_real_event_rejected_before_job_or_usage(self,ready):
        self.event.is_synthetic = False
        self.event.save()
        with self.assertRaisesMessage(ValidationError,"ficticios"):
            enqueue(event=self.event,actor=self.owner,kind="plan",prompt="Preparar demo",idempotency_key="synth1")
        self.assertEqual(Job.objects.count(),0)
        self.assertEqual(AIUsage.objects.count(),0)

    @patch("apps.assistant.free_harness.ready",return_value=True)
    @patch("apps.assistant.free_harness.run_free_harness")
    def test_free_generation_uses_existing_worker_and_accounting_without_payment(self,remote,ready):
        remote.return_value = {"payload":valid_plan(),"text":"", "usage":{"input_tokens":100,"output_tokens":200,"total_tokens":300}}
        job = enqueue(event=self.event,actor=self.owner,kind="plan",prompt="Preparar demo",idempotency_key="synth1")
        result = run_one()
        self.assertEqual(result.pk,job.pk)
        self.assertEqual(result.status,"succeeded")
        candidate = PlanCandidate.objects.get(event=self.event)
        self.assertEqual(candidate.status,"pending")
        self.assertEqual(candidate.validation,[])
        usage = AIUsage.objects.get(job=job)
        self.assertEqual(usage.total_tokens,300)
        self.assertEqual(usage.estimated_cost_usd,0)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.active_plan_id)
        self.assertTrue(remote.call_args.kwargs["synthetic"])

    @patch("apps.assistant.free_harness.ready",return_value=True)
    @patch("apps.assistant.free_harness.run_free_harness")
    def test_failure_keeps_current_plan_and_does_not_fallback(self,remote,ready):
        from apps.assistant.free_harness import FreeHarnessError
        remote.side_effect = FreeHarnessError("cuota")
        job = enqueue(event=self.event,actor=self.owner,kind="plan",prompt="Preparar demo",idempotency_key="synth1")
        self.assertEqual(run_one().status,"failed")
        self.assertEqual(remote.call_count,1)
        self.assertEqual(PlanCandidate.objects.count(),0)
        self.account.refresh_from_db()
        self.assertFalse(self.account.paid_enabled)
        self.assertEqual(self.account.monthly_budget_usd,0)
