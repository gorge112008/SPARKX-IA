from copy import deepcopy
from queue import Queue
from threading import Barrier, Thread
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from apps.events.services import create_event, update_event
from .domain import MAX_TASKS, plan_impact, validate_plan
from .models import PlanCandidate, PlanRevision
from .services import StalePlanError, approve_candidate, create_candidate, reject_candidate


def valid_plan():
    return {
        "title": "Seminario académico",
        "summary": "Sesión virtual con preparación y revisión del organizador.",
        "sessions": [
            {"id": "s1", "title": "Apertura", "start": "2026-11-14T09:00:00-05:00", "duration_minutes": 30, "speaker": "", "resource": "Sala virtual"},
            {"id": "s2", "title": "Conversatorio", "start": "2026-11-14T09:30:00-05:00", "duration_minutes": 30, "speaker": "", "resource": "Sala virtual"},
        ],
        "tasks": [
            {"id": "t1", "title": "Confirmar ponente", "depends_on": [], "status": "pending", "purpose": "Obtener confirmación antes de publicar."},
            {"id": "t2", "title": "Revisar agenda", "depends_on": ["t1"], "status": "pending", "purpose": "Validar la agenda con datos confirmados."},
        ],
        "risks": ["El ponente aún no está confirmado."],
    }


class PlanValidationTests(SimpleTestCase):
    def test_valid_plan_and_adjacent_sessions_are_accepted(self):
        self.assertEqual(validate_plan(valid_plan()), [])

    def test_untrusted_objects_and_unknown_fields_are_rejected(self):
        for payload in (None, [], "texto", {**valid_plan(), "approved_by": "modelo"}):
            with self.subTest(payload=payload):
                self.assertTrue(validate_plan(payload))

    def test_malformed_nested_values_are_errors_not_exceptions(self):
        plan = valid_plan()
        plan["sessions"] = [None, {"id": []}]
        plan["tasks"][0]["depends_on"] = [{"untrusted": "data"}]
        plan["tasks"][1]["id"] = []
        plan["risks"] = [None]
        self.assertTrue(validate_plan(plan))

    def test_invalid_durations_and_naive_dates_are_rejected(self):
        for duration in (0, -1, True, "30", 1441):
            plan = valid_plan()
            plan["sessions"][0]["duration_minutes"] = duration
            with self.subTest(duration=duration):
                self.assertTrue(validate_plan(plan))
        plan = valid_plan()
        plan["sessions"][0]["start"] = "2026-11-14T09:00:00"
        self.assertTrue(any("zona horaria" in error for error in validate_plan(plan)))

    def test_resource_overlap_accounts_for_different_timezone_offsets(self):
        plan = valid_plan()
        plan["sessions"][1]["start"] = "2026-11-14T14:15:00+00:00"
        self.assertTrue(any("solapan" in error for error in validate_plan(plan)))

    def test_same_speaker_cannot_overlap_even_in_different_rooms(self):
        plan = valid_plan()
        plan["sessions"][0]["speaker"] = "Ana Pérez"
        plan["sessions"][1].update(speaker="  ANA   PÉREZ ", resource="Otra sala", start="2026-11-14T09:15:00-05:00")
        self.assertTrue(any("ponente" in error and "solapan" in error for error in validate_plan(plan)))

    def test_unassigned_speakers_and_different_rooms_can_overlap(self):
        plan = valid_plan()
        plan["sessions"][1].update(resource="Otra sala", start="2026-11-14T09:15:00-05:00")
        self.assertEqual(validate_plan(plan), [])

    def test_cycles_and_missing_dependencies_are_rejected(self):
        plan = valid_plan()
        plan["tasks"][0]["depends_on"] = ["t2"]
        self.assertTrue(any("ciclo" in error for error in validate_plan(plan)))
        plan["tasks"][0]["depends_on"] = ["inexistente"]
        self.assertTrue(any("inexistente" in error for error in validate_plan(plan)))

    def test_duplicate_ids_and_dependencies_are_rejected(self):
        plan = valid_plan()
        plan["sessions"][1]["id"] = "s1"
        plan["tasks"][1]["depends_on"] = ["t1", "t1"]
        errors = validate_plan(plan)
        self.assertTrue(any("duplicado" in error for error in errors))
        self.assertTrue(any("repetir" in error for error in errors))

    def test_model_cannot_claim_real_execution(self):
        for status in ("prepared", "approved", "completed", "verified"):
            plan = valid_plan()
            plan["tasks"][0]["status"] = status
            with self.subTest(status=status):
                self.assertTrue(validate_plan(plan))

    def test_graph_size_is_bounded(self):
        plan = valid_plan()
        plan["tasks"] = [deepcopy(plan["tasks"][0]) for _ in range(MAX_TASKS + 1)]
        self.assertTrue(any("máximo" in error for error in validate_plan(plan)))

    def test_impact_reports_actual_changes_by_id(self):
        before = valid_plan()
        after = deepcopy(before)
        after["sessions"][0]["duration_minutes"] = 20
        after["tasks"].pop()
        impact = plan_impact(before, after)
        self.assertEqual(impact["sessions"]["changed"], ["s1"])
        self.assertEqual(impact["tasks"]["removed"], ["t2"])
        self.assertFalse(impact["risks_changed"])


class PlanCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="plan-owner", password="local-test-password")
        cls.other = get_user_model().objects.create_user(username="plan-other", password="local-test-password")

    def setUp(self):
        self.event = create_event(actor=self.owner, title="Seminario", brief="Evento académico")

    def candidate(self, payload=None):
        self.event.refresh_from_db()
        return create_candidate(event=self.event, actor=self.owner, payload=payload if payload is not None else valid_plan(), base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)

    def test_approve_updates_pointer_and_retains_exact_payload(self):
        candidate = self.candidate()
        revision = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, revision.pk)
        self.assertEqual(self.event.revision, 2)
        self.assertEqual(revision.payload, candidate.payload)
        self.assertEqual(candidate.status, PlanCandidate.Status.APPROVED)

    def test_old_approval_retry_never_reactivates_history(self):
        first = self.candidate()
        first_revision = approve_candidate(candidate_id=first.pk, actor=self.owner)
        second = self.candidate()
        second_revision = approve_candidate(candidate_id=second.pk, actor=self.owner)
        repeated = approve_candidate(candidate_id=first.pk, actor=self.owner)
        self.event.refresh_from_db()
        self.assertEqual(repeated.pk, first_revision.pk)
        self.assertEqual(self.event.active_plan_id, second_revision.pk)
        self.assertEqual(self.event.revision, 3)
        self.assertEqual(PlanRevision.objects.count(), 2)

    def test_two_candidates_from_same_snapshot_cannot_both_apply(self):
        first, second = self.candidate(), self.candidate()
        approve_candidate(candidate_id=first.pk, actor=self.owner)
        with self.assertRaises(StalePlanError):
            approve_candidate(candidate_id=second.pk, actor=self.owner)
        self.assertEqual(PlanRevision.objects.count(), 1)

    def test_event_edit_invalidates_existing_candidate(self):
        candidate = self.candidate()
        update_event(event_id=self.event.pk, actor=self.owner, capacity=80)
        with self.assertRaises(StalePlanError):
            approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.assertFalse(PlanRevision.objects.exists())

    def test_stale_creation_and_wrong_base_plan_are_rejected(self):
        with self.assertRaises(StalePlanError):
            create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=0)
        approve_candidate(candidate_id=self.candidate().pk, actor=self.owner)
        self.event.refresh_from_db()
        with self.assertRaises(StalePlanError):
            create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision, base_plan_id=None)

    def test_all_commands_enforce_event_ownership(self):
        candidate = self.candidate()
        for command in (approve_candidate, reject_candidate):
            with self.subTest(command=command.__name__), self.assertRaises(PermissionDenied):
                command(candidate_id=candidate.pk, actor=self.other)
        with self.assertRaises(PermissionDenied):
            create_candidate(event=self.event, actor=self.other, payload=valid_plan(), base_revision=1)
        self.assertFalse(PlanRevision.objects.exists())

    def test_invalid_candidate_is_visible_but_cannot_be_approved(self):
        plan = valid_plan()
        plan["tasks"][0]["status"] = "verified"
        candidate = self.candidate(plan)
        self.assertTrue(candidate.validation)
        with self.assertRaises(ValidationError):
            approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.assertFalse(PlanRevision.objects.exists())

    def test_rejection_is_idempotent_and_cannot_follow_approval(self):
        candidate = self.candidate()
        reject_candidate(candidate_id=candidate.pk, actor=self.owner)
        reject_candidate(candidate_id=candidate.pk, actor=self.owner)
        with self.assertRaises(ValidationError):
            approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        approved = self.candidate()
        approve_candidate(candidate_id=approved.pk, actor=self.owner)
        with self.assertRaises(ValidationError):
            reject_candidate(candidate_id=approved.pk, actor=self.owner)

    def test_candidate_content_and_approved_history_are_immutable(self):
        candidate = self.candidate()
        candidate.payload["summary"] = "Contenido sustituido tras mostrarlo"
        with self.assertRaises(ValidationError):
            candidate.save()
        candidate.refresh_from_db()
        revision = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        revision.payload["summary"] = "Reescritura de la historia"
        with self.assertRaises(ValidationError):
            revision.save()

    def test_non_json_payload_is_rejected_before_persistence(self):
        plan = valid_plan()
        plan["risks"] = [float("nan")]
        with self.assertRaises(ValidationError):
            self.candidate(plan)
        self.assertFalse(PlanCandidate.objects.exists())


@skipUnless(connection.vendor == "postgresql", "Las garantías de bloqueo se comprueban con PostgreSQL.")
class ConcurrentApprovalTests(TransactionTestCase):
    def test_only_one_competing_candidate_applies(self):
        owner = get_user_model().objects.create_user(username="concurrent-owner")
        event = create_event(actor=owner, title="Seminario", brief="Prueba de carrera")
        candidates = [create_candidate(event=event, actor=owner, payload=valid_plan(), base_revision=1) for _ in range(2)]
        barrier, results = Barrier(2), Queue()

        def apply(candidate_id):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=owner.pk)
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                barrier.wait(timeout=10)
                approve_candidate(candidate_id=candidate_id, actor=actor)
                results.put("approved")
            except StalePlanError:
                results.put("stale")
            except Exception as exc:
                results.put(type(exc).__name__)
            finally:
                connections.close_all()

        workers = [Thread(target=apply, args=(candidate.pk,), daemon=True) for candidate in candidates]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
            self.assertFalse(worker.is_alive(), "La aprobación concurrente no finalizó.")
        outcomes = sorted(results.get_nowait() for _ in workers)
        self.assertEqual(outcomes, ["approved", "stale"])
        event.refresh_from_db()
        self.assertEqual(event.revision, 2)
        self.assertEqual(PlanRevision.objects.filter(event=event).count(), 1)
