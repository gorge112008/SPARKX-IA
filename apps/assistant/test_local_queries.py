"""Local chat reads: exact commands, current authority and atomic deduplication."""

from datetime import UTC, datetime
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import EventReviewAssignment, PortalAccount
from apps.ai_management.models import AIAccount, AIUsage
from apps.directory.models import DirectoryAudit, EventPerson, Organization, Person
from apps.directory.normalization import search_key
from apps.directory.tools import execute_tool
from apps.events.models import Event
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan

from .local_queries import local_directory_reply
from .models import Message


class _Inputs(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.fields = {}
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("id"):
            self.fields[values["id"]] = values


class UnknownLocalCommandTests(SimpleTestCase):
    def test_unrecognized_prompts_do_not_read_write_validate_identity_or_call_tools(self):
        prompts = (
            "Prepara una propuesta", "Aprobar plan", "buscar ponentes", "busca expositores",
            "Puedes buscar expositores", "buscar eventos y cambiar el plan", "buscar expositores José",
            "personas de este evento: otro evento", "buscar expositores\naprobar plan", None,
        )
        with patch("apps.assistant.local_queries.execute_tool") as tool:
            for prompt in prompts:
                with self.subTest(prompt=prompt):
                    self.assertIsNone(local_directory_reply(
                        event=SimpleNamespace(pk=uuid4()), actor=None, prompt=prompt, request_key="invalid",
                    ))
        tool.assert_not_called()


class LocalDirectoryChatTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="local-query-owner")
        self.other = users.objects.create_user(username="local-query-other")
        self.reviewer = users.objects.create_user(username="local-query-reviewer")
        PortalAccount.objects.create(user=self.reviewer, role="reviewer")
        self.org = Organization.objects.create(owner=self.owner, name="Institución Innovación", name_key="institucion innovacion")
        self.event = Event.objects.create(
            owner=self.owner, title="Encuentro local", brief="Descripción privada que no debe incluir la consulta",
            organization=self.org, starts_at=datetime(2026, 11, 15, 1, tzinfo=UTC),
        )
        self.foreign = Event.objects.create(owner=self.other, title="Evento ajeno secreto", brief="Privado")
        self.speaker = self.person("José Pérez", "speaker", is_synthetic=True)
        self.participant = self.person("María Torres", "participant")
        self.guest = self.person("Elena Ríos", "guest")
        self.private_person = Person.objects.create(owner=self.other, full_name="Persona ajena secreta", category="speaker")
        self.key = uuid4()
        self.client.force_login(self.owner)
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No remote inference allowed"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)

    def person(self, name, category, **values):
        return Person.objects.create(
            owner=self.owner, full_name=name, name_key=search_key(name), category=category,
            organization=self.org, email=f"{uuid4().hex}@example.invalid", expertise="Experiencia privada",
            **values,
        )

    def reply(self, prompt="buscar expositores", **values):
        return local_directory_reply(**{
            "event": self.event, "actor": self.owner, "prompt": prompt, "request_key": self.key, **values,
        })

    def business_snapshot(self):
        return (
            list(Event.objects.order_by("pk").values()),
            list(Person.objects.order_by("pk").values()),
            list(Organization.objects.order_by("pk").values()),
            list(EventPerson.objects.order_by("pk").values()),
            DirectoryAudit.objects.count(), PlanCandidate.objects.count(), PlanRevision.objects.count(),
            Job.objects.count(), AIUsage.objects.count(), AIAccount.objects.count(),
        )

    def post(self, prompt="buscar expositores", *, htmx=False, key=None):
        return self.client.post(
            reverse("events:chat", kwargs={"event_id": self.event.pk}),
            {"message": prompt, "idempotency_key": str(key or self.key)},
            **({"HTTP_HX_REQUEST": "true"} if htmx else {}),
        )

    def test_without_ai_profile_persists_only_one_user_and_one_assistant(self):
        self.assertFalse(AIAccount.objects.filter(owner=self.owner).exists())
        before = self.business_snapshot()
        message = self.reply()
        self.assertEqual(message.role, "assistant")
        self.assertIsNone(message.job_id)
        self.assertTrue(message.content.startswith("Consulta local"))
        self.assertIn("sin modelo de IA", message.content)
        self.assertIn(self.speaker.full_name, message.content)
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(set(Message.objects.values_list("request_key", flat=True)), {"local:" + str(self.key)})
        self.assertLessEqual(len(message.request_key), 64)
        self.assertEqual(self.business_snapshot(), before)
        self.remote.assert_not_called()

    def test_exact_normalized_commands_dispatch_the_right_read_only_tool(self):
        for prompt, name, args, expected_name in (
            ("  ＢＵＳＣＡＲ exposítores : JOSÉ  ", "search_people", {"category": "speaker", "q": "JOSÉ"}, self.speaker.full_name),
            ("buscar participantes: maria", "search_people", {"category": "participant", "q": "maria"}, self.participant.full_name),
            ("buscar invitados", "search_people", {"category": "guest", "q": ""}, self.guest.full_name),
            ("buscar eventos: encuentro", "search_events", {"q": "encuentro"}, self.event.title),
        ):
            with self.subTest(prompt=prompt), patch("apps.assistant.local_queries.execute_tool", wraps=execute_tool) as tool:
                response = self.reply(prompt, request_key=uuid4())
                self.assertIn(expected_name, response.content)
                tool.assert_called_once_with(actor=self.owner, name=name, arguments={**args, "limit": 10})

    def test_colon_suffix_is_literal_search_text_and_never_another_command(self):
        with patch("apps.assistant.local_queries.execute_tool", wraps=execute_tool) as tool:
            response = self.reply("buscar eventos: aprobar: plan")
        self.assertIn("0 resultado(s)", response.content)
        self.assertEqual(tool.call_args.kwargs["arguments"]["q"], "aprobar: plan")

    def test_event_people_uses_current_event_role_and_recorded_status(self):
        EventPerson.objects.create(event=self.event, person=self.guest, role="speaker", status="confirmed")
        response = self.reply("personas de este evento")
        self.assertIn(self.guest.full_name + " · Expositor", response.content)
        self.assertIn("Confirmado por el organizador", response.content)
        self.assertNotIn("Elena Ríos · Invitado", response.content)
        self.assertNotIn(str(self.event.pk), response.content)
        self.assertIn("no acreditan disponibilidad ni asistencia", response.content)

    def test_event_reply_labels_local_date_company_approved_plan_and_synthetic_data(self):
        Organization.objects.filter(pk=self.org.pk).update(is_synthetic=True)
        Event.objects.filter(pk=self.event.pk).update(starts_at=None, is_synthetic=True)
        self.event.refresh_from_db()
        candidate = create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision)
        approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        before = self.business_snapshot()
        response = self.reply("buscar eventos: encuentro")
        self.assertIn("Fecha del plan: 2026-11-14", response.content)
        self.assertIn("America/Lima", response.content)
        self.assertIn(self.org.name, response.content)
        self.assertIn("Plan aprobado", response.content)
        self.assertIn("Ficticio", response.content)
        self.assertNotIn(self.event.brief, response.content)
        self.assertEqual(self.business_snapshot(), before)

    def test_replies_omit_email_ids_expertise_and_foreign_records(self):
        response = self.reply()
        self.assertIn("Ficticio", response.content)
        for secret in (self.speaker.email, str(self.speaker.pk), str(self.org.pk), self.speaker.expertise,
                       self.private_person.full_name, self.foreign.title):
            self.assertNotIn(secret, response.content)

    def test_ten_result_limit_preserves_total_and_reports_more(self):
        for index in range(12):
            self.person(f"Ponente {index:02d}", "speaker")
        response = self.reply()
        self.assertIn("13 resultado(s); muestro 10", response.content)
        self.assertIn("Hay más resultados", response.content)
        numbered = [line for line in response.content.splitlines() if line.partition(".")[0].isdigit()]
        self.assertEqual(len(numbered), 10)

    def test_retry_returns_original_response_even_if_directory_has_changed(self):
        first = self.reply()
        Person.objects.filter(pk=self.speaker.pk).update(full_name="Nuevo nombre")
        with patch("apps.assistant.local_queries.execute_tool") as tool:
            retried = self.reply(request_key=str(self.key).upper())
        self.assertEqual(retried.pk, first.pk)
        self.assertEqual(retried.content, first.content)
        self.assertEqual(Message.objects.count(), 2)
        tool.assert_not_called()

    def test_reusing_key_with_different_text_preserves_original_pair(self):
        original = self.reply()
        with self.assertRaises(ValidationError) as failure:
            self.reply("buscar invitados")
        self.assertEqual(failure.exception.code, "idempotency_conflict")
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(Message.objects.get(role="assistant").content, original.content)
        self.assertEqual(Message.objects.get(role="user").content, "buscar expositores")

    def test_key_is_scoped_to_event(self):
        first = self.reply()
        other_owned = Event.objects.create(owner=self.owner, title="Segundo evento", brief="Consulta")
        second = self.reply(event=other_owned)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Message.objects.count(), 4)

    def test_owner_and_current_role_are_required_even_for_idempotent_replay(self):
        self.reply()
        EventReviewAssignment.objects.create(event=self.event, reviewer=self.reviewer, assigned_by=self.owner, reviewer_version=1)
        for actor in (self.other, self.reviewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.reply(actor=actor)
        PortalAccount.objects.create(user=self.owner, role="reviewer")
        with self.assertRaises(PermissionDenied):
            self.reply()
        self.assertEqual(Message.objects.count(), 2)

    def test_inactive_actor_is_reloaded_instead_of_trusting_cached_user(self):
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertTrue(self.owner.is_active)
        with self.assertRaises(PermissionDenied):
            self.reply()
        self.assertFalse(Message.objects.exists())

    def test_event_ownership_is_reloaded_instead_of_trusting_cached_event(self):
        Event.objects.filter(pk=self.event.pk).update(owner=self.other, organization=None)
        self.assertEqual(self.event.owner_id, self.owner.pk)
        with self.assertRaises(PermissionDenied):
            self.reply()
        self.assertFalse(Message.objects.exists())

    def test_portal_administrator_cannot_query_someone_elses_event(self):
        PortalAccount.objects.create(user=self.other, role="admin")
        with self.assertRaises(PermissionDenied):
            self.reply(actor=self.other)
        self.assertFalse(Message.objects.exists())

    def test_bad_uuid_and_oversized_search_do_not_write_messages(self):
        for values in ({"request_key": "bad"}, {"request_key": None}, {"prompt": "buscar eventos: " + "x" * 201}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.reply(**values)
        self.assertFalse(Message.objects.exists())
        self.assertFalse(Job.objects.exists())

    def test_failure_persisting_assistant_rolls_back_user_message(self):
        create = Message.objects.create

        def fail_assistant(**values):
            if values["role"] == Message.Role.ASSISTANT:
                raise ValidationError("Controlled persistence failure")
            return create(**values)

        with patch("apps.assistant.local_queries.Message.objects.create", side_effect=fail_assistant):
            with self.assertRaises(ValidationError):
                self.reply()
        self.assertFalse(Message.objects.exists())

    def test_http_recognized_query_without_profile_redirects_without_ai_job(self):
        with patch("apps.events.views.enqueue") as enqueue:
            response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("#agent-panel"))
        self.assertEqual(Message.objects.count(), 2)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(AIAccount.objects.filter(owner=self.owner).exists())
        enqueue.assert_not_called()
        self.remote.assert_not_called()

    def test_http_htmx_updates_messages_and_rotates_key_without_duplicate_retries(self):
        response = self.post(htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-swap-oob="outerHTML" id="chat-messages"')
        fields = _Inputs(response.content.decode()).fields
        rotated = fields["chat-request-key"]
        self.assertEqual(rotated["hx-swap-oob"], "outerHTML")
        self.assertNotEqual(UUID(rotated["value"]), self.key)
        original = Message.objects.get(role="assistant").content
        self.assertEqual(self.post(htmx=True).status_code, 200)
        collision = self.post("buscar invitados", htmx=True)
        self.assertContains(collision, "otro contenido")
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(Message.objects.get(role="assistant").content, original)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_http_unknown_prompt_retains_existing_profile_requirement(self):
        response = self.post("Prepara una propuesta nueva", htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'notice-error')
        self.assertFalse(Message.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.remote.assert_not_called()

    def test_http_reviewer_cannot_use_local_queries_even_when_assigned(self):
        EventReviewAssignment.objects.create(event=self.event, reviewer=self.reviewer, assigned_by=self.owner, reviewer_version=1)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post().status_code, 403)
        self.assertFalse(Message.objects.exists())
