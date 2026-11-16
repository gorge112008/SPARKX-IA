"""Synthetic event creation with no remote models, jobs or live application data."""

from datetime import date, timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.directory.models import Organization
from apps.events.models import Event
from apps.jobs.models import Job, UIAction

from .event_creation import creation_turn, is_creation_request
from .execution import agent_execution
from .models import EventCreationDraft


ANSWERS = [
    "Seminario de tesis", "sin institución", "Ayudar a preparar una tesis de maestría.",
    "19/11/2026", "19:30", "sí", "50", "sí",
    "Preparar el proyecto de tesis", "Estudiantes de posgrado", "Virtual", "90 minutos",
    "Zoom, acceso pendiente", "Tres expositores ficticios", "Sin cobros ni envíos reales",
]


class EventCreationTests(TestCase):
    def setUp(self):
        local_day = patch("apps.assistant.event_creation.timezone.localdate", return_value=date(2026, 11, 15))
        local_day.start()
        self.addCleanup(local_day.stop)
        self.owner = get_user_model().objects.create_user(username="creation-owner")
        self.other = get_user_model().objects.create_user(username="creation-other")
        self.reviewer = get_user_model().objects.create_user(username="creation-reviewer")
        for actor in (self.owner, self.other, self.reviewer):
            PortalAccount.objects.create(user=actor, role="reviewer" if actor == self.reviewer else "organizer")
        self.state = None
        for target in ("apps.assistant.provider._opener.open", "apps.assistant.free_harness.run_free_harness", "apps.jobs.services.enqueue"):
            blocker = patch(target, side_effect=AssertionError("Event interview cannot invoke models or jobs"))
            mocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(mocked.assert_not_called)

    def begin(self, text="Hola Gica, quiero crear un evento", actor=None):
        self.state = creation_turn(actor or self.owner, text, expected_revision=0, request_id=uuid.uuid4())
        self.assertEqual(self.state["step_key"], "title")
        return self.state

    def answer(self, text="", **extra):
        actor = extra.pop("actor", self.owner)
        values = {"draft_id": self.state["draft_id"], "expected_revision": self.state["revision"], "request_id": uuid.uuid4(), **extra}
        self.state = creation_turn(actor, text, **values)
        return self.state

    def complete(self, answers=None):
        self.begin()
        for answer in answers or ANSWERS:
            response = self.answer(answer)
            self.assertFalse(response["error_code"], response)
        self.assertEqual(self.state["status"], "review")
        self.assertEqual(Event.objects.count(), 0)
        return self.state

    def test_complete_fifteen_answers_and_explicit_creation(self):
        self.complete()
        self.assertEqual(len(self.state["fields"]["interview_answers"]), 7)
        self.assertEqual(self.answer("sí")["error_code"], "confirmation_required")
        result = self.answer("sí, crear evento")
        self.assertEqual(result["status"], "created")
        event = Event.objects.get()
        self.assertEqual(event.owner, self.owner)
        self.assertEqual(event.title, ANSWERS[0])
        self.assertEqual(event.capacity, 50)
        self.assertEqual(event.timezone, "America/Lima")
        self.assertTrue(event.is_synthetic)
        self.assertEqual(event.starts_at.isoformat(), "2026-11-20T00:30:00+00:00")
        self.assertEqual(event.interview_answers["duration_minutes"]["value"], "90")
        self.assertEqual(event.scheduled_dates, ["2026-11-19"])
        self.assertIsNone(event.active_plan_id)
        self.assertEqual(result["event_url"], reverse("events:detail", args=[event.pk]))
        self.assertEqual((Job.objects.count(), AIUsage.objects.count(), UIAction.objects.count()), (0, 0, 0))

    def test_invalid_answer_preserves_step_and_revision(self):
        self.begin()
        for value in ANSWERS[:3]:
            self.answer(value)
        revision = self.state["revision"]
        result = self.answer("31/02/2026")
        self.assertEqual(result["error_code"], "invalid_answer")
        self.assertEqual(result["step_key"], "date")
        self.assertEqual(result["revision"], revision)
        self.assertIn("fecha válida", result["reply"])
        self.answer("19/11/2026")
        self.answer("25:99")
        self.assertEqual(self.state["step_key"], "time")
        self.answer("19:30")
        self.answer("sí")
        self.answer("100001")
        self.assertEqual(self.state["step_key"], "capacity")

    def test_duration_in_natural_hours_is_mechanical(self):
        for phrase, minutes in (("una hora y media", "90"), ("dos horas y quince minutos", "135"), ("media hora", "30")):
            self.begin()
            for value in ANSWERS[:11]:
                self.answer(value)
            self.assertEqual(self.state["step_key"], "duration_minutes")
            self.answer(phrase)
            self.assertEqual(self.state["fields"]["interview_answers"]["duration_minutes"]["value"], minutes)
            self.answer(operation="cancel")

    def test_missing_year_is_persisted_privately_then_answered_alone(self):
        self.begin()
        for value in ANSWERS[:3]:
            self.answer(value)
        revision = self.state["revision"]
        self.answer("5, 6 y 7 de septiembre")
        self.assertEqual(self.state["error_code"], "year_required")
        self.assertEqual(self.state["step_key"], "date")
        self.assertEqual(self.state["revision"], revision + 1)
        self.assertNotIn("_pending_date_year", self.state["fields"])
        self.assertEqual(EventCreationDraft.objects.get().data["_pending_date_year"], {"day_months": [[9, 5], [9, 6], [9, 7]]})
        resumed = creation_turn(self.owner, expected_revision=0, request_id=uuid.uuid4(), operation="resume")
        self.assertIn("¿De qué año?", resumed["reply"])
        self.answer("203")
        self.assertEqual(self.state["step_key"], "date")
        self.answer("2021")
        self.assertEqual(self.state["step_key"], "date")
        self.answer("2026")
        self.assertEqual(self.state["fields"]["scheduled_dates"], ["2026-09-05", "2026-09-06", "2026-09-07"])
        self.assertEqual(self.state["fields"]["date"], "2026-09-05")
        self.assertEqual(self.state["step_key"], "time")
        self.assertIn("sábado 5 de septiembre de 2026 y 2 fechas más", self.state["reply"])
        self.assertNotIn("_pending_date_year", EventCreationDraft.objects.get().data)
        self.assertLessEqual(len(self.state["reply"]), 280)

    def test_multiday_range_becomes_one_event_with_exact_dates(self):
        answers = [*ANSWERS]
        answers[3] = "del 19 al 21 de noviembre de 2026"
        self.complete(answers)
        self.answer("crear evento")
        event = Event.objects.get()
        self.assertEqual(event.scheduled_dates, ["2026-11-19", "2026-11-20", "2026-11-21"])
        self.assertEqual(Event.objects.count(), 1)

    def test_year_uses_current_server_year_not_a_fixed_constant(self):
        self.begin()
        for value in ANSWERS[:3]:
            self.answer(value)
        with patch("apps.assistant.event_creation.timezone.localdate", return_value=date(2030, 6, 10)):
            self.answer("5 de septiembre de 2026")
            self.assertEqual(self.state["error_code"], "year_required")
            self.assertIn("2030", self.state["reply"])
            self.answer("2040")
        self.assertEqual(self.state["fields"]["scheduled_dates"], ["2040-09-05"])

    def test_incomplete_date_correction_does_not_keep_old_schedule_visible(self):
        self.complete()
        self.answer(operation="edit", field="date")
        self.answer("5 de septiembre")
        self.assertEqual(self.state["step_key"], "date")
        self.assertNotIn("date", self.state["fields"])
        self.assertNotIn("scheduled_dates", self.state["fields"])
        self.answer("2026")
        self.assertEqual(self.state["status"], "review")
        self.assertEqual(self.state["fields"]["scheduled_dates"], ["2026-09-05"])

    def test_resume_private_and_one_active_draft(self):
        first = self.begin()
        resumed = creation_turn(self.owner, expected_revision=0, request_id=uuid.uuid4(), operation="resume")
        self.assertEqual(resumed["draft_id"], first["draft_id"])
        self.begin()
        self.assertEqual(EventCreationDraft.objects.count(), 1)
        self.assertFalse(creation_turn(self.other, expected_revision=0, request_id=uuid.uuid4(), operation="resume")["handled"])
        with self.assertRaises(Http404):
            creation_turn(self.other, "privado", draft_id=first["draft_id"], expected_revision=first["revision"], request_id=uuid.uuid4())
        with transaction.atomic(), self.assertRaises(IntegrityError):
            EventCreationDraft.objects.create(owner=self.owner, expires_at=timezone.now() + timedelta(hours=1))

    def test_stored_draft_cannot_capture_unrelated_new_command(self):
        self.begin()
        before = EventCreationDraft.objects.get()
        for text in ("abre calendario", "gracias", "qué es mantenimiento predictivo"):
            result = creation_turn(self.owner, text, expected_revision=0, request_id=uuid.uuid4())
            self.assertFalse(result["handled"])
        after = EventCreationDraft.objects.get()
        self.assertEqual((before.data, before.revision, before.updated_at), (after.data, after.revision, after.updated_at))
        self.answer("abre calendario")
        self.assertEqual(self.state["fields"]["title"], "abre calendario")
        self.assertEqual(UIAction.objects.count(), 0)

    def test_revision_and_latest_delivery_are_idempotent(self):
        self.begin()
        values = {"draft_id": self.state["draft_id"], "expected_revision": self.state["revision"], "request_id": uuid.uuid4()}
        one = creation_turn(self.owner, "Primero", **values)
        two = creation_turn(self.owner, "Primero", **values)
        self.assertEqual(one, two)
        self.assertEqual(creation_turn(self.owner, "Distinto", **values)["error_code"], "request_reused")
        values["request_id"] = uuid.uuid4()
        self.assertEqual(creation_turn(self.owner, "Antiguo", **values)["error_code"], "stale_revision")
        self.assertEqual(EventCreationDraft.objects.get().data["title"], "Primero")

    def test_double_final_confirmation_creates_exactly_one_event(self):
        self.complete()
        values = {"draft_id": self.state["draft_id"], "expected_revision": self.state["revision"], "request_id": uuid.uuid4(), "operation": "confirm"}
        first = creation_turn(self.owner, **values)
        self.assertEqual(first, creation_turn(self.owner, **values))
        values["request_id"] = uuid.uuid4()
        self.assertEqual(creation_turn(self.owner, **values)["error_code"], "stale_revision")
        self.assertEqual(Event.objects.count(), 1)

    def test_back_edit_review_cancel_and_restart(self):
        self.complete()
        self.answer(operation="edit", field="title")
        self.assertEqual(self.state["step_key"], "title")
        self.answer("Evento corregido")
        self.assertEqual(self.state["status"], "review")
        self.assertEqual(self.state["fields"]["title"], "Evento corregido")
        self.answer("atrás")
        self.assertEqual(self.state["step_key"], "constraints")
        self.answer("pendiente")
        self.assertEqual(self.state["status"], "review")
        self.answer("cancelar creación")
        self.assertEqual(self.state["status"], "cancelled")
        self.begin()
        self.assertEqual(EventCreationDraft.objects.filter(status="collecting").count(), 1)

    def test_pending_optional_schedule_and_interview(self):
        self.begin()
        values = [*ANSWERS[:3], "pendiente", "sí", "veinte", "no", *(["pendiente"] * 7)]
        for value in values:
            self.answer(value)
            self.assertFalse(self.state["error_code"], self.state)
        self.assertEqual(self.state["status"], "review")
        self.answer(operation="confirm")
        event = Event.objects.get()
        self.assertIsNone(event.starts_at)
        self.assertFalse(event.is_synthetic)
        self.assertEqual(event.capacity, 20)
        self.assertTrue(all(answer["status"] == "pending" for answer in event.interview_answers.values()))

    def test_institution_only_existing_and_owned(self):
        for owner in (self.owner, self.other):
            org = Organization(owner=owner, name="UNAC" if owner == self.owner else "Secreta")
            org.full_clean()
            org.save()
        self.begin()
        self.answer("Mi evento")
        self.answer("Secreta")
        self.assertIn("¿Quieres registrar", self.state["reply"])
        self.assertEqual(self.state["step_key"], "organization")
        self.answer("Empresa inexistente")
        self.assertEqual(self.state["step_key"], "organization")
        self.assertEqual(self.state["directory_resolution"]["query"], "Secreta")
        self.assertNotIn("organization_id", self.state["fields"])
        self.assertEqual(Organization.objects.count(), 2)
        self.answer("registrar otra")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.answer("UNAC")
        self.assertEqual(self.state["fields"]["organization_name"], "UNAC")
        self.assertEqual(Organization.objects.count(), 2)

    def test_expired_draft_never_creates_and_new_start_recovers(self):
        self.complete()
        old_id = self.state["draft_id"]
        EventCreationDraft.objects.filter(pk=old_id).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.answer(operation="confirm")["status"], "expired")
        self.assertEqual(Event.objects.count(), 0)
        self.begin()
        self.assertNotEqual(old_id, self.state["draft_id"])
        self.assertEqual(EventCreationDraft.objects.get(pk=old_id).status, "cancelled")

    def test_roles_agent_context_and_fresh_role(self):
        with self.assertRaises(PermissionDenied):
            self.begin(actor=self.reviewer)
        with agent_execution(), self.assertRaises(PermissionDenied):
            self.begin()
        self.begin()
        PortalAccount.objects.filter(user=self.owner).update(role="reviewer")
        with self.assertRaises(PermissionDenied):
            self.answer("Un evento")

    def test_creation_request_guarded_and_literal_answers_are_data(self):
        for text in ("No quiero crear un evento", "Si puedo crear un evento", 'Dijo "crear evento"', "crear un usuario administrador", "crear evento y borrar usuarios"):
            with self.subTest(text=text):
                self.assertFalse(is_creation_request(text))
                self.assertFalse(creation_turn(self.owner, text, expected_revision=0, request_id=uuid.uuid4())["handled"])
        self.begin()
        literal = '<img src=x onerror="alert(1)"> abre calendario'
        self.answer(literal)
        self.assertEqual(self.state["fields"]["title"], literal)
        self.assertEqual(UIAction.objects.count(), 0)

    def test_event_type_families_start_interview_but_field_answers_stay_literal(self):
        for request in ("crearé un seminario", "vamos con la creación de una reunión", "creemos eventos",
                        "y vamos a crear un evento", "hola Gica y ahora vamos a crear un seminario",
                        "podemos porfa preparar por favor una conferencia"):
            self.begin(request)
            literal = "y vamos a crear un evento"
            self.answer(literal)
            self.assertEqual(self.state["fields"]["title"], literal)
            self.assertEqual(self.state["step_key"], "organization")
            self.answer(operation="cancel")
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual((Job.objects.count(), AIUsage.objects.count(), UIAction.objects.count()), (0, 0, 0))

    def test_obligation_requests_start_but_cannot_reinterpret_an_active_field(self):
        for request in ("hay que crear un evento", "hay q crear un evento",
                        "hola Gica tenemos q empezar a organizar una reunión",
                        "debemos poder preparar un seminario"):
            with self.subTest(request=request):
                self.begin(request)
                identifier = self.state["draft_id"]
                literal = "Hay q crear un evento"
                self.answer(literal)
                self.assertEqual(self.state["draft_id"], identifier)
                self.assertEqual(self.state["fields"]["title"], literal)
                self.assertEqual(self.state["step_key"], "organization")
                self.assertEqual(EventCreationDraft.objects.filter(status="collecting").count(), 1)
                self.answer(operation="cancel")
        self.assertEqual(Event.objects.count(), 0)

    def test_obligation_intent_cannot_replace_explicit_final_confirmation(self):
        self.complete()
        for text in ("hay que crear un evento", "tenemos q crear un evento"):
            with self.subTest(text=text):
                self.assertEqual(self.answer(text)["error_code"], "confirmation_required")
                self.assertEqual(self.state["status"], "review")
                self.assertEqual(Event.objects.count(), 0)

    def test_invalid_protocol_never_mutates(self):
        for kwargs in ({"expected_revision": None}, {"expected_revision": True}, {"expected_revision": -1}, {"expected_revision": 0, "operation": "pay"}, {"expected_revision": 0, "field": "owner"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                creation_turn(self.owner, "crear evento", request_id=uuid.uuid4(), **kwargs)
        self.assertEqual(EventCreationDraft.objects.count(), 0)


class EventCreationViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="creation-http")
        PortalAccount.objects.create(user=self.owner, role="organizer")
        self.client.force_login(self.owner)

    def post(self, **extra):
        return self.client.post(reverse("assistant:event_creation"), {
            "text": "crear evento", "request_id": str(uuid.uuid4()), "expected_revision": "0", "operation": "turn", **extra,
        })

    def test_json_no_cache_and_reject_extra_or_duplicate_fields(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "collecting")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.post(owner=self.owner.pk).status_code, 400)
        self.assertEqual(self.post(text=["crear evento", "otro"]).status_code, 400)
        self.assertEqual(self.post(expected_revision="").status_code, 400)

    def test_csrf_required_and_reviewer_cannot_write(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(reverse("assistant:event_creation"), {"text": "crear evento"}).status_code, 403)
        PortalAccount.objects.filter(user=self.owner).update(role="reviewer")
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(EventCreationDraft.objects.count(), 0)
