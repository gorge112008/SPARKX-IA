"""Human progress, exact-plan writes, durable receipts and conservative carry."""

from copy import deepcopy
from queue import Queue
from threading import Barrier, Thread
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from apps.events.services import create_event, update_event

from apps.planning.models import PlanCandidate, PlanRevision, TaskProgress, TaskProgressChange
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.task_progress import TaskPlanConflict, TaskProgressConflict, update_task_progress


def _payload():
    def task(identifier, title, dependencies=()):
        return {"id": identifier, "title": title, "purpose": f"Preparar: {title}",
                "depends_on": list(dependencies), "status": "pending"}

    return {
        "title": "Seminario", "summary": "Preparación del evento", "sessions": [], "risks": [],
        "tasks": [task("a", "Confirmar fecha"), task("b", "Preparar sala", ("a",)),
                  task("c", "Realizar ensayo", ("a", "b")), task("d", "Publicar materiales")],
    }


class TaskProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="progress-owner")
        cls.other = get_user_model().objects.create_user(username="progress-other")

    def setUp(self):
        self.event = create_event(actor=self.owner, title="Seminario", brief="Preparación manual")
        self.plan = self.approve(_payload())

    def approve(self, payload):
        self.event.refresh_from_db()
        candidate = create_candidate(
            event=self.event, actor=self.owner, payload=payload,
            base_revision=self.event.revision, base_plan_id=self.event.active_plan_id,
        )
        plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return plan

    def change(self, *, task_id="a", status=TaskProgress.Status.IN_PROGRESS,
               expected_version=0, request_key=None, note="", **overrides):
        parameters = {
            "event": self.event, "actor": self.owner, "plan_id": self.plan.pk,
            "task_id": task_id, "status": status, "expected_version": expected_version,
            "request_key": request_key or uuid.uuid4(), "note": note,
        }
        return update_task_progress(**(parameters | overrides))

    def test_initial_and_current_noops_do_not_invent_changes_or_authorship(self):
        result = self.change(status=TaskProgress.Status.NOT_STARTED)
        self.assertIsNone(result)
        self.assertFalse(TaskProgress.objects.exists())
        self.assertFalse(TaskProgressChange.objects.exists())
        first = self.change(note="Empezamos")
        result = self.change(expected_version=1, note="Otra nota sin transición")
        self.assertEqual(result.pk, first.pk)
        self.assertEqual(result.version, 1)
        self.assertEqual(result.note, "Empezamos")
        self.assertEqual(result.updated_at, first.updated_at)
        self.assertEqual(result.changes.count(), 1)

    def test_manual_transitions_record_actor_time_and_preserve_approved_content(self):
        payload, event_version = deepcopy(self.plan.payload), self.event.revision
        started = self.change(note="Reunión iniciada")
        completed = self.change(
            status=TaskProgress.Status.COMPLETED, expected_version=1, note="Confirmación recibida",
        )
        reopened = self.change(expected_version=2, note="La fecha requiere otra confirmación")
        self.assertEqual(started.pk, completed.pk)
        self.assertEqual(reopened.version, 3)
        self.assertEqual(reopened.status, TaskProgress.Status.IN_PROGRESS)
        self.assertEqual(reopened.updated_by_id, self.owner.pk)
        changes = list(reopened.changes.order_by("version"))
        self.assertEqual([entry.version for entry in changes], [1, 2, 3])
        self.assertEqual([entry.from_status for entry in changes], [
            TaskProgress.Status.NOT_STARTED, TaskProgress.Status.IN_PROGRESS,
            TaskProgress.Status.COMPLETED,
        ])
        self.assertEqual(changes[-1].actor_id, self.owner.pk)
        self.assertEqual(changes[-1].created_at, reopened.updated_at)
        self.assertEqual(changes[-1].note, reopened.note)
        self.plan.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.plan.payload, payload)
        self.assertEqual(self.plan.candidate.payload, payload)
        self.assertEqual(self.event.revision, event_version)
        self.assertEqual(self.event.active_plan_id, self.plan.pk)

    def test_direct_completion_and_reopening_are_manual_without_dependency_cascades(self):
        progress = self.change(
            task_id="c", status=TaskProgress.Status.COMPLETED, note="Ensayo realizado por el equipo",
        )
        self.assertEqual(progress.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(
            list(self.plan.task_progress.values_list("task_id", flat=True)), ["c"],
        )
        result = self.change(
            task_id="c", status=TaskProgress.Status.NOT_STARTED, expected_version=1,
            note="Repetiremos el ensayo con otra configuración",
        )
        self.assertEqual(result.status, TaskProgress.Status.NOT_STARTED)
        self.assertEqual(result.version, 2)
        self.assertEqual(TaskProgressChange.objects.count(), 2)

    def test_completion_and_reopening_require_notes_but_completed_noop_does_not(self):
        with self.assertRaises(ValidationError) as caught:
            self.change(status=TaskProgress.Status.COMPLETED, note="   ")
        self.assertEqual(caught.exception.code, "note_required")
        self.assertFalse(TaskProgress.objects.exists())
        done = self.change(status=TaskProgress.Status.COMPLETED, note="Confirmado por el equipo")
        no_op = self.change(status=TaskProgress.Status.COMPLETED, expected_version=1)
        self.assertEqual(no_op.updated_at, done.updated_at)
        with self.assertRaises(ValidationError) as caught:
            self.change(expected_version=1)
        self.assertEqual(caught.exception.code, "note_required")
        done.refresh_from_db()
        self.assertEqual(done.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(done.changes.count(), 1)

    def test_owner_and_exact_active_plan_are_rechecked_even_for_old_receipts(self):
        key = uuid.uuid4()
        self.change(request_key=key)
        with self.assertRaises(PermissionDenied):
            self.change(actor=self.other, request_key=key)
        newer = self.approve(deepcopy(self.plan.payload))
        with self.assertRaises(TaskPlanConflict) as caught:
            self.change(request_key=key)
        self.assertEqual(caught.exception.code, "stale_task_plan")
        self.assertEqual(self.event.active_plan_id, newer.pk)
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_stale_version_rejects_equal_status_instead_of_hiding_lost_updates(self):
        first = self.change()
        with self.assertRaises(TaskProgressConflict) as caught:
            self.change(expected_version=0)
        self.assertEqual(caught.exception.code, "stale_task")
        with self.assertRaises(TaskProgressConflict):
            self.change(task_id="b", expected_version=1)
        first.refresh_from_db()
        self.assertEqual(first.version, 1)
        self.assertEqual(first.changes.count(), 1)

    def test_receipt_retry_returns_current_state_without_reactivating_old_status(self):
        key = uuid.uuid4()
        first = self.change(request_key=key, note="Comenzamos")
        repeated = self.change(request_key=str(key), note="Comenzamos")
        self.assertEqual(repeated.pk, first.pk)
        self.assertEqual(repeated.changes.count(), 1)
        self.change(status=TaskProgress.Status.COMPLETED, expected_version=1, note="Confirmado")
        repeated = self.change(request_key=key, note="Comenzamos")
        self.assertEqual(repeated.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(repeated.version, 2)
        self.assertEqual(repeated.changes.count(), 2)

    def test_reused_receipt_with_different_status_note_or_version_is_rejected(self):
        key = uuid.uuid4()
        self.change(request_key=key, note="Empezamos")
        for overrides in (
            {"status": TaskProgress.Status.COMPLETED}, {"note": "Otros datos"},
            {"expected_version": 1},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError) as caught:
                self.change(request_key=key, **({"note": "Empezamos"} | overrides))
            self.assertEqual(caught.exception.code, "task_request_conflict")
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_invalid_input_and_unknown_task_create_no_operational_records(self):
        for overrides in (
            {"status": "verified"}, {"status": []}, {"task_id": None}, {"task_id": " "},
            {"task_id": "x" * 65}, {"task_id": "unknown"}, {"expected_version": True},
            {"expected_version": -1}, {"expected_version": "0"}, {"request_key": "bad"},
            {"request_key": 123}, {"note": None}, {"note": "x" * 1001},
            {"plan_id": "not-a-uuid"}, {"plan_id": uuid.uuid4()},
        ):
            parameters = {"event": self.event, "actor": self.owner, "plan_id": self.plan.pk,
                          "task_id": "a", "status": TaskProgress.Status.IN_PROGRESS,
                          "expected_version": 0, "request_key": uuid.uuid4(), "note": ""}
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                update_task_progress(**(parameters | overrides))
        self.assertFalse(TaskProgress.objects.exists())
        self.assertFalse(TaskProgressChange.objects.exists())

    def test_transition_and_receipt_are_atomic_on_first_write_and_existing_progress(self):
        with patch("apps.planning.task_progress.TaskProgressChange.objects.create",
                   side_effect=RuntimeError("receipt unavailable")):
            with self.assertRaises(RuntimeError):
                self.change()
        self.assertFalse(TaskProgress.objects.exists())
        first = self.change()
        with patch("apps.planning.task_progress.TaskProgressChange.objects.create",
                   side_effect=RuntimeError("receipt unavailable")):
            with self.assertRaises(RuntimeError):
                self.change(status=TaskProgress.Status.COMPLETED, expected_version=1, note="Hecho")
        first.refresh_from_db()
        self.assertEqual(first.status, TaskProgress.Status.IN_PROGRESS)
        self.assertEqual(first.version, 1)
        self.assertEqual(first.changes.count(), 1)

    def test_saved_audit_entries_cannot_be_edited_or_individually_deleted(self):
        progress = self.change()
        entry = progress.changes.get()
        entry.note = "Sustituir la evidencia"
        with self.assertRaises(ValidationError):
            entry.save()
        with self.assertRaises(ValidationError):
            entry.delete()
        entry.refresh_from_db()
        self.assertEqual(entry.note, "")

    def test_approval_carries_provenance_but_does_not_invent_manual_changes(self):
        previous = self.change(status=TaskProgress.Status.COMPLETED, note="Confirmado por correo")
        self.change(task_id="b", note="Sala en preparación")
        newer = self.approve(deepcopy(self.plan.payload))
        inherited = newer.task_progress.get(task_id="a")
        self.assertEqual(inherited.status, previous.status)
        self.assertEqual(inherited.updated_by_id, previous.updated_by_id)
        self.assertEqual(inherited.updated_at, previous.updated_at)
        self.assertEqual(inherited.note, previous.note)
        self.assertEqual(inherited.version, 1)
        self.assertEqual(inherited.carried_from_id, previous.pk)
        self.assertEqual(inherited.changes.count(), 0)
        self.assertEqual(newer.task_progress.count(), 2)
        self.assertFalse(newer.task_progress.filter(task_id="c").exists())
        self.assertEqual(self.plan.task_progress.count(), 2)
        self.assertEqual(TaskProgressChange.objects.count(), 2)
        approve_candidate(candidate_id=newer.candidate_id, actor=self.owner)
        self.assertEqual(newer.task_progress.count(), 2)

    def test_changed_ancestor_invalidates_transitively_without_resetting_unrelated_tasks(self):
        for task in self.plan.payload["tasks"]:
            self.change(task_id=task["id"], status=TaskProgress.Status.COMPLETED, note="Declarado")
        changed = deepcopy(self.plan.payload)
        changed["tasks"][0]["purpose"] = "Confirmar una fecha y una zona diferentes"
        newer = self.approve(changed)
        self.assertEqual(list(newer.task_progress.values_list("task_id", flat=True)), ["d"])
        self.assertEqual(self.plan.task_progress.count(), 4)
        self.assertEqual(TaskProgressChange.objects.count(), 4)

    def test_material_event_edit_never_carries_equal_task_completion(self):
        previous = self.change(status=TaskProgress.Status.COMPLETED, note="Aforo confirmado")
        payload = deepcopy(self.plan.payload)
        update_event(event_id=self.event.pk, actor=self.owner, capacity=80)
        newer = self.approve(payload)
        self.assertEqual(newer.payload, payload)
        self.assertFalse(newer.task_progress.exists())
        previous.refresh_from_db()
        self.assertEqual(previous.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(previous.note, "Aforo confirmado")
        self.assertEqual(previous.changes.count(), 1)
        self.assertEqual(TaskProgress.objects.count(), 1)
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_new_dependency_invalidates_descendants_and_new_task_has_no_progress(self):
        for task in self.plan.payload["tasks"]:
            self.change(task_id=task["id"], note="Empezamos")
        changed = deepcopy(self.plan.payload)
        changed["tasks"].append({"id": "e", "title": "Nueva autorización", "purpose": "Autorizar",
                                 "depends_on": [], "status": "pending"})
        changed["tasks"][1]["depends_on"] = ["e"]
        newer = self.approve(changed)
        self.assertEqual(set(newer.task_progress.values_list("task_id", flat=True)), {"a", "d"})

    def test_normalized_ids_and_dependency_order_do_not_invalidate_unchanged_content(self):
        spaced = _payload()
        spaced["tasks"][0]["id"] = " a "
        spaced["tasks"][1]["depends_on"] = [" a "]
        spaced["tasks"][2]["depends_on"] = [" b ", " a "]
        self.plan = self.approve(spaced)
        progress = self.change(task_id=" a ", note="Normalizado")
        self.change(task_id="b")
        self.change(task_id="c")
        self.assertEqual(progress.task_id, "a")
        newer = self.approve(_payload())
        self.assertEqual(
            set(newer.task_progress.values_list("task_id", flat=True)), {"a", "b", "c"},
        )

    def test_removed_then_reintroduced_task_never_revives_older_progress(self):
        self.change(task_id="d", status=TaskProgress.Status.COMPLETED, note="Publicado")
        self.change(task_id="a")
        removed = deepcopy(self.plan.payload)
        removed["tasks"] = [task for task in removed["tasks"] if task["id"] != "d"]
        middle = self.approve(removed)
        newest = self.approve(deepcopy(self.plan.payload))
        self.assertFalse(middle.task_progress.filter(task_id="d").exists())
        self.assertFalse(newest.task_progress.filter(task_id="d").exists())
        self.assertTrue(newest.task_progress.filter(task_id="a").exists())
        self.assertEqual(self.plan.task_progress.get(task_id="d").status, "completed")

    def test_failed_carry_rolls_back_approval_and_new_revision(self):
        self.change()
        self.event.refresh_from_db()
        candidate = create_candidate(
            event=self.event, actor=self.owner, payload=deepcopy(self.plan.payload),
            base_revision=self.event.revision, base_plan_id=self.plan.pk,
        )
        with patch("apps.planning.task_progress.TaskProgress.objects.bulk_create",
                   side_effect=RuntimeError("carry unavailable")):
            with self.assertRaises(RuntimeError):
                approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, self.plan.pk)
        self.assertEqual(candidate.status, PlanCandidate.Status.PENDING)
        self.assertEqual(PlanRevision.objects.filter(event=self.event).count(), 1)
        self.assertEqual(TaskProgress.objects.count(), 1)


@skipUnless(connection.vendor == "postgresql", "Las carreras de tareas requieren PostgreSQL.")
class ConcurrentTaskProgressTests(TransactionTestCase):
    def run_competing_updates(self, *, same_key):
        owner = get_user_model().objects.create_user(username="concurrent-task-owner")
        event = create_event(actor=owner, title="Seminario", brief="Prueba de progreso concurrente")
        candidate = create_candidate(event=event, actor=owner, payload=_payload(), base_revision=1)
        plan = approve_candidate(candidate_id=candidate.pk, actor=owner)
        shared_key, barrier, results = uuid.uuid4(), Barrier(2), Queue()

        def apply(key):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=owner.pk)
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                barrier.wait(timeout=10)
                update_task_progress(
                    event=event, actor=actor, plan_id=plan.pk, task_id="a",
                    status=TaskProgress.Status.IN_PROGRESS, expected_version=0, request_key=key,
                )
                results.put("changed")
            except TaskProgressConflict:
                results.put("stale")
            except Exception as exc:
                results.put(type(exc).__name__)
            finally:
                connections.close_all()

        keys = [shared_key, shared_key if same_key else uuid.uuid4()]
        workers = [Thread(target=apply, args=(key,), daemon=True) for key in keys]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
            self.assertFalse(worker.is_alive(), "La actualización concurrente no finalizó.")
        outcomes = sorted(results.get_nowait() for _ in workers)
        self.assertEqual(outcomes, ["changed", "changed" if same_key else "stale"])
        self.assertEqual(TaskProgress.objects.get(plan=plan, task_id="a").version, 1)
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_competing_versions_apply_one_transition(self):
        self.run_competing_updates(same_key=False)

    def test_repeated_key_shares_one_atomic_receipt(self):
        self.run_competing_updates(same_key=True)
