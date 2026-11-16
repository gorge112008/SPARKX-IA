"""Local readiness hints use isolated records; no real credentials or network."""
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.ai_management.services import current_month
from apps.ai_management.testing import configure_test_account
from apps.events.models import Event
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision
from .checks import collect_local_checks
from .models import ChecklistProgress


@override_settings(OPENAI_API_KEY="", GROQ_API_KEY="", GEMINI_API_KEY="", OLLAMA_ENABLED=False)
class LocalChecklistChecksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username="local-check-owner", is_staff=True)
        cls.other = users.objects.create_user(username="local-check-other", is_staff=True)

    def setUp(self):
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("Local checks cannot contact providers"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(self.remote.assert_not_called)

    def checks(self):
        return collect_local_checks(self.owner)

    def configure(self, **kwargs):
        return configure_test_account(self.owner, **kwargs)

    def journey(self, *, owner=None, source=AIUsage.AccountingSource.PROVIDER):
        owner = owner or self.owner
        account = AIAccount.objects.filter(owner=owner).first() or AIAccount.objects.create(owner=owner)
        event = Event.objects.create(owner=owner, title="Evento de prueba", brief="Datos controlados")
        candidate = PlanCandidate.objects.create(
            event=event, payload={}, base_revision=1, created_by=owner,
            status=PlanCandidate.Status.APPROVED,
        )
        revision = PlanRevision.objects.create(
            event=event, version=1, payload={}, approved_by=owner, candidate=candidate,
        )
        job = Job.objects.create(
            event=event, actor=owner, kind=Job.Kind.PLAN, prompt="Prueba controlada",
            base_revision=1, request_hash="0" * 64, idempotency_key=str(uuid.uuid4()),
            status=Job.Status.SUCCEEDED, result={"candidate_id": str(candidate.pk)},
        )
        usage = AIUsage.objects.create(
            job=job, account=account, month=current_month(), snapshot={},
            reserved_input_tokens=100, reserved_output_tokens=100, reserved_usd=Decimal("0"),
            status=AIUsage.Status.SETTLED, accounting_source=source,
            input_tokens=10, output_tokens=5, total_tokens=15,
            dispatch_token=uuid.uuid4(), dispatched_at=timezone.now(), settled_at=timezone.now(),
            estimated_cost_usd=Decimal("0"),
        )
        return event, candidate, revision, job, usage

    def test_empty_checks_are_read_only_and_have_one_timestamp(self):
        at = datetime(2026, 11, 12, 15, 0, tzinfo=datetime_timezone.utc)
        checks = collect_local_checks(self.owner, at=at)
        self.assertEqual(set(checks), {"creditos_api", "credencial_privada", "presupuesto_ia", "prueba_recorrido"})
        self.assertEqual(checks["creditos_api"]["status"], "info")
        self.assertTrue(all(row["checked_at"] == at for row in checks.values()))
        self.assertTrue(all(row["status"] == "pending" for key, row in checks.items() if key != "creditos_api"))
        self.assertFalse(AIAccount.objects.exists())
        self.assertFalse(ChecklistProgress.objects.exists())
        self.assertFalse(Job.objects.exists())

    def test_unsaved_owner_has_no_database_effect(self):
        checks = collect_local_checks(get_user_model()(username="unsaved"))
        self.assertEqual(checks["credencial_privada"]["status"], "pending")
        self.assertFalse(AIAccount.objects.exists())

    def test_missing_credential_is_pending_while_budget_is_separately_ready(self):
        self.configure()
        checks = self.checks()
        self.assertEqual(checks["credencial_privada"]["status"], "pending")
        self.assertEqual(checks["presupuesto_ia"]["status"], "ready")
        self.assertEqual(checks["creditos_api"]["status"], "info")

    @override_settings(OPENAI_API_KEY="test-not-a-real-secret")
    def test_present_credential_is_not_reported_as_validated_by_provider(self):
        self.configure()
        checks = self.checks()
        self.assertEqual(checks["credencial_privada"]["status"], "ready")
        self.assertIn("No se comprobó su validez", checks["credencial_privada"]["message"])
        self.assertNotIn("test-not-a-real-secret", str(checks))
        self.assertEqual(checks["creditos_api"]["status"], "info")

    def test_other_owners_active_profile_is_not_used(self):
        foreign_account = configure_test_account(self.other)
        AIAccount.objects.create(owner=self.owner, active_profile=foreign_account.active_profile)
        with patch("apps.project_checklist.checks.provider.profile_ready") as ready:
            checks = self.checks()
        ready.assert_not_called()
        self.assertEqual(checks["credencial_privada"]["status"], "pending")
        self.assertEqual(checks["presupuesto_ia"]["status"], "pending")

    @override_settings(OPENAI_API_KEY="test-not-a-real-secret")
    def test_invalid_or_disabled_profile_is_pending(self):
        account = self.configure()
        profile = account.active_profile
        profile.enabled = False
        profile.save(update_fields=["enabled"])
        self.assertEqual(self.checks()["credencial_privada"]["status"], "pending")
        profile.enabled = True
        profile.mode = AIProfile.Mode.FREE
        profile.save(update_fields=["enabled", "mode"])
        self.assertEqual(self.checks()["presupuesto_ia"]["status"], "pending")

    @override_settings(OPENAI_API_KEY="test-not-a-real-secret")
    def test_payment_consent_and_budget_are_not_activated_by_checks(self):
        account = self.configure(budget="0", paid=False)
        checks = self.checks()
        self.assertEqual(checks["credencial_privada"]["status"], "ready")
        self.assertEqual(checks["presupuesto_ia"]["status"], "pending")
        account.refresh_from_db()
        self.assertFalse(account.paid_enabled)
        self.assertEqual(account.monthly_budget_usd, 0)
        self.assertFalse(AIUsage.objects.exists())

    def test_full_maximum_reservation_must_fit_usd_and_tokens(self):
        account = self.configure(budget="0.000001")
        self.assertEqual(self.checks()["presupuesto_ia"]["status"], "pending")
        account.monthly_budget_usd = Decimal("10")
        account.monthly_token_limit = 1
        account.save()
        self.assertEqual(self.checks()["presupuesto_ia"]["status"], "pending")

    def test_cached_rate_cannot_underestimate_maximum_reservation(self):
        account = self.configure(budget="0.03")
        profile = account.active_profile
        profile.input_rate = Decimal("0")
        profile.cached_rate = Decimal("2")
        profile.output_rate = Decimal("0")
        profile.save()
        self.assertEqual(self.checks()["presupuesto_ia"]["status"], "pending")

    def test_reserved_and_uncertain_usage_reduce_available_local_budget(self):
        self.configure(budget="0.05")
        _event, _candidate, _revision, _job, usage = self.journey()
        usage.status = AIUsage.Status.UNCERTAIN
        usage.reserved_usd = Decimal("0.04")
        usage.save(update_fields=["status", "reserved_usd"])
        checks = self.checks()
        self.assertEqual(checks["presupuesto_ia"]["status"], "pending")
        self.assertEqual(checks["prueba_recorrido"]["status"], "pending")

    @override_settings(OLLAMA_ENABLED=True)
    def test_local_flag_does_not_claim_running_service_or_model(self):
        profile = AIProfile.objects.create(
            owner=self.owner, name="Local de prueba", provider="ollama", mode="local",
            model="qwen3:4b-instruct-2507-q4_K_M",
        )
        AIAccount.objects.create(owner=self.owner, active_profile=profile)
        checks = self.checks()
        self.assertEqual(checks["credencial_privada"]["status"], "ready")
        self.assertIn("No se comprobó que Ollama esté ejecutándose", checks["credencial_privada"]["message"])
        self.assertEqual(checks["presupuesto_ia"]["status"], "ready")

    @override_settings(OPENAI_API_KEY="test-not-a-real-secret")
    def test_configuration_errors_never_echo_exception_details(self):
        self.configure()
        with patch("apps.project_checklist.checks.configured_snapshot", side_effect=ValidationError("secret-should-never-appear")):
            checks = self.checks()
        self.assertEqual(checks["presupuesto_ia"]["status"], "pending")
        self.assertNotIn("secret-should-never-appear", str(checks))

    def test_coherent_records_are_labelled_local_not_external_verification(self):
        self.journey()
        check = self.checks()["prueba_recorrido"]
        self.assertEqual(check["status"], "ready")
        self.assertIn("registros locales", check["message"])
        self.assertIn("no verifican por sí solos inferencia real", check["message"])

    def test_manually_approved_demo_without_job_and_usage_is_not_a_journey(self):
        event = Event.objects.create(owner=self.owner, title="Demo manual", brief="Sin inferencia")
        candidate = PlanCandidate.objects.create(event=event, payload={}, base_revision=1, created_by=self.owner, status="approved")
        PlanRevision.objects.create(event=event, candidate=candidate, payload={}, approved_by=self.owner, version=1)
        self.assertEqual(self.checks()["prueba_recorrido"]["status"], "pending")

    def test_foreign_owners_records_are_not_visible(self):
        self.journey(owner=self.other)
        self.assertEqual(self.checks()["prueba_recorrido"]["status"], "pending")
        self.assertFalse(AIAccount.objects.filter(owner=self.owner).exists())

    def test_manual_reconciliation_is_not_provider_observed_usage(self):
        self.journey(source=AIUsage.AccountingSource.MANUAL)
        self.assertEqual(self.checks()["prueba_recorrido"]["status"], "pending")

    def test_usage_must_be_complete_dispatched_and_settled(self):
        _event, _candidate, _revision, _job, usage = self.journey()
        for change in ({"dispatch_token": None}, {"dispatched_at": None}, {"settled_at": None},
                       {"total_tokens": 0}, {"input_tokens": None}, {"output_tokens": None},
                       {"status": AIUsage.Status.RELEASED}):
            with self.subTest(change=tuple(change)):
                original = {key: getattr(usage, key) for key in change}
                AIUsage.objects.filter(pk=usage.pk).update(**change)
                self.assertEqual(self.checks()["prueba_recorrido"]["status"], "pending")
                AIUsage.objects.filter(pk=usage.pk).update(**original)

    def test_job_must_belong_to_owner_and_refer_to_same_event_approval(self):
        event, candidate, revision, job, usage = self.journey()
        foreign_event = Event.objects.create(owner=self.other, title="Ajeno", brief="Ajeno")
        foreign_account = AIAccount.objects.create(owner=self.other)
        for model, pk, change in (
            (Job, job.pk, {"kind": Job.Kind.CHAT}),
            (Job, job.pk, {"status": Job.Status.FAILED}),
            (Job, job.pk, {"actor_id": self.other.pk}),
            (Job, job.pk, {"event_id": foreign_event.pk}),
            (AIUsage, usage.pk, {"account_id": foreign_account.pk}),
            (PlanCandidate, candidate.pk, {"event_id": foreign_event.pk}),
            (PlanCandidate, candidate.pk, {"created_by_id": self.other.pk}),
            (PlanCandidate, candidate.pk, {"status": PlanCandidate.Status.PENDING}),
            (PlanRevision, revision.pk, {"event_id": foreign_event.pk}),
            (PlanRevision, revision.pk, {"approved_by_id": self.other.pk}),
        ):
            with self.subTest(model=model.__name__, change=tuple(change)):
                original = model.objects.filter(pk=pk).values(*change).get()
                model.objects.filter(pk=pk).update(**change)
                self.assertEqual(self.checks()["prueba_recorrido"]["status"], "pending")
                model.objects.filter(pk=pk).update(**original)
        self.assertEqual(self.checks()["prueba_recorrido"]["status"], "ready")

    def test_malformed_or_unrelated_candidate_links_are_ignored(self):
        _event, _candidate, _revision, job, _usage = self.journey()
        for result in ([], {}, {"candidate_id": "not-a-uuid"}, {"candidate_id": str(uuid.uuid4())}, {"candidate_id": []}):
            with self.subTest(result=result):
                Job.objects.filter(pk=job.pk).update(result=result)
                self.assertEqual(self.checks()["prueba_recorrido"]["status"], "pending")

    @override_settings(OPENAI_API_KEY="test-not-a-real-secret")
    def test_checks_never_write_financial_plan_or_manual_records(self):
        self.configure()
        self.journey()
        ChecklistProgress.objects.create(owner=self.owner, item_key="prueba_recorrido", status="in_progress")
        models = (AIAccount, AIProfile, AIUsage, Event, Job, PlanCandidate, PlanRevision, ChecklistProgress)
        before = {model: list(model.objects.order_by("pk").values()) for model in models}
        for _ in range(2):
            self.assertEqual(self.checks()["prueba_recorrido"]["status"], "ready")
        self.assertEqual(before, {model: list(model.objects.order_by("pk").values()) for model in models})
