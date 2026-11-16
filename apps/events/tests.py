from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from .services import create_event, update_event


class EventCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="event-owner", password="local-test-password")
        cls.other = get_user_model().objects.create_user(username="event-other", password="local-test-password")

    def event(self):
        return create_event(actor=self.owner, title="Seminario", brief="Seminario académico virtual")

    def test_material_edits_increment_snapshot_revision(self):
        event = self.event()
        updated = update_event(event_id=event.pk, actor=self.owner, capacity=80)
        self.assertEqual(updated.revision, 2)
        self.assertEqual(updated.capacity, 80)
        unchanged = update_event(event_id=event.pk, actor=self.owner, capacity=80)
        self.assertEqual(unchanged.revision, 2)

    def test_other_owner_cannot_modify_event(self):
        event = self.event()
        with self.assertRaises(PermissionDenied):
            update_event(event_id=event.pk, actor=self.other, title="Acceso ajeno")
        event.refresh_from_db()
        self.assertEqual(event.title, "Seminario")
        self.assertEqual(event.revision, 1)

    def test_commands_do_not_accept_owner_or_plan_fields(self):
        event = self.event()
        with self.assertRaises(ValidationError):
            update_event(event_id=event.pk, actor=self.owner, owner=self.other)

    def test_timezone_and_capacity_are_validated(self):
        for kwargs in ({"timezone": "Inventada/Lima"}, {"capacity": 0}, {"capacity": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                create_event(actor=self.owner, title="Evento", brief="Descripción", **kwargs)

    def test_naive_start_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_event(actor=self.owner, title="Evento", brief="Descripción", starts_at=datetime(2026, 11, 14, 9))
