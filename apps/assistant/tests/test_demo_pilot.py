"""The narrated pilot endpoint reads a single owned synthetic event only."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.directory.models import Organization
from apps.events.models import Event
from apps.events.services import create_event

from apps.assistant.demo_pilot import PILOT_EVENT_ID, demo_pilot
from apps.assistant.execution import agent_execution
from apps.assistant.models import EventCreationDraft


class DemoPilotTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="pilot-owner")
        self.other = users.create_user(username="pilot-other")
        PortalAccount.objects.create(user=self.owner, role="organizer")
        PortalAccount.objects.create(user=self.other, role="organizer")
        self.url = reverse("assistant:demo_pilot")
        self.client.force_login(self.owner)

    def pilot(self, **changes):
        values = {
            "actor": self.owner,
            "event_id": PILOT_EVENT_ID,
            "title": "Piloto GICA",
            "brief": "Datos declarados del piloto; Zoom pendiente.",
            "starts_at": datetime(2026, 11, 20, 0, 30, tzinfo=ZoneInfo("UTC")),
            "timezone": "America/Lima",
            "scheduled_dates": ["2026-11-19"],
            "capacity": 100,
            "is_synthetic": True,
        }
        values.update(changes)
        return create_event(**values)

    def assert_no_cache(self, response):
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_owner_receives_only_the_contract_with_local_date_and_current_data(self):
        event = self.pilot()
        event.interview_answers = {
            "modality": {"status": "assumed", "value": "Virtual"},
            "duration_minutes": {"status": "assumed", "value": "90"},
        }
        event.save(update_fields=["interview_answers"])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assert_no_cache(response)
        data = response.json()
        self.assertEqual(set(data), {"available", "event_id", "event_url", "fields"})
        self.assertTrue(data["available"])
        self.assertEqual(data["event_id"], str(event.pk))
        self.assertEqual(data["event_url"], reverse("events:detail", args=[event.pk]))
        fields = data["fields"]
        self.assertEqual(set(fields), {
            "title", "organization_id", "organization_name", "brief", "date",
            "scheduled_dates", "time", "timezone", "capacity", "is_synthetic",
            "interview_answers",
        })
        self.assertEqual(fields["date"], "2026-11-19")
        self.assertEqual(fields["time"], "19:30")
        self.assertEqual(fields["interview_answers"], event.interview_answers)
        self.assertIsNone(fields["organization_id"])
        self.assertEqual(fields["organization_name"], "")
        event.title = "Título corregido por el propietario"
        event.save(update_fields=["title"])
        self.assertEqual(self.client.get(self.url).json()["fields"]["title"], event.title)

    def test_missing_foreign_and_real_events_are_indistinguishable(self):
        missing = self.client.get(self.url)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json(), {"available": False})
        self.assert_no_cache(missing)
        event = self.pilot(actor=self.other)
        self.assertEqual(self.client.get(self.url).json(), missing.json())
        event.owner = self.owner
        event.is_synthetic = False
        event.save(update_fields=["owner", "is_synthetic"])
        self.assertEqual(self.client.get(self.url).json(), missing.json())

    def test_organization_is_exposed_only_when_owned(self):
        organization = Organization.objects.create(owner=self.owner, name="GICA", name_key="gica")
        event = self.pilot(organization_id=organization.pk)
        fields = self.client.get(self.url).json()["fields"]
        self.assertEqual(fields["organization_name"], "GICA")
        self.assertEqual(fields["organization_id"], str(organization.pk))
        # Even malformed legacy cross-owner references cannot disclose a name.
        Organization.objects.filter(pk=organization.pk).update(owner=self.other)
        fields = self.client.get(self.url).json()["fields"]
        self.assertIsNone(fields["organization_id"])
        self.assertEqual(fields["organization_name"], "")

    def test_no_start_is_returned_without_inventing_a_date_or_time(self):
        self.pilot(starts_at=None, scheduled_dates=[])
        fields = self.client.get(self.url).json()["fields"]
        self.assertIsNone(fields["date"])
        self.assertEqual(fields["time"], "")
        self.assertEqual(fields["scheduled_dates"], [])

    def test_unauthenticated_and_reviewer_do_not_receive_the_snapshot(self):
        self.pilot()
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)
        self.client.force_login(self.owner)
        PortalAccount.objects.filter(user=self.owner).update(role="reviewer")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Datos declarados del piloto", status_code=403)

    def test_current_role_and_activation_are_checked_beyond_request_user_cache(self):
        self.pilot()
        request = RequestFactory().get(self.url)
        request.user = self.owner
        PortalAccount.objects.filter(user=self.owner).update(role="reviewer")
        self.assertEqual(demo_pilot(request).status_code, 403)
        PortalAccount.objects.filter(user=self.owner).update(role="organizer")
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertEqual(demo_pilot(request).status_code, 403)

    def test_agent_execution_is_rejected_even_for_an_owner(self):
        self.pilot()
        with agent_execution("gica-1"):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"available": False})

    def test_post_is_not_a_creation_route_and_repeated_reads_have_no_writes(self):
        self.pilot()
        count = Event.objects.count()
        self.assertEqual(self.client.post(self.url, {"title": "No crear"}).status_code, 405)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            for _ in range(2):
                self.assertTrue(self.client.get(self.url).json()["available"])
        self.assertFalse(any(
            query["sql"].lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE "))
            for query in queries
        ))
        self.assertEqual(Event.objects.count(), count)
        self.assertEqual(EventCreationDraft.objects.count(), 0)
