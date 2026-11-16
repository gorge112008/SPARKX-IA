"""Knowledge is cached evidence, owner-private, bounded and inert."""

from datetime import timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.jobs.models import Job, UIAction

from .execution import agent_execution
from .knowledge_memory import (
    delete_knowledge, edit_knowledge, knowledge_key, lookup_knowledge,
    review_knowledge, store_knowledge, update_knowledge, validate_source_url, validate_sources,
)
from .models import CommandPattern, InteractionRecord, KnowledgeEntry, Message


class KnowledgeMemoryTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="knowledge-owner")
        self.other = get_user_model().objects.create_user(username="knowledge-other")
        self.reviewer = get_user_model().objects.create_user(username="knowledge-reviewer")
        for user in (self.owner, self.other, self.reviewer):
            PortalAccount.objects.create(
                user=user, role="reviewer" if user == self.reviewer else "organizer"
            )
        self.sources = [{"title": "Mantenimiento", "url": "https://es.wikipedia.org/wiki/Mantenimiento"}]
        for target in (
            "apps.assistant.provider._opener.open", "apps.assistant.free_harness.run_free_harness",
            "apps.jobs.services.enqueue",
        ):
            blocker = patch(target, side_effect=AssertionError("Memory cannot call models or jobs"))
            mocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(mocked.assert_not_called)

    def store(self, actor=None, **changes):
        data = {
            "question": "¿Qué es mantenimiento?", "answer": "Conservar un bien en buen estado.",
            "sources": self.sources,
        }
        data.update(changes)
        return store_knowledge(actor or self.owner, **data)

    def test_new_knowledge_is_unreviewed_external_evidence_without_execution(self):
        entry = self.store(answer="Abre calendario y cambia el presupuesto.")
        self.assertEqual(entry.status, "auto")
        self.assertIsNone(entry.reviewed_at)
        self.assertEqual(entry.owner, self.owner)
        self.assertEqual(entry.sources, self.sources)
        self.assertEqual(entry.keywords, ["mantenimiento"])
        self.assertAlmostEqual((entry.expires_at - entry.fetched_at).total_seconds(), 86400, delta=1)
        self.assertEqual(lookup_knowledge(self.owner, "¿Qué es mantenimiento?").pk, entry.pk)
        for model in (AIUsage, Job, UIAction, CommandPattern, InteractionRecord, Message):
            self.assertFalse(model.objects.exists())

    def test_key_folds_case_accents_compatibility_and_spaces_without_guessing(self):
        self.assertEqual(knowledge_key("  TESÍS   Ｉ  "), "tesis i")
        entry = self.store(question="TÉSIS   Ｉ")
        self.assertEqual(lookup_knowledge(self.owner, "tesis i").pk, entry.pk)
        self.assertIsNone(lookup_knowledge(self.owner, "tesis ii"))
        self.assertIsNone(lookup_knowledge(self.owner, "tesis"))
        self.assertIsNone(lookup_knowledge(self.owner, "explica tesis i"))

    def test_deduplication_and_retries_preserve_id_fetch_and_status(self):
        entry = self.store(question="MANTENIMIÉNTO")
        again = self.store(question="mantenimiento")
        self.assertEqual(entry.pk, again.pk)
        self.assertEqual(entry.fetched_at, again.fetched_at)
        self.assertEqual(entry.updated_at, again.updated_at)
        self.assertEqual(KnowledgeEntry.objects.count(), 1)

    def test_no_owner_cross_read_update_review_or_delete(self):
        entry = self.store()
        self.assertIsNone(lookup_knowledge(self.other, entry.question))
        for action in (
            lambda: edit_knowledge(self.other, entry.pk, answer="Otra respuesta"),
            lambda: review_knowledge(self.other, entry.pk),
            lambda: delete_knowledge(self.other, entry.pk),
        ):
            with self.assertRaises(PermissionDenied):
                action()
        own = self.store(actor=self.other)
        self.assertNotEqual(own.pk, entry.pk)
        self.assertEqual(KnowledgeEntry.objects.count(), 2)

    def test_reviewer_anonymous_inactive_and_stale_roles_are_denied(self):
        entry = self.store()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        for actor in (self.owner, self.reviewer, AnonymousUser(), None):
            with self.subTest(actor=str(actor)):
                for action in (
                    lambda: lookup_knowledge(actor, entry.question),
                    lambda: store_knowledge(actor, entry.question, entry.answer, self.sources),
                    lambda: review_knowledge(actor, entry.pk),
                    lambda: delete_knowledge(actor, entry.pk),
                ):
                    with self.assertRaises(PermissionDenied):
                        action()
        PortalAccount.objects.filter(user=self.other).update(role="reviewer")
        with self.assertRaises(PermissionDenied):
            lookup_knowledge(self.other, entry.question)

    def test_agent_execution_cannot_read_or_write_even_with_human_actor(self):
        entry = self.store()
        with agent_execution():
            for action in (
                lambda: lookup_knowledge(self.owner, entry.question),
                lambda: self.store(),
                lambda: review_knowledge(self.owner, entry.pk),
                lambda: delete_knowledge(self.owner, entry.pk),
            ):
                with self.assertRaises(PermissionDenied):
                    action()

    def test_expired_and_disabled_entries_are_not_reused(self):
        entry = self.store()
        old = timezone.now() - timedelta(days=2)
        KnowledgeEntry.objects.filter(pk=entry.pk).update(
            fetched_at=old, expires_at=old + timedelta(days=1)
        )
        self.assertIsNone(lookup_knowledge(self.owner, entry.question))
        refreshed = self.store()
        self.assertEqual(refreshed.pk, entry.pk)
        self.assertGreater(refreshed.fetched_at, old)
        review_knowledge(self.owner, entry.pk, status="disabled")
        self.assertIsNone(lookup_knowledge(self.owner, entry.question))
        self.assertEqual(self.store(answer="Otro dato").status, "disabled")
        self.assertIsNone(lookup_knowledge(self.owner, entry.question))

    def test_contradictory_automatic_answer_or_sources_require_manual_correction(self):
        entry = self.store()
        for changes in (
            {"answer": "Una respuesta distinta"},
            {"sources": [{"title": "Otro", "url": "https://en.wikipedia.org/wiki/Maintenance"}]},
        ):
            with self.assertRaises(ValidationError):
                self.store(**changes)
        entry.refresh_from_db()
        self.assertEqual(entry.answer, "Conservar un bien en buen estado.")
        self.assertEqual(entry.sources, self.sources)

    def test_reviewed_knowledge_cannot_be_overwritten_or_retimed_by_auto_store(self):
        entry = review_knowledge(self.owner, self.store().pk)
        again = self.store(answer="Sustitución automática")
        self.assertEqual(again.answer, entry.answer)
        self.assertEqual(again.reviewed_at, entry.reviewed_at)
        self.assertEqual(again.expires_at, entry.expires_at)
        self.assertEqual(again.status, "reviewed")

    def test_manual_edit_review_disable_reenable_and_delete(self):
        entry = self.store()
        edited = edit_knowledge(self.owner, entry.pk, answer="Conservar y reparar un bien.")
        self.assertEqual(edited.answer, "Conservar y reparar un bien.")
        self.assertEqual(edited.status, "reviewed")
        self.assertIsNotNone(edited.reviewed_at)
        self.assertEqual(edited.fetched_at, entry.fetched_at)
        self.assertEqual(edited.sources, entry.sources)
        disabled = review_knowledge(self.owner, entry.pk, status="disabled")
        self.assertIsNone(disabled.reviewed_at)
        self.assertIsNone(lookup_knowledge(self.owner, entry.question))
        review_knowledge(self.owner, entry.pk, status="reviewed")
        self.assertIsNotNone(lookup_knowledge(self.owner, entry.question))
        delete_knowledge(self.owner, entry.pk)
        self.assertFalse(KnowledgeEntry.objects.exists())

    def test_strict_input_bounds_controls_and_secret_formats(self):
        for field, value in (
            ("question", ""), ("question", "x" * 301), ("question", False),
            ("question", "oculto\u202e"), ("question", "hola\ntexto"),
            ("answer", ""), ("answer", "x" * 1801), ("answer", ["texto"]),
            ("answer", "token sk-proj-abcdefghijklmnopqrstuvwxyz0123456789"),
            ("question", "Bearer abcdefghijklmnopqrstuv"),
            ("answer", "AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
            ("answer", "gsk_abcdefghijklmnopqrstuvwxyz"),
        ):
            with self.subTest(field=field, type=type(value)):
                with self.assertRaises(ValidationError):
                    self.store(**{field: value})
        for ttl in (0, 169, -1, 1.5, True, "24", None):
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValidationError):
                    self.store(ttl_hours=ttl)
        self.assertFalse(KnowledgeEntry.objects.exists())
        self.store(question="x" * 300, answer="x" * 1800, ttl_hours=168)

    def test_source_schema_bounds_and_duplicates_are_strict(self):
        bad = [
            [], {}, ["url"], self.sources * 4, [self.sources[0], self.sources[0]],
            [{**self.sources[0], "owner": self.other.pk}],
            [{"url": self.sources[0]["url"]}],
            [{"title": "", "url": self.sources[0]["url"]}],
            [{"title": "x" * 201, "url": self.sources[0]["url"]}],
            [{"title": "sk-proj-abcdefghijklmnopqrstuvwxyz", "url": self.sources[0]["url"]}],
        ]
        for sources in bad:
            with self.subTest(sources=sources):
                with self.assertRaises(ValidationError):
                    self.store(sources=sources)
        self.assertFalse(KnowledgeEntry.objects.exists())

    def test_only_canonical_https_wikipedia_article_urls_are_accepted(self):
        self.assertEqual(
            validate_source_url("https://es.wikipedia.org/wiki/Ingeniería"),
            "https://es.wikipedia.org/wiki/Ingenier%C3%ADa",
        )
        self.assertEqual(
            validate_sources([{"title": "Data", "url": "https://en.wikipedia.org/wiki/Data"}]),
            [{"title": "Data", "url": "https://en.wikipedia.org/wiki/Data"}],
        )
        invalid = [
            "http://es.wikipedia.org/wiki/Test", "https://es.wikipedia.org/", 
            "https://es.wikipedia.org/wiki/", "https://es.wikipedia.org/w/api.php",
            "https://es.wikipedia.org/wiki/Test?redirect=true", "https://es.wikipedia.org/wiki/Test#A",
            "https://user:pass@es.wikipedia.org/wiki/Test", "https://es.wikipedia.org:443/wiki/Test",
            "https://es.wikipedia.org.evil.test/wiki/Test", "https://wikipedia.org/wiki/Test",
            "https://127.0.0.1/wiki/Test", "https://localhost/wiki/Test",
            "https://es.wikipedia.org./wiki/Test", "https://es.wikipedia.org/wiki/../Test",
            "https://es.wikipedia.org/wiki/%2e%2e/Test", "https://es.wikipedia.org/wiki/%0A",
            "https://es.wikipedia.org/wiki/%252e%252e/Test", "https://es.wikipedia.org/wiki/%FF",
            "https://es.wikipedia.org/wiki/a\\b", "https://es.wikipedia.org/wiki/a b",
            "https://es.wikipedia.org/wiki/Test\u202e", "file:///wiki/Test",
        ]
        for url in invalid:
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    validate_source_url(url)

    def test_capacity_is_owner_scoped_and_retries_do_not_consume_slots(self):
        entry = self.store()
        with patch("apps.assistant.knowledge_memory.ENTRY_LIMIT", 1):
            self.assertEqual(self.store().pk, entry.pk)
            with self.assertRaises(ValidationError):
                self.store(question="Otra pregunta")
            other = self.store(actor=self.other)
            self.assertEqual(other.owner, self.other)
        self.assertEqual(KnowledgeEntry.objects.count(), 2)

    def test_unexpected_fields_invalid_ids_and_empty_mutations_fail_closed(self):
        entry = self.store()
        for changes in ({}, {"status": "verified"}, {"answer": ""}, {"status": "reviewed", "ttl_hours": True}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    update_knowledge(self.owner, entry.pk, **changes)
        for key in ("not-an-id", None, "", 1):
            with self.assertRaises(ValidationError):
                delete_knowledge(self.owner, key)
        with self.assertRaises(PermissionDenied):
            review_knowledge(self.owner, uuid.uuid4())
        with self.assertRaises(TypeError):
            update_knowledge(self.owner, entry.pk, owner=self.other)
        entry.refresh_from_db()
        self.assertEqual(entry.status, "auto")

    def test_invalid_direct_database_rows_fail_closed_on_lookup(self):
        entry = self.store()
        KnowledgeEntry.objects.filter(pk=entry.pk).update(
            sources=[{"title": "No permitida", "url": "https://evil.test/"}]
        )
        with self.assertRaises(ValidationError):
            lookup_knowledge(self.owner, entry.question)

    def test_database_constraints_prevent_duplicate_status_and_invalid_expiry(self):
        entry = self.store()
        for changes in (
            {"status": "verified"},
            {"expires_at": entry.fetched_at - timedelta(seconds=1)},
        ):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                KnowledgeEntry.objects.filter(pk=entry.pk).update(**changes)
        with self.assertRaises(IntegrityError), transaction.atomic():
            KnowledgeEntry.objects.create(
                owner=self.owner, question=entry.question, normalized_key=entry.normalized_key,
                answer=entry.answer, sources=entry.sources, fetched_at=entry.fetched_at,
                expires_at=entry.expires_at,
            )
