"""Local guidance with isolated fixtures; no remote calls or plan mutation."""
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.directory.models import EventPerson, Organization, Person
from apps.directory.services import upsert_organization, upsert_person
from apps.events.interview import QUESTIONS
from apps.events.models import Event
from apps.events.services import archive_event, create_event
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan
from apps.assistant.execution import agent_execution
from apps.assistant.guided_event import ACTIONS, STATE_KEY, guided_turn
from apps.assistant.models import EventCreationDraft


class GuidedEventTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="guided-owner")
        self.other = get_user_model().objects.create_user(username="guided-other")
        self.reviewer = get_user_model().objects.create_user(username="guided-reviewer")
        PortalAccount.objects.create(user=self.reviewer, role="reviewer")
        self.org = upsert_organization(actor=self.owner, name="Universidad Nacional del Callao", aliases=["UNAC"])
        self.speaker = upsert_person(actor=self.owner, full_name="Robert Castillo Alva", category="speaker", organization_id=self.org.pk)
        answers = {question.key: {"status": "confirmed", "value": "Dato público confirmado"} for question in QUESTIONS}
        answers.update(modality={"status": "confirmed", "value": "Virtual"}, duration_minutes={"status": "confirmed", "value": "90"})
        self.event = create_event(actor=self.owner, title="Evento guiado", brief="Contexto de organización",
            starts_at=datetime.fromisoformat("2026-11-19T19:30:00-05:00"), scheduled_dates=["2026-11-19"],
            interview_answers=answers, organization_id=self.org.pk, speaker_id=self.speaker.pk)
        self.state = None
        self.client.force_login(self.owner)
        for name in ("apps.assistant.provider._opener.open", "apps.assistant.free_harness.run_compact_harness",
                "apps.jobs.services.enqueue", "apps.assistant.compact_planning.enqueue_compact"):
            blocker = patch(name, side_effect=AssertionError("A guide cannot dispatch a model"))
            mock = blocker.start(); self.addCleanup(blocker.stop); self.addCleanup(mock.assert_not_called)

    def turn(self, text="", **changes):
        values = {"event_id": self.event.pk, "expected_revision": 0, "request_id": uuid.uuid4()}
        if self.state and self.state["draft_id"]:
            values.update(draft_id=self.state["draft_id"], expected_revision=self.state["revision"])
        values.update(changes)
        self.state = guided_turn(self.owner, text, **values)
        return self.state

    def approve_plan(self):
        payload = valid_plan()
        for index, session in enumerate(payload["sessions"]):
            session.update(start=f"2026-11-19T{19 if index == 0 else 20}:30:00-05:00", speaker=self.speaker.full_name)
        candidate = create_candidate(event=self.event, actor=self.owner, payload=payload, base_revision=self.event.revision)
        self.plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return self.plan

    def test_registry_before_event_uses_real_forms_without_fabricating_an_event_or_draft(self):
        for text, action, name in (("Registrar una institución", "open_organization_create", "directory:organization_create"),
                ("crear expositor", "open_speaker_create", "directory:person_create")):
            result = guided_turn(self.owner, text, request_id=uuid.uuid4())
            self.assertEqual((result["action"], result["url"]), (action, reverse(name)))
            self.assertEqual(result["event_id"], "")
            self.assertIn("Guardar", result["reply"])
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(EventCreationDraft.objects.count(), 0)

    def test_state_only_preserves_creation_data_and_replay_or_stale_turn_has_no_event_effect(self):
        legacy = {"title": "Título dictado original", "directory_people": [{"id": str(self.speaker.pk), "role": "speaker"}]}
        draft = EventCreationDraft.objects.create(owner=self.owner, event=self.event, status="created", step="", data=legacy,
            expires_at=timezone.now() + timedelta(hours=1))
        request_id = uuid.uuid4()
        first = self.turn("Hola Gica, abre el calendario", request_id=request_id)
        self.assertEqual(first["action"], "open_calendar")
        self.assertEqual(first, guided_turn(self.owner, "Hola Gica, abre el calendario", event_id=self.event.pk, request_id=request_id))
        draft.refresh_from_db()
        self.assertEqual({key: value for key, value in draft.data.items() if key != STATE_KEY}, legacy)
        self.assertEqual(draft.data[STATE_KEY]["v"], 1)
        stale = self.turn("ver agenda", expected_revision=first["revision"] - 1)
        self.assertEqual(stale["status"], "conflict")
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, 1)
        self.assertEqual((Job.objects.count(), AIUsage.objects.count(), PlanRevision.objects.count()), (0, 0, 0))

    def test_missing_date_is_asked_then_prefilled_but_never_saved(self):
        Event.objects.filter(pk=self.event.pk).update(starts_at=None, scheduled_dates=[])
        self.event.refresh_from_db()
        asked = self.turn("prepara mi agenda")
        self.assertEqual(asked["awaiting"], "date")
        self.assertNotIn("action", asked)
        result = self.turn("19 de noviembre de 2026")
        self.assertEqual(result["field_values"], {"scheduled_dates": "19/11/2026"})
        self.assertEqual(result["url"], reverse("events:edit", args=[self.event.pk]))
        self.assertEqual(result["awaiting"], "")
        self.event.refresh_from_db()
        self.assertIsNone(self.event.starts_at)
        self.assertEqual(self.event.scheduled_dates, [])

    def test_missing_duration_normalizes_natural_numbers_before_human_save(self):
        values = deepcopy(self.event.interview_answers)
        values["duration_minutes"] = {"status": "pending", "value": ""}
        Event.objects.filter(pk=self.event.pk).update(interview_answers=values)
        self.event.refresh_from_db()
        self.assertEqual(self.turn("generar propuesta")["awaiting"], "duration_minutes")
        response = self.turn("una hora y media")
        self.assertEqual(response["field_values"], {"duration_minutes": "90"})
        self.event.refresh_from_db()
        self.assertEqual(self.event.interview_answers["duration_minutes"]["status"], "pending")

    def test_status_queries_repeat_the_missing_question_without_filling_or_dispatching(self):
        Event.objects.filter(pk=self.event.pk).update(starts_at=None, scheduled_dates=[])
        self.event.refresh_from_db()
        for text in ("estado", "Gica, ¿qué falta?", "¿Dónde nos quedamos?", "Dime el estado del evento"):
            with self.subTest(text=text):
                result = self.turn(text)
                self.assertEqual((result["status"], result["awaiting"]), ("clarify", "date"))
                self.assertIn("¿Qué día", result["reply"])
                self.assertNotIn("action", result)
                self.assertNotIn("field_values", result)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.starts_at)
        self.assertFalse(Job.objects.exists())

    def test_status_overview_does_not_generate_or_approve_anything(self):
        complete = self.turn("qué falta")
        self.assertEqual((complete["step"], complete["status"]), ("overview", "info"))
        self.assertNotIn("action", complete)
        candidate = create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision)
        pending = self.turn("dónde nos quedamos")
        self.assertIn("pendiente de revisión", pending["reply"])
        self.assertNotIn("action", pending)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, "pending")
        self.approve_plan()
        approved = self.turn("estado")
        self.assertIn("agenda está aprobada", approved["reply"])
        self.assertNotIn("action", approved)
        self.assertEqual(PlanRevision.objects.count(), 1)
        self.assertFalse(Job.objects.exists())

    def test_social_turns_preserve_pending_people_choices_and_interview_data(self):
        self.jorge = upsert_person(actor=self.owner, full_name="Jorge Gayoso Ugas", category="speaker")
        upsert_person(actor=self.owner, full_name="Jorge Otro", category="speaker")
        self.turn("cambiar expositor")
        offered = self.turn("Jorge")
        expected_choices = offered["choices"]
        before = (Person.objects.count(), Organization.objects.count(), deepcopy(self.event.interview_answers))
        for text in ("hola", "buenos días", "muchas gracias", "graccias", "gracias por tu ayuda", "cómo estás"):
            with self.subTest(text=text):
                result = self.turn(text)
                self.assertEqual(result["awaiting"], "speaker")
                self.assertEqual(result["choices"], expected_choices)
                self.assertIn("¿Quién será el expositor?", result["reply"])
                self.assertNotIn("action", result)
                self.assertNotIn("field_values", result)
        draft = EventCreationDraft.objects.get(pk=self.state["draft_id"])
        for field in ("organization", "objective", "duration_minutes", "date", "time"):
            draft.data[STATE_KEY].update(waiting=field, choice_ids=[], step="generate")
            draft.save(update_fields=["data"])
            result = self.turn("Muchas gracias")
            self.assertEqual(result["awaiting"], field)
            self.assertNotIn("action", result)
            self.assertNotIn("field_values", result)
            draft.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual((Person.objects.count(), Organization.objects.count(), self.event.interview_answers), before)
        self.assertEqual(EventPerson.objects.filter(event=self.event).get().person_id, self.speaker.pk)

    def test_partial_speaker_choices_are_owned_bounded_rechecked_and_do_not_assign(self):
        self.jorge = upsert_person(actor=self.owner, full_name="Jorge Gayoso Ugas", category="speaker", organization_id=self.org.pk)
        second = upsert_person(actor=self.owner, full_name="Jorge Otro", category="speaker")
        upsert_person(actor=self.other, full_name="Jorge Ajeno privado", category="speaker")
        self.assertEqual(self.turn("Quiero cambiar al expositor")["awaiting"], "speaker")
        offered = self.turn("Jorge")
        self.assertEqual({item["value"] for item in offered["choices"]}, {str(self.jorge.pk), str(second.pk)})
        self.assertNotIn("Ajeno", str(offered))
        self.assertNotIn("field_values", self.turn("sí"))
        first = offered["choices"][0]
        response = self.turn("1")
        self.assertEqual(response["field_values"], {"speaker_id": first["value"]})
        self.assertEqual(EventPerson.objects.filter(event=self.event, status="planned").get().person_id, self.speaker.pk)

    def test_unknown_speaker_only_opens_normal_registration_form_without_creating_people(self):
        self.turn("cambiar expositor")
        before = Person.objects.count()
        result = self.turn("Jorge Gayoso")
        self.assertEqual(result["action"], "open_speaker_create")
        self.assertEqual(result["field_values"], {"full_name": "Jorge Gayoso", "category": "speaker", "organization": str(self.org.pk)})
        self.assertEqual(Person.objects.count(), before)

    def test_generation_navigation_respects_real_pilot_boundary_without_dispatch(self):
        result = self.turn("Gica, por favor prepara la propuesta de mi evento")
        self.assertEqual(result["action"], "open_generate")
        self.assertIn("acotada", result["reply"])
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_approval_only_opens_exact_current_candidate_and_cannot_apply_it(self):
        candidate = create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision)
        result = self.turn("aprueba la propuesta")
        self.assertEqual(result["action"], "open_approval")
        self.assertEqual(result["candidate_id"], str(candidate.pk))
        self.assertIn("tu clic", result["reply"])
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, "pending")
        self.assertFalse(PlanRevision.objects.exists())
        self.assertEqual(self.turn("no quiero aprobar nada")["status"], "info")
        self.assertFalse(PlanRevision.objects.exists())

    def test_approved_steps_navigate_and_schedule_changes_still_require_human_proposal(self):
        plan = self.approve_plan()
        before = deepcopy(plan.payload)
        for text, action in (("abre mi agenda", "open_agenda"), ("preparación", "open_preparation"),
                ("ajusta el horario", "open_schedule"), ("calendario", "open_calendar")):
            self.assertEqual(self.turn(text)["action"], action)
        plan.refresh_from_db(); self.assertEqual(plan.payload, before)
        self.assertEqual(PlanRevision.objects.count(), 1)
        self.assertEqual(PlanCandidate.objects.count(), 1)

    def test_new_event_revision_resets_pending_question_instead_of_filling_stale_data(self):
        self.turn("cambiar expositor")
        Event.objects.filter(pk=self.event.pk).update(revision=self.event.revision + 1)
        result = self.turn("Jorge Gayoso")
        self.assertEqual(result["status"], "clarify")
        self.assertEqual(result["awaiting"], "")
        self.assertNotIn("action", result)

    def test_owner_role_agent_and_archive_guards_prevent_access(self):
        for actor in (self.other, self.reviewer):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                guided_turn(actor, "abre agenda", event_id=self.event.pk, request_id=uuid.uuid4())
        with agent_execution(), self.assertRaises(PermissionDenied):
            guided_turn(self.owner, "abre calendario", event_id=self.event.pk, request_id=uuid.uuid4())
        archive_event(actor=self.owner, event_id=self.event.pk, expected_revision=self.event.revision)
        with self.assertRaises(PermissionDenied):
            self.turn("abre calendario")

    def test_corrupt_private_state_is_replaced_without_injecting_a_route_or_resetting_legacy_fields(self):
        draft = EventCreationDraft.objects.create(owner=self.owner, event=self.event, status="created", step="",
            data={"title": "Texto original", STATE_KEY: {"v": 1, "step": {}, "waiting": [], "choice_ids": [], "event_revision": 1}},
            expires_at=timezone.now() + timedelta(hours=1))
        result = self.turn("calendario")
        self.assertEqual(result["action"], "open_calendar")
        draft.refresh_from_db()
        self.assertEqual(draft.data["title"], "Texto original")
        self.assertEqual(draft.data[STATE_KEY]["step"], "calendar")

    def test_uncreated_draft_cannot_be_rebound_to_an_existing_event(self):
        draft = EventCreationDraft.objects.create(owner=self.owner, expires_at=timezone.now() + timedelta(hours=1))
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.turn("calendario", draft_id=draft.pk, expected_revision=draft.revision)
        self.assertFalse(EventCreationDraft.objects.filter(event=self.event).exists())

    def test_guide_without_event_or_intent_never_captures_or_invalidates_normal_creation(self):
        draft = EventCreationDraft.objects.create(owner=self.owner, data={"title": "Mi borrador"}, step="organization",
            expires_at=timezone.now() + timedelta(hours=1))
        before = (draft.revision, draft.last_request_id, deepcopy(draft.data), draft.status)
        for values in ({}, {"draft_id": draft.pk, "expected_revision": draft.revision}):
            result = guided_turn(self.owner, "hola", request_id=uuid.uuid4(), **values)
            self.assertFalse(result["handled"])
            self.assertNotIn("action", result)
        draft.refresh_from_db()
        self.assertEqual((draft.revision, draft.last_request_id, draft.data, draft.status), before)
        self.assertEqual(EventCreationDraft.objects.count(), 1)

    def test_http_endpoint_only_accepts_guide_fields_and_never_accepts_action_or_selector(self):
        url = reverse("assistant:event_creation")
        base = {"operation": "guide", "text": "calendario", "event_id": str(self.event.pk), "request_id": str(uuid.uuid4()), "expected_revision": 0}
        result = self.client.post(url, base)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["action"], "open_calendar")
        for changed in ({"url": "/admin/"}, {"action": "save"}, {"field": "title"}):
            self.assertEqual(self.client.post(url, base | changed).status_code, 400)
        self.assertEqual(self.client.post(url, base | {"event_id": str(uuid.uuid4())}).status_code, 404)
        self.assertTrue(all(action.startswith("open_") for action in ACTIONS))
