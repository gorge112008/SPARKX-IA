"""Authorization, evidence, exact-version verification and owner form tests."""
from copy import deepcopy
from datetime import datetime
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.directory.services import upsert_person
from apps.events.services import create_event
from .models import PreparationChange, TaskPreparation, TaskProgress
from .preparation import PreparationConflict, preparation_rows, preparation_state, update_task_preparation
from .preparation_views import preparation
from .services import approve_candidate, create_candidate
from .task_progress import TaskPlanConflict, update_task_progress

urlpatterns = [path("preparation-test/<uuid:event_id>/", preparation, name="preparation_test"), path("", include("config.urls"))]


def payload():
    return {"title": "Seminario", "summary": "Preparación con evidencia humana.", "sessions": [], "risks": [],
            "tasks": [{"id": "t1", "title": "Revisar material", "depends_on": [], "status": "pending", "purpose": "Revisión del organizador."},
                      {"id": "t2", "title": "Realizar ensayo", "depends_on": ["t1"], "status": "pending", "purpose": "Preparar el evento."}]}


class PreparationFixture:
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="preparation-owner")
        cls.other = get_user_model().objects.create_user(username="preparation-other")

    def setUp(self):
        self.event = create_event(actor=self.owner, title="Ejemplo", brief="Preparación declarada.")
        self.plan = self.approve(payload())
        self.person = upsert_person(actor=self.owner, full_name="Responsable de ejemplo", category="participant")

    def approve(self, content):
        self.event.refresh_from_db()
        candidate = create_candidate(event=self.event, actor=self.owner, payload=content,
            base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)
        plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return plan

    def save(self, **overrides):
        return update_task_preparation(**({
            "event": self.event, "actor": self.owner, "plan_id": self.plan.pk, "task_id": "t1",
            "stage": "prepared", "expected_version": 0, "request_key": uuid.uuid4(),
            "responsible_person_id": self.person.pk, "responsible_person_version": self.person.version,
            "evidence_note": "El organizador revisó el material.",
        } | overrides))

    def progress(self, status="completed", version=0):
        return update_task_progress(event=self.event, actor=self.owner, plan_id=self.plan.pk,
            task_id="t1", status=status, expected_version=version, request_key=uuid.uuid4(),
            note="Declaración de ejecución del organizador.")


class PreparationTests(PreparationFixture, TestCase):
    def test_responsibility_due_date_and_evidence_do_not_modify_execution_or_plan(self):
        before, revision = deepcopy(self.plan.payload), self.event.revision
        due = timezone.now()
        record = self.save(stage="pending", due_at=due)
        self.assertEqual(record.version, 1)
        self.assertEqual(record.responsible_person_id, self.person.pk)
        self.assertEqual(record.responsible_person_version, self.person.version)
        self.assertEqual(record.due_at, due)
        self.assertFalse(TaskProgress.objects.exists())
        self.plan.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.plan.payload, before)
        self.assertEqual(self.event.revision, revision)
        receipt = record.changes.get()
        self.assertEqual(receipt.actor_id, self.owner.pk)
        self.assertEqual(receipt.created_at, record.updated_at)
        self.assertIn("due_at", receipt.changed_fields)
        self.assertNotIn(record.evidence_note, str(receipt.changed_fields))
        self.assertEqual(len(receipt.request_digest), 64)

    def test_prepared_approved_verified_require_person_and_evidence(self):
        for stage in ("prepared", "approved", "verified"):
            for values in ({"responsible_person_id": None, "responsible_person_version": None}, {"evidence_note": "", "evidence_url": ""}):
                with self.subTest(stage=stage, values=values), self.assertRaises(ValidationError):
                    self.save(stage=stage, **values)
        self.assertFalse(TaskPreparation.objects.exists())
        self.assertFalse(TaskProgress.objects.exists())

    def test_verification_requires_completed_execution_and_does_not_complete_it(self):
        with self.assertRaisesRegex(ValidationError, "completada"):
            self.save(stage="verified")
        in_progress = self.progress("in_progress")
        with self.assertRaises(ValidationError):
            self.save(stage="verified")
        in_progress.refresh_from_db()
        self.assertEqual(in_progress.status, "in_progress")
        self.assertEqual(in_progress.version, 1)
        self.assertFalse(TaskPreparation.objects.exists())

    def test_verification_tracks_exact_progress_version_and_reopening_invalidates_read_only(self):
        completed = self.progress()
        record = self.save(stage="verified")
        self.assertEqual(record.verified_progress_version, completed.version)
        self.assertEqual(preparation_state(record, self.event)["label"], "Verificado por el organizador")
        reopened = self.progress("in_progress", completed.version)
        self.assertFalse(preparation_state(record, self.event)["valid"])
        self.progress("completed", reopened.version)
        self.assertFalse(preparation_state(record, self.event)["valid"])
        record.refresh_from_db()
        self.assertEqual(record.stage, "verified")
        self.assertEqual(record.version, 1)
        self.assertEqual(record.changes.count(), 1)
        renewed = self.save(stage="verified", expected_version=1)
        self.assertTrue(preparation_state(renewed, self.event)["valid"])
        self.assertEqual(renewed.verified_progress_version, 3)
        self.assertEqual(renewed.changes.count(), 2)

    def test_changed_contact_invalidates_stored_assertion_without_rewriting_history(self):
        record = self.save()
        self.person = upsert_person(actor=self.owner, full_name="Nombre revisado", category="participant",
            object_id=self.person.pk, expected_version=self.person.version)
        self.assertFalse(preparation_state(record, self.event)["valid"])
        record.refresh_from_db()
        self.assertEqual(record.stage, "prepared")
        self.assertEqual(record.version, 1)
        with self.assertRaises(ValidationError):
            self.save(expected_version=1, responsible_person_version=1)
        renewed = self.save(expected_version=1)
        self.assertTrue(preparation_state(renewed, self.event)["valid"])

    def test_foreign_archived_or_wrong_version_responsibles_are_rejected(self):
        foreign = upsert_person(actor=self.other, full_name="Contacto ajeno", category="participant")
        inactive = upsert_person(actor=self.owner, full_name="Contacto archivado", category="guest", is_active=False)
        for values in (
            {"responsible_person_id": foreign.pk, "responsible_person_version": foreign.version},
            {"responsible_person_id": inactive.pk, "responsible_person_version": inactive.version},
            {"responsible_person_version": self.person.version + 1},
            {"responsible_person_version": True},
            {"responsible_person_version": None},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.save(**values)
        self.assertFalse(TaskPreparation.objects.exists())

    def test_owner_activity_and_role_are_requeried_before_any_write_or_receipt_replay(self):
        with self.assertRaises(PermissionDenied):
            self.save(actor=self.other)
        key = uuid.uuid4()
        self.save(request_key=key)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.save(request_key=key)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=True)
        PortalAccount.objects.create(user=self.owner, role="reviewer")
        with self.assertRaises(PermissionDenied):
            self.save(request_key=key)
        self.assertEqual(PreparationChange.objects.count(), 1)

    def test_exact_plan_and_known_task_are_required_even_for_retries(self):
        key = uuid.uuid4()
        record = self.save(request_key=key)
        with self.assertRaises(ValidationError):
            self.save(task_id="inventada")
        newer = self.approve(payload())
        with self.assertRaises(TaskPlanConflict):
            self.save(request_key=key)
        self.assertEqual(TaskPreparation.objects.filter(plan=newer).count(), 0)
        self.assertFalse(preparation_state(record, self.event)["valid"])

    def test_cas_conflicts_reject_stale_updates_including_equal_values(self):
        record = self.save()
        with self.assertRaises(PreparationConflict):
            self.save()
        for bad in (-1, True, "1", None):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.save(expected_version=bad)
        record.refresh_from_db()
        self.assertEqual(record.version, 1)

    def test_idempotent_receipt_replay_returns_current_record_without_reinstating_history(self):
        key = uuid.uuid4()
        self.save(request_key=key)
        latest = self.save(stage="approved", expected_version=1)
        replay = self.save(request_key=key)
        self.assertEqual(replay.pk, latest.pk)
        self.assertEqual(replay.stage, "approved")
        self.assertEqual(replay.version, 2)
        self.assertEqual(replay.changes.count(), 2)
        with self.assertRaisesRegex(ValidationError, "otros datos"):
            self.save(request_key=key, evidence_note="Contenido diferente")

    def test_evidence_can_be_https_reference_without_fetching_or_confirming_it(self):
        record = self.save(evidence_note="", evidence_url="https://example.org/material?version=1")
        self.assertEqual(record.evidence_url, "https://example.org/material?version=1")
        self.assertTrue(preparation_state(record, self.event)["valid"])
        self.assertEqual(record.stage, "prepared")
        self.assertFalse(TaskProgress.objects.exists())

    def test_invalid_links_naive_dates_and_oversized_evidence_are_rejected(self):
        for values in (
            {"evidence_url": "http://example.org/evidence"},
            {"evidence_url": "javascript:alert(1)"},
            {"evidence_url": "https://user:password@example.org/evidence"},
            {"evidence_note": "x" * 1001}, {"evidence_url": "https://example.org/" + "x" * 1000},
            {"due_at": datetime(2026, 11, 15, 9)}, {"due_at": "2026-11-15"},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.save(**values)
        self.assertFalse(TaskPreparation.objects.exists())

    def test_return_to_pending_requires_a_reason_and_clears_verification_snapshot(self):
        self.progress()
        self.save(stage="verified")
        with self.assertRaisesRegex(ValidationError, "motivo"):
            self.save(stage="pending", expected_version=1, evidence_note="")
        pending = self.save(stage="pending", expected_version=1, evidence_note="Revisaremos el documento corregido.",
            responsible_person_id=None, responsible_person_version=None)
        self.assertEqual(pending.stage, "pending")
        self.assertIsNone(pending.verified_progress_version)
        self.assertEqual(TaskProgress.objects.get().status, "completed")
        self.assertEqual(pending.changes.count(), 2)

    def test_same_values_do_not_duplicate_a_human_assertion_and_history_is_append_only(self):
        record = self.save()
        same = self.save(expected_version=1)
        self.assertEqual(same.version, 1)
        self.assertEqual(same.changes.count(), 1)
        receipt = record.changes.get()
        receipt.to_stage = "verified"
        with self.assertRaises(ValidationError):
            receipt.save()
        with self.assertRaises(ValidationError):
            receipt.delete()

    def test_projection_has_all_current_tasks_and_performs_no_writes(self):
        rows = preparation_rows(self.event)
        self.assertEqual([row["task_id"] for row in rows], ["t1", "t2"])
        self.assertTrue(all(row["state"]["stage"] == "pending" for row in rows))
        self.assertFalse(TaskPreparation.objects.exists())
        self.progress()
        self.save(stage="verified")
        self.progress("in_progress", 1)
        rows = preparation_rows(self.event)
        self.assertEqual(rows[0]["state"]["stage"], "review_required")
        self.assertEqual(TaskPreparation.objects.get().stage, "verified")


@override_settings(ROOT_URLCONF=__name__)
class PreparationViewTests(PreparationFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.url = reverse("preparation_test", args=[self.event.pk])

    def form_data(self, **overrides):
        return {
            "plan_id": str(self.plan.pk), "task_id": "t1", "stage": "prepared", "expected_version": "0",
            "request_key": str(uuid.uuid4()), "responsible_person": f"{self.person.pk}:{self.person.version}",
            "evidence_note": "Revisión declarada desde el formulario.", "evidence_url": "", "due_at": "2026-11-15T11:00",
        } | overrides

    def test_owner_get_shows_tasks_without_creating_records(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Responsables y evidencia")
        self.assertContains(response, "Verificado por el organizador")
        self.assertContains(response, self.person.full_name)
        self.assertFalse(TaskPreparation.objects.exists())

    def test_post_saves_one_task_and_does_not_change_execution(self):
        response = self.client.post(self.url, self.form_data())
        self.assertRedirects(response, self.url)
        record = TaskPreparation.objects.get()
        self.assertEqual(record.task_id, "t1")
        self.assertEqual(record.stage, "prepared")
        self.assertEqual(record.due_at.isoformat(), "2026-11-15T16:00:00+00:00")
        self.assertFalse(TaskProgress.objects.exists())

    def test_stale_form_gets_conflict_and_retains_user_input(self):
        self.save()
        response = self.client.post(self.url, self.form_data(evidence_note="Texto aún no guardado"))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Texto aún no guardado", status_code=409)
        self.assertEqual(TaskPreparation.objects.get().version, 1)

    def test_form_cannot_select_foreign_archived_or_changed_contact_versions(self):
        foreign = upsert_person(actor=self.other, full_name="Privado ajeno", category="participant")
        response = self.client.get(self.url)
        self.assertNotContains(response, foreign.full_name)
        self.assertEqual(self.client.post(self.url, self.form_data(responsible_person=f"{foreign.pk}:1")).status_code, 400)
        self.assertEqual(self.client.post(self.url, self.form_data(responsible_person=f"{self.person.pk}:99")).status_code, 400)
        self.assertFalse(TaskPreparation.objects.exists())

    def test_reopened_execution_is_presented_as_review_required(self):
        self.progress()
        self.save(stage="verified")
        self.progress("in_progress", 1)
        response = self.client.get(self.url)
        self.assertContains(response, "Requiere revisión del organizador")
        self.assertContains(response, "La ejecución cambió")
        self.assertEqual(TaskPreparation.objects.get().stage, "verified")

    def test_other_owner_and_reviewer_cannot_read_or_write(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.form_data()).status_code, 404)
        PortalAccount.objects.create(user=self.owner, role="reviewer")
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertFalse(TaskPreparation.objects.exists())

    def test_csrf_and_post_only_mutation(self):
        self.client.handler.enforce_csrf_checks = True
        self.assertEqual(self.client.post(self.url, self.form_data()).status_code, 403)
        self.client.handler.enforce_csrf_checks = False
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertFalse(TaskPreparation.objects.exists())
