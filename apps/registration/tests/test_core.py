"""Security and persistence checks use Django's isolated test database only.

These sequential tests do not establish PostgreSQL concurrency guarantees.
"""
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.directory.models import Person
from apps.events.models import Event
from apps.events.services import create_event
from apps.planning.models import PlanCandidate, PlanRevision
from apps.registration.models import Registration, RegistrationPage, RegistrationSubmission
from apps.registration.services import (FORM_MAX_AGE, RECEIPT_MESSAGE, RegistrationConflict,
                       availability, set_registration_state, submission_token,
                       submit_registration)


class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="registration-owner")
        cls.other = get_user_model().objects.create_user(username="registration-other")
        cls.event = create_event(actor=cls.owner, title="Encuentro con inscripción", brief="Contexto privado que nunca debe publicarse", capacity=2)
        cls.candidate = PlanCandidate.objects.create(
            event=cls.event, payload={"private": "Propuesta privada"}, base_revision=1,
            created_by=cls.owner, status=PlanCandidate.Status.APPROVED,
        )
        cls.plan = PlanRevision.objects.create(event=cls.event, version=1, payload={"private": "Plan privado"},
                                              approved_by=cls.owner, candidate=cls.candidate)
        Event.objects.filter(pk=cls.event.pk).update(active_plan=cls.plan)
        cls.event.refresh_from_db()

    def state(self, action="open", **kwargs):
        event = Event.objects.get(pk=self.event.pk)
        page = RegistrationPage.objects.filter(event=event).first()
        defaults = dict(event_id=event.pk, actor=self.owner, action=action, expected_version=page.version if page else 0,
                        expected_revision=event.revision, expected_plan=event.active_plan_id, confirmed=True)
        defaults.update(kwargs)
        return set_registration_state(**defaults)

    def send(self, page, email="persona@example.test", name="Persona de prueba", form_token=None, **kwargs):
        return submit_registration(token=page.public_token, full_name=name, email=email,
                                   form_token=form_token or submission_token(page), **kwargs)

    def test_open_requires_approved_plan_and_explicit_confirmation(self):
        Event.objects.filter(pk=self.event.pk).update(active_plan=None)
        with self.assertRaises(ValidationError):
            self.state()
        self.assertFalse(RegistrationPage.objects.exists())
        Event.objects.filter(pk=self.event.pk).update(active_plan=self.plan)
        with self.assertRaises(ValidationError):
            self.state(confirmed=False)
        self.assertFalse(RegistrationPage.objects.exists())

    def test_command_rechecks_actor_ownership_activation_and_current_role(self):
        with self.assertRaises(PermissionDenied):
            self.state(actor=self.other)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.state()  # The in-memory owner still says is_active=True.
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=True)
        PortalAccount.objects.create(user=self.owner, role=PortalAccount.Role.REVIEWER)
        with self.assertRaises(PermissionDenied):
            self.state()
        self.assertFalse(RegistrationPage.objects.exists())

    def test_stale_event_plan_or_publication_versions_do_not_change_state(self):
        page = self.state()
        for kwargs in ({"expected_version": 0}, {"expected_revision": 0}, {"expected_plan": None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(RegistrationConflict):
                self.state("closed", **kwargs)
        page.refresh_from_db()
        self.assertEqual(page.state, "open")
        self.assertEqual(page.version, 1)

    def test_close_and_reopen_keep_plan_and_registrations(self):
        page = self.state()
        self.send(page)
        before = Event.objects.get(pk=self.event.pk)
        closed = self.state("closed")
        self.assertEqual(closed.version, 2)
        self.assertIsNotNone(closed.closed_at)
        reopened = self.state()
        self.assertEqual(reopened.version, 3)
        self.assertEqual(reopened.public_token, page.public_token)
        after = Event.objects.get(pk=self.event.pk)
        self.assertEqual((after.revision, after.active_plan_id), (before.revision, before.active_plan_id))
        self.assertEqual(Registration.objects.count(), 1)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.payload, {"private": "Plan privado"})

    def test_normalized_duplicate_is_generic_and_does_not_replace_person(self):
        page = self.state()
        accepted = self.send(page, email="  PERSONA@Example.Test  ", name=" Persona   inicial ")
        duplicate = self.send(page, email="persona@example.test", name="Otra identidad")
        self.assertEqual(accepted, duplicate)
        self.assertEqual(accepted, RECEIPT_MESSAGE)
        registration = Registration.objects.get()
        self.assertEqual(registration.email, "persona@example.test")
        self.assertEqual(registration.full_name, "Persona inicial")
        self.assertFalse(Person.objects.exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Registration.objects.create(event=self.event, full_name="Duplicado directo", email=registration.email)

    def test_submission_key_cannot_create_another_registration_on_replay(self):
        page = self.state()
        key = submission_token(page)
        self.send(page, form_token=key)
        self.send(page, form_token=key, email="otro@example.test", name="Otra persona")
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)
        self.assertEqual(Registration.objects.get().full_name, "Persona de prueba")

    def test_capacity_counts_only_active_and_full_has_same_receipt(self):
        Event.objects.filter(pk=self.event.pk).update(capacity=1)
        page = self.state()
        Registration.objects.create(event=self.event, full_name="Cancelada", email="cancelada@example.test", status="cancelled")
        first = self.send(page)
        full = self.send(page, email="otra@example.test")
        self.assertEqual(first, full)
        self.assertEqual(Registration.objects.filter(status="active").count(), 1)
        self.assertEqual(availability(Event.objects.get(pk=self.event.pk)), {"active": 1, "capacity": 1, "remaining": 0})
        self.send(page, email="cancelada@example.test", name="Intento de reactivar")
        self.assertEqual(Registration.objects.get(email="cancelada@example.test").status, "cancelled")

    def test_closed_or_stale_form_never_uses_a_seat(self):
        page = self.state()
        old_form = submission_token(page)
        self.state("closed")
        self.assertEqual(self.send(page, form_token=old_form), RECEIPT_MESSAGE)
        reopened = self.state()
        self.send(reopened, form_token=submission_token(page), email="vieja@example.test")
        self.assertFalse(Registration.objects.exists())
        self.send(reopened, email="nueva@example.test")
        self.assertEqual(Registration.objects.get().email, "nueva@example.test")

    def test_tampered_expired_and_other_page_forms_are_rejected(self):
        page = self.state()
        second_event = create_event(actor=self.owner, title="Otro", brief="Privado")
        other_candidate = PlanCandidate.objects.create(event=second_event, payload={}, base_revision=1, created_by=self.owner)
        other_plan = PlanRevision.objects.create(event=second_event, version=1, payload={}, approved_by=self.owner, candidate=other_candidate)
        Event.objects.filter(pk=second_event.pk).update(active_plan=other_plan)
        other_page = set_registration_state(event_id=second_event.pk, actor=self.owner, action="open", expected_version=0,
                                            expected_revision=1, expected_plan=other_plan.pk, confirmed=True)
        with patch("django.core.signing.time.time", return_value=time.time() - FORM_MAX_AGE - 10):
            expired = submission_token(page)
        for key in ("tampered", expired, submission_token(other_page)):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                self.send(page, form_token=key)
        self.assertFalse(RegistrationSubmission.objects.exists())
        self.send(page)
        self.send(other_page)
        self.assertEqual(Registration.objects.count(), 2)  # Uniqueness is per event.

    def test_new_approved_plan_pauses_until_explicit_republication_and_expires_old_forms(self):
        page = self.state()
        old_form = submission_token(page)
        candidate = PlanCandidate.objects.create(event=self.event, payload={}, base_revision=1, base_plan=self.plan,
                                                 created_by=self.owner, status=PlanCandidate.Status.APPROVED)
        new_plan = PlanRevision.objects.create(event=self.event, version=2, payload={}, approved_by=self.owner, candidate=candidate)
        Event.objects.filter(pk=self.event.pk).update(active_plan=new_plan)
        public_url = reverse("event_registration:public", kwargs={"token": page.public_token})
        response = self.client.get(public_url)
        self.assertNotContains(response, 'name="full_name"')
        self.assertContains(response, "Las inscripciones no están abiertas")
        self.send(page, email="en-pausa@example.test")
        self.assertFalse(Registration.objects.exists())
        self.client.force_login(self.owner)
        management = self.client.get(reverse("event_registration:manage", kwargs={"event_id": self.event.pk}))
        self.assertContains(management, "Inscripciones en pausa")
        self.assertContains(management, 'name="action" value="closed"')
        self.assertEqual(management.context["publication_action"], "open")
        republished = self.state("open")
        self.assertEqual(republished.version, 2)
        self.assertEqual(republished.published_plan_id, new_plan.pk)
        self.assertEqual(republished.public_token, page.public_token)
        self.send(republished, form_token=old_form, email="formulario-viejo@example.test")
        self.assertFalse(Registration.objects.exists())
        self.send(republished, email="nuevo-plan@example.test")
        self.assertEqual(Registration.objects.get().email, "nuevo-plan@example.test")

    def test_gets_do_not_publish_reserve_or_submit(self):
        self.client.force_login(self.owner)
        url = reverse("event_registration:manage", kwargs={"event_id": self.event.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(RegistrationPage.objects.exists())
        page = self.state()
        self.client.logout()
        public = reverse("event_registration:public", kwargs={"token": page.public_token})
        self.assertEqual(self.client.get(public).status_code, 200)
        self.assertEqual(self.client.get(reverse("event_registration:received", kwargs={"token": page.public_token})).status_code, 200)
        self.assertFalse(Registration.objects.exists())
        self.assertFalse(RegistrationSubmission.objects.exists())

    def test_public_page_has_opaque_token_minimum_fields_and_no_private_content(self):
        page = self.state()
        self.assertEqual(len(page.public_token), 43)
        self.assertNotIn(str(self.event.pk), page.public_token)
        url = reverse("event_registration:public", kwargs={"token": page.public_token})
        response = self.client.get(url)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "cupos disponibles")
        self.assertNotContains(response, self.event.brief)
        self.assertNotContains(response, "Plan privado")
        self.assertContains(response, 'name="full_name"')
        self.assertContains(response, 'name="email"')
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.get("/r/").status_code, 404)
        self.assertEqual(self.client.get(reverse("event_registration:public", kwargs={"token": self.event.pk})).status_code, 404)

    def test_public_post_receipt_matches_accepted_duplicate_full_and_closed(self):
        Event.objects.filter(pk=self.event.pk).update(capacity=1)
        page = self.state()
        url = reverse("event_registration:public", kwargs={"token": page.public_token})
        bodies = []
        for email in ("persona@example.test", "PERSONA@example.test", "sin-cupo@example.test"):
            response = self.client.post(url, {"full_name": "Persona", "email": email, "form_token": submission_token(page)}, follow=True)
            self.assertEqual(response.status_code, 200)
            bodies.append(response.content)
        self.state("closed")
        response = self.client.post(url, {"full_name": "Otra", "email": "cerrada@example.test", "form_token": submission_token(page)}, follow=True)
        bodies.append(response.content)
        self.assertTrue(all(body == bodies[0] for body in bodies))
        self.assertNotIn(b"persona@example.test", bodies[0])
        self.assertEqual(Registration.objects.count(), 1)

    def test_management_is_owner_only_and_state_endpoint_is_post_only(self):
        page = self.state()
        self.send(page)
        url = reverse("event_registration:manage", kwargs={"event_id": self.event.pk})
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "persona@example.test")
        self.assertEqual(self.client.get(reverse("event_registration:change_state", kwargs={"event_id": self.event.pk})).status_code, 405)

    def test_organizer_http_open_and_close_check_versions_and_confirmation(self):
        self.client.force_login(self.owner)
        url = reverse("event_registration:change_state", kwargs={"event_id": self.event.pk})
        payload = {"action": "open", "expected_version": 0, "expected_revision": 1,
                   "expected_plan": str(self.plan.pk)}
        self.assertEqual(self.client.post(url, payload).status_code, 400)
        self.assertFalse(RegistrationPage.objects.exists())
        payload["confirmed"] = "on"
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        page = RegistrationPage.objects.get()
        payload["action"] = "closed"
        self.assertEqual(self.client.post(url, payload).status_code, 409)
        page.refresh_from_db()
        self.assertEqual(page.state, "open")
        payload["expected_version"] = page.version
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.state, "closed")

    def test_reviewer_is_blocked_on_public_and_management_even_with_stale_actor(self):
        page = self.state()
        PortalAccount.objects.create(user=self.owner, role=PortalAccount.Role.REVIEWER)
        with self.assertRaises(PermissionDenied):
            self.send(page, actor=self.owner)
        self.client.force_login(self.owner)
        for name, kwargs in (("public", {"token": page.public_token}), ("manage", {"event_id": self.event.pk})):
            self.assertEqual(self.client.get(reverse("event_registration:" + name, kwargs=kwargs)).status_code, 403)
        self.assertFalse(Registration.objects.exists())

    def test_public_and_organizer_posts_require_csrf(self):
        page = self.state()
        client = Client(enforce_csrf_checks=True)
        public = reverse("event_registration:public", kwargs={"token": page.public_token})
        client.get(public)
        payload = {"full_name": "Persona", "email": "persona@example.test", "form_token": submission_token(page)}
        self.assertEqual(client.post(public, payload).status_code, 403)
        self.assertFalse(Registration.objects.exists())
        payload["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        self.assertEqual(client.post(public, payload).status_code, 302)
        client.force_login(self.owner)
        state_url = reverse("event_registration:change_state", kwargs={"event_id": self.event.pk})
        self.assertEqual(client.post(state_url, {"action": "closed"}).status_code, 403)
        page.refresh_from_db()
        self.assertEqual(page.state, "open")
