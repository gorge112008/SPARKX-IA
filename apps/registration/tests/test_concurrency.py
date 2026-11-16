"""Run only on an isolated PostgreSQL test database; SQLite cannot verify locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase

from apps.events.models import Event
from apps.events.services import create_event
from apps.planning.models import PlanCandidate, PlanRevision
from apps.registration.models import Registration, RegistrationSubmission
from apps.registration.services import set_registration_state, submission_token, submit_registration


@skipUnless(connection.vendor == "postgresql", "El aforo y el cierre concurrentes requieren PostgreSQL.")
class PostgreSQLRegistrationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="registration-race")
        self.event = create_event(actor=self.owner, title="Último cupo", brief="Prueba sintética de concurrencia", capacity=1)
        candidate = PlanCandidate.objects.create(event=self.event, payload={}, base_revision=1, created_by=self.owner)
        self.plan = PlanRevision.objects.create(event=self.event, version=1, payload={}, approved_by=self.owner, candidate=candidate)
        Event.objects.filter(pk=self.event.pk).update(active_plan=self.plan)
        self.page = set_registration_state(event_id=self.event.pk, actor=self.owner, action="open", expected_version=0,
                                           expected_revision=1, expected_plan=self.plan.pk, confirmed=True)

    def parallel(self, operation):
        barrier = Barrier(2)

        def work(index):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                barrier.wait(timeout=10)
                return operation(index)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work, index) for index in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_competing_last_seat_preserves_capacity(self):
        tokens = [submission_token(self.page), submission_token(self.page)]
        receipts = self.parallel(lambda index: submit_registration(
            token=self.page.public_token, full_name=f"Persona {index}", email=f"persona{index}@example.test",
            form_token=tokens[index],
        ))
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(Registration.objects.filter(event=self.event, status="active").count(), 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 2)

    def test_same_key_race_commits_one_seat_and_receipt(self):
        key = submission_token(self.page)
        self.parallel(lambda index: submit_registration(token=self.page.public_token, full_name="Persona",
                                                        email="persona@example.test", form_token=key))
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)

    def test_closure_holding_event_lock_rejects_waiting_submission(self):
        barrier = Barrier(2)
        key = submission_token(self.page)

        def close_first():
            close_old_connections()
            try:
                with transaction.atomic():
                    Event.objects.select_for_update().get(pk=self.event.pk)
                    barrier.wait(timeout=10)
                    set_registration_state(event_id=self.event.pk, actor=self.owner, action="closed", expected_version=1,
                                           expected_revision=1, expected_plan=self.plan.pk, confirmed=True)
            finally:
                connections.close_all()

        def submit_waiting():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                barrier.wait(timeout=10)
                submit_registration(token=self.page.public_token, full_name="Persona", email="persona@example.test", form_token=key)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(close_first), pool.submit(submit_waiting)]
            for future in futures:
                future.result(timeout=20)
        self.page.refresh_from_db()
        self.assertEqual(self.page.state, "closed")
        self.assertFalse(Registration.objects.exists())
