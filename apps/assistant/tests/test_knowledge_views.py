"""Private reference UI: authority, CSRF, escaping and non-executing review."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.jobs.models import Job, UIAction

from apps.assistant.execution import agent_execution
from apps.assistant.knowledge_memory import store_knowledge
from apps.assistant.models import CommandPattern, KnowledgeEntry, LearnedAlias, Message, PublicLookupAttempt


class KnowledgeViewTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="reference-owner")
        self.other = users.objects.create_user(username="reference-other")
        self.reviewer = users.objects.create_user(username="reference-reviewer")
        for user in (self.owner, self.other, self.reviewer):
            PortalAccount.objects.create(
                user=user, role="reviewer" if user == self.reviewer else "organizer",
            )
        self.library_url = reverse("assistant:knowledge")
        self.query_url = reverse("assistant:knowledge_query")
        self.clear_url = reverse("assistant:lookup_history_clear")
        self.login(self.owner)
        for target in (
            "apps.assistant.provider._opener.open",
            "apps.assistant.public_knowledge.build_opener",
            "apps.jobs.services.enqueue",
        ):
            blocked = patch(target, side_effect=AssertionError("View QA must not use external services"))
            mocked = blocked.start()
            self.addCleanup(blocked.stop)
            self.addCleanup(mocked.assert_not_called)

    def login(self, actor, client=None):
        client = client or self.client
        client.force_login(actor)
        session = client.session
        session["portal_auth_version"] = 1
        session.save()
        return client

    def entry(self, question="mantenimiento predictivo", answer="Una referencia pública.", owner=None, **values):
        return store_knowledge(
            owner or self.owner, question, answer,
            values.pop("sources", [{"title": "Mantenimiento", "url": "https://es.wikipedia.org/wiki/Mantenimiento"}]),
            **values,
        )

    def alias(self, *, owner=None, label="tablero", intent="calendar_open"):
        return LearnedAlias.objects.create(
            owner=owner or self.owner, alias=label, normalized_key=label, intent=intent,
        )

    def knowledge_url(self, entry):
        return reverse("assistant:knowledge_change", args=[entry.pk])

    def alias_url(self, alias):
        return reverse("assistant:alias_change", args=[alias.pk])

    def question(self, **values):
        return {"text": "Qué es mantenimiento predictivo", "request_id": str(uuid4()), **values}

    def result(self, **values):
        return {
            "handled": True, "status": "found", "reply": "Una referencia pública.",
            "answer": "Una referencia pública.", "tokens": 0, "origin": "memory", "sources": [
                {"title": "Mantenimiento", "url": "https://es.wikipedia.org/wiki/Mantenimiento"},
            ], **values,
        }

    def assert_no_execution(self):
        for model in (UIAction, AIUsage, Job, CommandPattern, Message):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_login_and_current_session_are_required(self):
        anonymous = Client()
        self.assertRedirects(anonymous.get(self.library_url), reverse("login") + "?next=" + self.library_url)
        response = anonymous.post(self.query_url, self.question())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))
        session = self.client.session
        session["portal_auth_version"] = 999
        session.save()
        self.assertRedirects(self.client.get(self.library_url), reverse("login"))
        self.assert_no_execution()

    def test_library_contains_only_owner_entries_and_aliases_with_private_cache_headers(self):
        self.entry(question="referencia propia")
        self.alias(label="tablero propio")
        self.entry(question="referencia extranjera secreta", owner=self.other)
        self.alias(label="alias extranjero secreto", owner=self.other)
        response = self.client.get(self.library_url)
        self.assertContains(response, "referencia propia")
        self.assertContains(response, "tablero propio")
        self.assertNotContains(response, "referencia extranjera secreta")
        self.assertNotContains(response, "alias extranjero secreto")
        self.assertEqual(response.context["knowledge_count"], 1)
        self.assertEqual(response.context["alias_count"], 1)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
        self.assert_no_execution()

    def test_library_filter_and_pagination_remain_owner_scoped(self):
        for index in range(13):
            self.entry(question=f"referencia propia {index}")
        self.entry(question="referencia extranjera exclusiva", owner=self.other)
        self.alias(label="tablero exacto")
        response = self.client.get(self.library_url)
        self.assertEqual(len(response.context["entries"]), 12)
        self.assertEqual(response.context["page_obj"].paginator.count, 13)
        response = self.client.get(self.library_url, {"page": 2})
        self.assertEqual(len(response.context["entries"]), 1)
        response = self.client.get(self.library_url, {"q": "extranjera"})
        self.assertEqual(len(response.context["entries"]), 0)
        self.assertEqual(len(response.context["aliases"]), 0)
        self.assertNotContains(response, "referencia extranjera exclusiva")
        response = self.client.get(self.library_url, {"q": "tablero exacto", "page": "invalid"})
        self.assertEqual(len(response.context["aliases"]), 1)

    def test_saved_text_and_filter_are_escaped_in_html(self):
        payload = '<script>alert("x")</script>'
        self.entry(question=payload, answer='<img src=x onerror="alert(1)">', sources=[{
            "title": payload, "url": "https://es.wikipedia.org/wiki/Mantenimiento",
        }])
        self.alias(label='<img src=x onerror="alias()">')
        response = self.client.get(self.library_url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, "&lt;img")
        self.assertNotContains(response, payload)
        self.assertNotContains(response, '<img src=x onerror=')
        response = self.client.get(self.library_url, {"q": payload})
        self.assertNotContains(response, payload)
        self.assertContains(response, "&lt;script&gt;")
        self.assert_no_execution()

    def test_query_json_forwards_validated_arguments_and_network_opt_in_without_execution(self):
        data = self.question()
        expected = self.result()
        with patch("apps.assistant.knowledge_views.answer_public_question", return_value=expected) as service:
            response = self.client.post(self.query_url, data, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), expected)
            args, kwargs = service.call_args
            self.assertEqual(args[0].pk, self.owner.pk)
            self.assertEqual(args[1], data["text"])
            self.assertEqual(str(args[2]), data["request_id"])
            self.assertEqual(kwargs, {"context": "", "allow_network": False})
            response = self.client.post(self.query_url, self.question(allow_network="on", context="theme"), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(service.call_args.kwargs, {"context": "theme", "allow_network": True})
        self.assertFalse(KnowledgeEntry.objects.exists())
        self.assertFalse(PublicLookupAttempt.objects.exists())
        self.assert_no_execution()

    def test_query_html_escapes_reference_answer_and_title(self):
        payload = '<script>alert("remote")</script>'
        result = self.result(answer=payload, reply=payload, sources=[{
            "title": '<img src=x onerror="remote()">', "url": "https://es.wikipedia.org/wiki/Mantenimiento",
        }])
        with patch("apps.assistant.knowledge_views.answer_public_question", return_value=result):
            response = self.client.post(self.query_url, self.question())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, "&lt;img")
        self.assertNotContains(response, payload)
        self.assertNotContains(response, '<img src=x onerror=')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assert_no_execution()

    def test_query_rejects_duplicate_fields_invalid_ids_context_and_options_before_service(self):
        cases = (
            self.question(text=["qué es mantenimiento", "qué es otra cosa"]),
            self.question(request_id=[str(uuid4()), str(uuid4())]),
            self.question(context=["", "person_name"]),
            self.question(allow_network=["on", "off"]),
            self.question(allow_network="yes"), self.question(context="administrador"),
            self.question(request_id="not-a-uuid"), self.question(text="a" * 301),
            self.question(text=""), self.question(extra="injected"),
        )
        with patch("apps.assistant.knowledge_views.answer_public_question") as service:
            for data in cases:
                with self.subTest(data=data):
                    response = self.client.post(self.query_url, data, HTTP_ACCEPT="application/json")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["status"], "invalid")
            service.assert_not_called()
        self.assertFalse(KnowledgeEntry.objects.exists())
        self.assert_no_execution()

    def test_query_service_validation_errors_are_presented_without_execution(self):
        with patch("apps.assistant.knowledge_views.answer_public_question", side_effect=ValidationError("No compartas información privada.")):
            response = self.client.post(self.query_url, self.question(), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("privada", response.json()["reply"])
            response = self.client.post(self.query_url, self.question())
            self.assertContains(response, "No compartas información privada.", status_code=400)
        self.assert_no_execution()

    def test_all_post_operations_require_csrf_and_valid_token_allows_query(self):
        entry, alias = self.entry(), self.alias()
        csrf_client = self.login(self.owner, Client(enforce_csrf_checks=True))
        with patch("apps.assistant.knowledge_views.answer_public_question", return_value=self.result()) as service:
            for url, data in (
                (self.query_url, self.question()),
                (self.knowledge_url(entry), {"operation": "delete"}),
                (self.alias_url(alias), {"operation": "delete"}),
                (self.clear_url, {"confirm": "on"}),
            ):
                with self.subTest(url=url):
                    self.assertEqual(csrf_client.post(url, data).status_code, 403)
            service.assert_not_called()
            self.assertTrue(KnowledgeEntry.objects.filter(pk=entry.pk).exists())
            self.assertTrue(LearnedAlias.objects.filter(pk=alias.pk).exists())
            self.assertEqual(csrf_client.get(self.library_url).status_code, 200)
            token = csrf_client.cookies["csrftoken"].value
            response = csrf_client.post(self.query_url, self.question(csrfmiddlewaretoken=token), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 200)
            service.assert_called_once()
        self.assert_no_execution()

    def test_mutations_are_post_only_and_library_is_get_only(self):
        entry, alias = self.entry(), self.alias()
        for url in (self.query_url, self.knowledge_url(entry), self.alias_url(alias), self.clear_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(self.library_url).status_code, 405)
        self.assert_no_execution()

    def test_owner_can_review_disable_reactivate_edit_and_delete_reference(self):
        entry = self.entry()
        for operation, status in (("review", "reviewed"), ("disable", "disabled"), ("activate", "reviewed")):
            with self.subTest(operation=operation):
                self.assertRedirects(self.client.post(self.knowledge_url(entry), {"operation": operation}), self.library_url)
                entry.refresh_from_db()
                self.assertEqual(entry.status, status)
        response = self.client.post(self.knowledge_url(entry), {"operation": "edit", "answer": "Corrección humana."})
        self.assertRedirects(response, self.library_url)
        entry.refresh_from_db()
        self.assertEqual((entry.answer, entry.status), ("Corrección humana.", "reviewed"))
        self.assertIsNotNone(entry.reviewed_at)
        self.assertRedirects(self.client.post(self.knowledge_url(entry), {"operation": "delete"}), self.library_url)
        self.assertFalse(KnowledgeEntry.objects.filter(pk=entry.pk).exists())
        self.assert_no_execution()

    def test_invalid_reference_edit_or_operation_preserves_original(self):
        entry = self.entry()
        for data in (
            {"operation": "edit", "answer": ""}, {"operation": "edit", "answer": "a" * 1801},
            {"operation": "inject"}, {"operation": "edit", "answer": "abc\u200bdef"},
        ):
            with self.subTest(data=data):
                self.assertRedirects(self.client.post(self.knowledge_url(entry), data), self.library_url)
                entry.refresh_from_db()
                self.assertEqual((entry.answer, entry.status), ("Una referencia pública.", "auto"))
        self.assert_no_execution()

    def test_other_owner_cannot_read_through_change_or_mutate_reference_or_alias(self):
        entry, alias = self.entry(owner=self.other), self.alias(owner=self.other)
        for operation in ("review", "disable", "activate", "edit", "delete"):
            with self.subTest(operation=operation):
                response = self.client.post(self.knowledge_url(entry), {"operation": operation, "answer": "Intrusión."})
                self.assertEqual(response.status_code, 404)
        for operation in ("review", "disable", "delete"):
            self.assertEqual(self.client.post(self.alias_url(alias), {"operation": operation}).status_code, 404)
        entry.refresh_from_db()
        alias.refresh_from_db()
        self.assertEqual((entry.status, alias.status), ("auto", "auto"))
        self.assert_no_execution()

    def test_duplicate_mutation_operations_or_invalid_alias_operation_are_rejected(self):
        entry, alias = self.entry(), self.alias()
        for url in (self.knowledge_url(entry), self.alias_url(alias)):
            self.assertEqual(self.client.post(url, {"operation": ["review", "delete"]}).status_code, 400)
        self.assertEqual(self.client.post(self.alias_url(alias), {"operation": "edit"}).status_code, 400)
        self.assertEqual(self.client.post(self.alias_url(alias), {}).status_code, 400)
        self.assertEqual(self.client.post(self.clear_url, {"confirm": ["on", "on"]}).status_code, 400)
        entry.refresh_from_db()
        alias.refresh_from_db()
        self.assertEqual((entry.status, alias.status), ("auto", "auto"))
        self.assert_no_execution()

    def test_alias_review_is_limited_to_five_existing_actions_and_cannot_change_intent(self):
        intents = {"theme_light", "theme_dark", "calendar_open", "directory_open", "events_open"}
        self.assertEqual(set(LearnedAlias.Intent.values), intents)
        for intent in intents:
            alias = self.alias(label="concepto " + intent, intent=intent)
            for operation, expected in (("review", "reviewed"), ("disable", "disabled"), ("review", "reviewed")):
                with self.subTest(intent=intent, operation=operation):
                    response = self.client.post(self.alias_url(alias), {
                        "operation": operation, "intent": "people_search", "owner": self.other.pk,
                        "alias": "administrador",
                    })
                    self.assertRedirects(response, self.library_url)
                    alias.refresh_from_db()
                    self.assertEqual((alias.status, alias.intent, alias.owner_id), (expected, intent, self.owner.pk))
            self.assertRedirects(self.client.post(self.alias_url(alias), {"operation": "delete"}), self.library_url)
            self.assertFalse(LearnedAlias.objects.filter(pk=alias.pk).exists())
        self.assert_no_execution()

    def test_reviewer_and_agent_context_cannot_use_library_query_or_review(self):
        entry, alias = self.entry(), self.alias()
        routes = (
            (self.library_url, "get", {}), (self.query_url, "post", self.question()),
            (self.knowledge_url(entry), "post", {"operation": "delete"}),
            (self.alias_url(alias), "post", {"operation": "delete"}),
            (self.clear_url, "post", {"confirm": "on"}),
        )
        self.login(self.reviewer)
        for url, method, data in routes:
            with self.subTest(role="reviewer", url=url):
                self.assertEqual(getattr(self.client, method)(url, data).status_code, 403)
        self.login(self.owner)
        with agent_execution():
            for url, method, data in routes:
                with self.subTest(role="agent", url=url):
                    self.assertEqual(getattr(self.client, method)(url, data).status_code, 403)
        self.assertTrue(KnowledgeEntry.objects.filter(pk=entry.pk).exists())
        self.assertTrue(LearnedAlias.objects.filter(pk=alias.pk).exists())
        self.assert_no_execution()

    def test_inactive_account_session_cannot_query_or_mutate(self):
        entry, alias = self.entry(), self.alias()
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with patch("apps.assistant.knowledge_views.answer_public_question") as service:
            for url, data in (
                (self.query_url, self.question()),
                (self.knowledge_url(entry), {"operation": "delete"}),
                (self.alias_url(alias), {"operation": "delete"}),
            ):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))
            service.assert_not_called()
        self.assertTrue(KnowledgeEntry.objects.filter(pk=entry.pk).exists())
        self.assertTrue(LearnedAlias.objects.filter(pk=alias.pk).exists())
        self.assert_no_execution()

    def test_history_clear_preserves_today_pending_other_owner_and_saved_knowledge(self):
        entry = self.entry()
        now, yesterday = timezone.now(), timezone.now() - timedelta(days=2)
        records = []
        for owner, finished in ((self.owner, yesterday), (self.owner, now), (self.owner, None), (self.other, yesterday)):
            attempt = PublicLookupAttempt.objects.create(
                owner=owner, request_id=uuid4(), query_hash="0" * 64,
                status="pending" if finished is None else "failed", finished_at=finished,
            )
            if finished != now:
                PublicLookupAttempt.objects.filter(pk=attempt.pk).update(created_at=yesterday)
            records.append(attempt)
        self.assertEqual(self.client.post(self.clear_url).status_code, 400)
        self.assertEqual(PublicLookupAttempt.objects.count(), 4)
        self.assertRedirects(self.client.post(self.clear_url, {"confirm": "on"}), self.library_url)
        self.assertFalse(PublicLookupAttempt.objects.filter(pk=records[0].pk).exists())
        self.assertEqual(set(PublicLookupAttempt.objects.values_list("pk", flat=True)), {record.pk for record in records[1:]})
        self.assertTrue(KnowledgeEntry.objects.filter(pk=entry.pk).exists())
        self.assert_no_execution()
