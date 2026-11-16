"""Real locking checks are intentionally unavailable on SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from .models import Person
from .services import upsert_person


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class DirectoryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="directory-race")

    def parallel(self, operation):
        barrier = Barrier(2)
        def work(index):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.owner.pk)
                barrier.wait(timeout=10)
                try:
                    operation(actor, index)
                    return "saved"
                except ValidationError:
                    return "rejected"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work, index) for index in range(2)]
            return sorted(f.result(timeout=20) for f in futures)

    def test_same_email_race_creates_one_contact(self):
        result = self.parallel(lambda actor, index: upsert_person(
            actor=actor, full_name=f"Persona {index}", category="guest", email="same@example.invalid"))
        self.assertEqual(result, ["rejected", "saved"])
        self.assertEqual(Person.objects.count(), 1)

    def test_same_version_race_preserves_one_winner(self):
        person = upsert_person(actor=self.owner, full_name="Original", category="guest")
        result = self.parallel(lambda actor, index: upsert_person(
            actor=actor, object_id=person.pk, expected_version=1, full_name=f"Cambio {index}", category="guest"))
        self.assertEqual(result, ["rejected", "saved"])
        person.refresh_from_db()
        self.assertEqual(person.version, 2)
