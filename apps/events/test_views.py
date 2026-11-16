"""Endpoint behavior: scope, CSRF, replay safety and honest queued AI."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_management.testing import configure_test_account
from apps.assistant.models import Message
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan
from .forms import EventForm
from .models import Event
from .services import create_event


@override_settings(OPENAI_API_KEY="test-placeholder-never-used-for-network", AI_DAILY_JOB_LIMIT=50, AI_MAX_PENDING_PER_EVENT=10)
class EventEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="http-owner", password="http-tests-password")
        cls.other = get_user_model().objects.create_user(username="http-other", password="http-tests-password")
        configure_test_account(cls.owner, token_limit=2000000)

    def setUp(self):
        self.event = create_event(actor=self.owner, title="Seminario propio", brief="Objetivos académicos del evento", is_synthetic=True)
        self.foreign = create_event(actor=self.other, title="Evento privado ajeno", brief="Descripción privada ajena", is_synthetic=True)
        self.client.force_login(self.owner)

    def url(self, name, event=None, **kwargs):
        return reverse("events:" + name, kwargs={"event_id": (event or self.event).pk, **kwargs})

    def candidate(self):
        self.event.refresh_from_db()
        return create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)

    def post_generate(self, **extra):
        data = {"brief": "", "expected_revision": self.event.revision, "idempotency_key": str(uuid.uuid4())}
        data.update(extra)
        return self.client.post(self.url("generate"), data)

    def test_anonymous_pages_require_login(self):
        self.client.logout()
        for url in (reverse("events:index"), reverse("events:create"), self.url("detail")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response.url)

    def test_index_and_detail_do_not_disclose_another_event(self):
        response = self.client.get(reverse("events:index"))
        self.assertContains(response, "Seminario propio")
        self.assertNotContains(response, "Evento privado ajeno")
        self.assertEqual(self.client.get(self.url("detail", self.foreign)).status_code, 404)

    def test_detail_exposes_context_and_distinct_request_keys(self):
        response = self.client.get(self.url("detail"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["plan"])
        self.assertTrue(response.context["ai_configured"])
        self.assertNotEqual(response.context["generate_key"], response.context["chat_key"])
        uuid.UUID(response.context["generate_key"])

    def test_first_candidate_detail_reports_additions_without_active_plan(self):
        candidate = self.candidate()
        response = self.client.get(self.url("detail"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["candidate"].pk, candidate.pk)
        self.assertIsNone(response.context["plan"])
        self.assertEqual(response.context["impact"]["sessions"]["added"], ["s1", "s2"])
        self.assertEqual(response.context["impact"]["tasks"]["added"], ["t1", "t2"])

    def test_event_creation_uses_selected_timezone_and_server_actor(self):
        response = self.client.post(reverse("events:create"), {"title": "Evento en Nueva York", "brief": "Seminario virtual", "starts_at": "2026-11-14T09:00", "timezone": "America/New_York", "capacity": 50, "owner": self.other.pk})
        event = Event.objects.get(title="Evento en Nueva York")
        self.assertRedirects(response, self.url("detail", event))
        self.assertEqual(event.owner_id, self.owner.pk)
        self.assertEqual(event.starts_at.hour, 14)  # UTC in November, not the server's Lima zone.

    def test_invalid_creation_retains_input_and_creates_nothing(self):
        before = Event.objects.count()
        response = self.client.post(reverse("events:create"), {"title": "Conservar este título", "brief": "Descripción conservada", "starts_at": "2026-03-08T02:30", "timezone": "America/New_York", "capacity": 50})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conservar este título")
        self.assertTrue(response.context["form"].errors["starts_at"])
        self.assertEqual(Event.objects.count(), before)

    def test_generate_queues_real_work_and_deduplicates(self):
        key = str(uuid.uuid4())
        first = self.post_generate(idempotency_key=key)
        second = self.post_generate(idempotency_key=key)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        current_job = Job.objects.get(event=self.event)
        self.assertEqual(current_job.kind, Job.Kind.PLAN)
        self.assertEqual(current_job.status, Job.Status.QUEUED)
        self.assertEqual(current_job.prompt, "Prepara una propuesta inicial con el contexto de este evento.")
        self.assertFalse(PlanCandidate.objects.exists())

    def test_openai_pilot_rejects_non_synthetic_event_without_jobs_or_messages(self):
        Event.objects.filter(pk=self.event.pk).update(is_synthetic=False)
        response = self.client.post(self.url("generate"), {
            "brief": "Prepara una agenda", "idempotency_key": str(uuid.uuid4()),
        }, HTTP_HX_REQUEST="true")
        self.assertContains(response, "sólo permite eventos de demostración con datos ficticios")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_generate_rejects_stale_displayed_event(self):
        self.post_generate(expected_revision=999)
        self.assertFalse(Job.objects.exists())

    @override_settings(OPENAI_API_KEY="")
    def test_missing_provider_never_creates_fake_plan_or_job(self):
        response = self.client.post(self.url("generate"), {"brief": "Prepara una agenda", "idempotency_key": str(uuid.uuid4())}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "aún no está configurada")
        self.assertFalse(Job.objects.exists())
        self.assertFalse(PlanCandidate.objects.exists())

    def test_htmx_generate_returns_status_and_fresh_form_key(self):
        response = self.client.post(self.url("generate"), {"brief": "", "idempotency_key": str(uuid.uuid4())}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "En cola")
        self.assertContains(response, 'id="generate-request-key"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')

    def test_chat_retry_stores_one_user_message_without_response_job_relation(self):
        data = {"message": "¿Qué falta preparar?", "idempotency_key": str(uuid.uuid4())}
        self.client.post(self.url("chat"), data)
        self.client.post(self.url("chat"), data)
        current_job = Job.objects.get(event=self.event)
        message = Message.objects.get(event=self.event, role="user")
        self.assertEqual(message.request_key, str(current_job.pk))
        self.assertIsNone(message.job_id)
        self.assertFalse(Message.objects.filter(role="assistant").exists())

    def test_chat_conflicting_retry_does_not_add_content(self):
        key = str(uuid.uuid4())
        self.client.post(self.url("chat"), {"message": "Primera pregunta", "idempotency_key": key})
        self.client.post(self.url("chat"), {"message": "Contenido distinto", "idempotency_key": key})
        self.assertEqual(Job.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)

    @override_settings(AI_DAILY_JOB_LIMIT=0)
    def test_failed_enqueue_does_not_store_orphan_user_message(self):
        self.client.post(self.url("chat"), {"message": "Pregunta válida", "idempotency_key": str(uuid.uuid4())})
        self.assertFalse(Message.objects.exists())
        self.assertFalse(Job.objects.exists())

    def test_message_failure_rolls_back_job_in_same_transaction(self):
        with patch("apps.events.views.Message.objects.get_or_create", side_effect=ValidationError("No se pudo guardar el mensaje.")):
            self.client.post(self.url("chat"), {"message": "Pregunta válida", "idempotency_key": str(uuid.uuid4())})
        self.assertFalse(Job.objects.exists())

    def test_chat_markup_escapes_untrusted_message(self):
        response = self.client.post(self.url("chat"), {"message": "<script>alert(1)</script>", "idempotency_key": str(uuid.uuid4())}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, 'id="chat-messages"')
        self.assertContains(response, 'id="chat-request-key"')

    def test_nested_foreign_resources_return_404(self):
        foreign_candidate = create_candidate(event=self.foreign, actor=self.other, payload=valid_plan(), base_revision=1)
        foreign_job = Job.objects.create(event=self.foreign, actor=self.other, kind="chat", prompt="Pregunta privada", base_revision=1, request_hash="f" * 64, idempotency_key="foreign")
        operations = [
            ("generate", {"idempotency_key": str(uuid.uuid4())}, self.foreign, {}),
            ("chat", {"message": "Pregunta válida", "idempotency_key": str(uuid.uuid4())}, self.foreign, {}),
            ("approve", {}, self.event, {"candidate_id": foreign_candidate.pk}),
            ("reject", {}, self.event, {"candidate_id": foreign_candidate.pk}),
            ("cancel", {}, self.event, {"job_id": foreign_job.pk}),
        ]
        for name, data, event, kwargs in operations:
            with self.subTest(name=name):
                self.assertEqual(self.client.post(self.url(name, event, **kwargs), data).status_code, 404)
        self.assertEqual(self.client.get(self.url("job", job_id=foreign_job.pk)).status_code, 404)

    def test_htmx_cancel_finished_job_keeps_widget_and_result_link(self):
        current_job = Job.objects.create(event=self.event, actor=self.owner, kind="chat", prompt="Pregunta", base_revision=1, request_hash="c" * 64, idempotency_key="cancel-finished", status=Job.Status.SUCCEEDED)
        response = self.client.post(self.url("cancel", job_id=current_job.pk), HTTP_HX_REQUEST="true")
        self.assertContains(response, f'id="job-{current_job.pk}"')
        self.assertContains(response, f'id="job-action-{current_job.pk}"')
        self.assertContains(response, "Trabajo completado")
        self.assertContains(response, "Ver respuesta")
        self.assertContains(response, f'href="{self.url("detail")}?result={current_job.pk}#agent-title"')
        self.assertContains(response, "Este trabajo ya terminó y no puede cancelarse.")
        current_job.refresh_from_db()
        self.assertEqual(current_job.status, Job.Status.SUCCEEDED)

    def test_htmx_cancel_race_refreshes_finished_job_and_escapes_error(self):
        current_job = Job.objects.create(event=self.event, actor=self.owner, kind="chat", prompt="Pregunta", base_revision=1, request_hash="d" * 64, idempotency_key="cancel-race")

        def finish_before_cancel(**_kwargs):
            # The view already read a queued snapshot; the worker finishes now.
            Job.objects.filter(pk=current_job.pk).update(status=Job.Status.SUCCEEDED)
            raise ValidationError("El trabajo terminó: <script>alert(1)</script>")

        with patch("apps.events.views.cancel_job", side_effect=finish_before_cancel):
            response = self.client.post(self.url("cancel", job_id=current_job.pk), HTTP_HX_REQUEST="true")
        self.assertContains(response, f'id="job-{current_job.pk}"')
        self.assertContains(response, "Trabajo completado")
        self.assertContains(response, "Ver respuesta")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, ">Cancelar</button>")

    def test_all_mutations_require_post(self):
        candidate = self.candidate()
        current_job = Job.objects.create(event=self.event, actor=self.owner, kind="chat", prompt="Pregunta", base_revision=1, request_hash="a" * 64, idempotency_key="method-test")
        for name, kwargs in [("generate", {}), ("chat", {}), ("approve", {"candidate_id": candidate.pk}), ("reject", {"candidate_id": candidate.pk}), ("cancel", {"job_id": current_job.pk})]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(self.url(name, **kwargs)).status_code, 405)

    def test_csrf_is_required_for_authenticated_mutations(self):
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url("generate"), {"brief": "Agenda válida", "idempotency_key": str(uuid.uuid4())}).status_code, 403)
        secured.get(self.url("detail"))
        token = secured.cookies["csrftoken"].value
        response = secured.post(self.url("generate"), {"brief": "Agenda válida", "idempotency_key": str(uuid.uuid4()), "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Job.objects.count(), 1)

    def test_approval_requires_snapshot_of_exact_candidate(self):
        candidate = self.candidate()
        response = self.client.post(self.url("approve", candidate_id=candidate.pk), {"expected_revision": 999, "expected_plan": ""})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanRevision.objects.exists())
        response = self.client.post(self.url("approve", candidate_id=candidate.pk), {"expected_revision": candidate.base_revision, "expected_plan": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PlanRevision.objects.count(), 1)

    def test_approval_http_retry_returns_history_without_reactivation(self):
        first = self.candidate()
        payload = {"expected_revision": first.base_revision, "expected_plan": ""}
        self.client.post(self.url("approve", candidate_id=first.pk), payload)
        second = self.candidate()
        active = approve_candidate(candidate_id=second.pk, actor=self.owner)
        self.client.post(self.url("approve", candidate_id=first.pk), payload)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, active.pk)
        self.assertEqual(PlanRevision.objects.count(), 2)

    def test_cancel_is_scoped_and_idempotent(self):
        self.post_generate()
        current_job = Job.objects.get()
        url = self.url("cancel", job_id=current_job.pk)
        self.client.post(url)
        self.client.post(url)
        current_job.refresh_from_db()
        self.assertEqual(current_job.status, Job.Status.CANCELLED)

    def test_completed_chat_poll_contains_escaped_response(self):
        self.client.post(self.url("chat"), {"message": "Pregunta válida", "idempotency_key": str(uuid.uuid4())})
        current_job = Job.objects.get()
        current_job.status = Job.Status.SUCCEEDED
        current_job.save(update_fields=["status"])
        Message.objects.create(event=self.event, role="assistant", content="Respuesta <b>sin HTML activo</b>", job=current_job)
        response = self.client.get(self.url("job", job_id=current_job.pk), HTTP_HX_REQUEST="true")
        self.assertContains(response, "Respuesta &lt;b&gt;")
        self.assertContains(response, 'hx-swap-oob="outerHTML" id="chat-messages"')


class EventFormTimezoneTests(TestCase):
    def test_ambiguous_wall_clock_requires_clarification(self):
        form = EventForm({"title": "Evento", "brief": "Seminario virtual", "starts_at": "2026-11-01T01:30", "timezone": "America/New_York", "capacity": 50})
        self.assertFalse(form.is_valid())
        self.assertIn("starts_at", form.errors)
