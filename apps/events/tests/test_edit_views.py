"""Explicit event edits preserve approved work and reject stale snapshots."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision, TaskProgress
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.task_progress import update_task_progress
from apps.planning.tests import valid_plan
from apps.events.models import Event
from apps.events.services import create_event, update_event


class EventEditEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="edit-owner")
        cls.other = get_user_model().objects.create_user(username="edit-other")

    def setUp(self):
        self.event = create_event(
            actor=self.owner, title="Seminario propio", brief="Objetivos del seminario virtual",
            starts_at=datetime(2026, 11, 14, 9, 30, tzinfo=ZoneInfo("America/New_York")),
            timezone="America/New_York", capacity=80,
        )
        self.client.force_login(self.owner)

    def url(self, name="edit", event=None, **kwargs):
        return reverse("events:" + name, kwargs={"event_id": (event or self.event).pk, **kwargs})

    def data(self, **changes):
        values = {
            "title": self.event.title, "brief": self.event.brief,
            "starts_at": "2026-11-14T09:30", "timezone": self.event.timezone,
            "capacity": self.event.capacity, "expected_revision": self.event.revision,
        }
        values.update(changes)
        return values

    def candidate(self):
        self.event.refresh_from_db()
        payload = valid_plan()
        for index, session in enumerate(payload["sessions"]):
            session["start"] = (self.event.starts_at + timedelta(minutes=30 * index)).isoformat()
        return create_candidate(
            event=self.event, actor=self.owner, payload=payload,
            base_revision=self.event.revision, base_plan_id=self.event.active_plan_id,
        )

    def test_edit_is_navigable_and_uses_event_local_time(self):
        detail = self.client.get(self.url("detail"))
        self.assertContains(detail, f'href="{self.url()}"')
        response = self.client.get(self.url())
        self.assertContains(response, 'value="2026-11-14T09:30"')
        self.assertContains(response, 'name="expected_revision" value="1"')
        self.assertContains(response, "Guardar ficha")
        self.assertEqual(response.context["form"].initial["timezone"], "America/New_York")

    def test_owner_edit_updates_existing_event_and_revision_without_ai(self):
        response = self.client.post(self.url(), self.data(
            title="Seminario corregido", starts_at="2026-11-14T18:00", timezone="America/Lima",
            owner=self.other.pk, active_plan=str(uuid.uuid4()), revision=999,
        ))
        self.assertRedirects(response, self.url("detail"))
        self.event.refresh_from_db()
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(self.event.title, "Seminario corregido")
        self.assertEqual(self.event.owner_id, self.owner.pk)
        self.assertEqual(self.event.starts_at.hour, 23)
        self.assertEqual(self.event.revision, 2)
        self.assertIsNone(self.event.active_plan_id)
        self.assertFalse(Job.objects.exists())

    def test_unchanged_edit_does_not_invalidate_current_revision(self):
        response = self.client.post(self.url(), self.data())
        self.assertRedirects(response, self.url("detail"))
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, 1)

    def test_invalid_input_preserves_fields_and_stored_event(self):
        response = self.client.post(self.url(), self.data(
            title="Conservar mi edición", capacity=0, starts_at="2026-11-01T01:30",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conservar mi edición")
        self.assertFormError(response.context["form"], "capacity", "Asegúrese de que este valor es mayor o igual a 1.")
        self.assertIn("starts_at", response.context["form"].errors)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Seminario propio")
        self.assertEqual(self.event.capacity, 80)
        self.assertEqual(self.event.revision, 1)

    def test_missing_revision_is_not_treated_as_current(self):
        values = self.data(title="No debe guardarse")
        del values["expected_revision"]
        response = self.client.post(self.url(), values)
        self.assertEqual(response.status_code, 200)
        self.assertIn("expected_revision", response.context["form"].errors)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Seminario propio")
        self.assertEqual(self.event.revision, 1)

    def test_stale_edit_requires_review_of_current_data_before_explicit_resubmit(self):
        attempted = self.data(title="Mi propuesta conservada", capacity=70)
        update_event(event_id=self.event.pk, actor=self.owner, title="Título vigente", capacity=50)
        response = self.client.post(self.url(), attempted)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Ficha actual · revisión 2", status_code=409)
        self.assertContains(response, "Título vigente", status_code=409)
        self.assertContains(response, "Mi propuesta conservada", status_code=409)
        self.assertContains(response, 'name="expected_revision" value="2"', status_code=409)
        self.assertContains(response, "No guardamos tus cambios", status_code=409)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Título vigente")
        self.assertEqual(self.event.capacity, 50)
        self.assertEqual(self.event.revision, 2)
        attempted["expected_revision"] = response.context["form"]["expected_revision"].value()
        saved = self.client.post(self.url(), attempted)
        self.assertRedirects(saved, self.url("detail"))
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Mi propuesta conservada")
        self.assertEqual(self.event.capacity, 70)
        self.assertEqual(self.event.revision, 3)

    def test_foreign_event_is_hidden_on_get_and_post(self):
        foreign = create_event(actor=self.other, title="Privado ajeno", brief="Descripción confidencial")
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url(event=foreign), self.data())
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, "Descripción confidencial", status_code=404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.revision, 1)

    def test_anonymous_edit_requires_login_and_unsupported_method_is_rejected(self):
        self.assertEqual(self.client.put(self.url(), self.data()).status_code, 405)
        self.client.logout()
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url(), self.data())
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response.url)

    def test_csrf_is_required_for_save(self):
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url(), self.data(title="Bloqueado sin CSRF")).status_code, 403)
        secured.get(self.url())
        values = self.data(title="Cambio con CSRF", csrfmiddlewaretoken=secured.cookies["csrftoken"].value)
        self.assertEqual(secured.post(self.url(), values).status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Cambio con CSRF")

    def test_edit_preserves_active_plan_and_task_progress_but_blocks_old_candidate(self):
        approved = approve_candidate(candidate_id=self.candidate().pk, actor=self.owner)
        self.event.refresh_from_db()
        task_id = approved.payload["tasks"][0]["id"]
        progress = update_task_progress(
            event=self.event, actor=self.owner, plan_id=approved.pk, task_id=task_id,
            status=TaskProgress.Status.COMPLETED, expected_version=0,
            request_key=str(uuid.uuid4()), note="Preparación confirmada por el organizador.",
        )
        pending = self.candidate()
        response = self.client.post(self.url(), self.data(capacity=60))
        self.assertRedirects(response, self.url("detail"))
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, approved.pk)
        progress.refresh_from_db()
        self.assertEqual(progress.status, TaskProgress.Status.COMPLETED)
        self.assertEqual(progress.version, 1)
        detail = self.client.get(self.url("detail"))
        self.assertContains(detail, "Esta propuesta usa una versión anterior")
        attempt = self.client.post(self.url("approve", candidate_id=pending.pk), {
            "expected_revision": pending.base_revision, "expected_plan": str(approved.pk),
        })
        self.assertEqual(attempt.status_code, 302)
        pending.refresh_from_db()
        self.assertEqual(pending.status, PlanCandidate.Status.PENDING)
        self.assertEqual(PlanRevision.objects.count(), 1)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, approved.pk)

    def test_conflict_display_escapes_current_and_submitted_content(self):
        update_event(event_id=self.event.pk, actor=self.owner, title="<script>current()</script>")
        response = self.client.post(self.url(), self.data(title="<script>input()</script>"))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "&lt;script&gt;current()&lt;/script&gt;", status_code=409)
        self.assertNotContains(response, "<script>current()</script>", status_code=409)
        self.assertNotContains(response, "<script>input()</script>", status_code=409)
