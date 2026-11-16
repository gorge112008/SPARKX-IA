"""Automatic vocabulary stays explicit, owner-private and action-bounded."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.jobs import command_language as language
from apps.jobs.models import Job, UIAction

from .execution import agent_execution
from .learned_aliases import parse_teaching, resolve_alias, try_learn
from .models import CommandPattern, LearnedAlias, Message


class TeachingFrameTests(SimpleTestCase):
    def test_only_complete_deliberate_definitions_are_teaching(self):
        cases = {
            "cuando diga programación, me refiero al calendario": ("programación", "calendario"),
            "Gica, cuando diga tablero me refiero a la lista de eventos.": ("tablero", "lista de eventos"),
            "programación significa abrir calendario": ("programación", "abrir calendario"),
            "cuando diga tablero quiero abrir eventos": ("tablero", "eventos"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_teaching(text), expected)
        for text in (
            "qué significa programación", "¿programación significa calendario?", "programación",
            "no cuando diga tablero me refiero a calendario", "me dijeron que tablero significa calendario",
            '"cuando diga tablero me refiero al calendario"', "cuando\ndiga tablero me refiero a calendario",
            "cuando diga tablero me refiero a", "cuando diga , me refiero a calendario",
            "", None, "a" * 301,
        ):
            with self.subTest(text=text):
                self.assertIsNone(parse_teaching(text))


class LearnedAliasTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="alias-owner")
        self.other = users.objects.create_user(username="alias-other")
        self.reviewer = users.objects.create_user(username="alias-reviewer")
        for user in (self.owner, self.other, self.reviewer):
            PortalAccount.objects.create(
                user=user, role="reviewer" if user == self.reviewer else "organizer",
            )
        for target in ("apps.assistant.provider._opener.open", "apps.jobs.services.enqueue"):
            blocked = patch(target, side_effect=AssertionError("Vocabulary must stay local"))
            mocked = blocked.start()
            self.addCleanup(blocked.stop)
            self.addCleanup(mocked.assert_not_called)

    def learn(self, alias="tablero", target="calendario", actor=None):
        return try_learn(actor or self.owner, f"cuando diga {alias}, me refiero a {target}")

    def assert_no_execution(self):
        for model in (AIUsage, Job, UIAction, Message, CommandPattern):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_explicit_teaching_is_auto_active_without_execution(self):
        entry = self.learn()
        self.assertEqual((entry.alias, entry.normalized_key, entry.intent, entry.status), (
            "tablero", "tablero", "calendar_open", "auto",
        ))
        self.assertIsNone(entry.reviewed_at)
        self.assert_no_execution()

    def test_five_actions_require_existing_canonical_targets(self):
        cases = (
            ("luz solar", "modo claro", "theme_light"),
            ("noche cerrada", "modo oscuro", "theme_dark"),
            ("tablero", "abrir calendario", "calendar_open"),
            ("archivo central", "directorio", "directory_open"),
            ("encuentros", "lista de eventos", "events_open"),
        )
        for alias, target, intent in cases:
            with self.subTest(alias=alias):
                self.learn(alias, target)
                self.assertEqual(resolve_alias(self.owner, alias)["action"], intent)
        self.assert_no_execution()

    def test_explicit_definition_disambiguates_only_for_its_owner(self):
        self.assertEqual(language.interpret("programación")["status"], "clarify")
        self.assertIsNone(resolve_alias(self.owner, "programación"))
        self.learn("programación", "calendario")
        for text in ("programación", "Abre programación", "Hola Gica abre programación por favor"):
            with self.subTest(text=text):
                result = resolve_alias(self.owner, text)
                self.assertIsNotNone(result)
                self.assertEqual((result["action"], result["query"]), ("calendar_open", ""))
                self.assertIsNone(resolve_alias(self.other, text))
        self.assertEqual(language.interpret("programación")["status"], "clarify")

    def test_ordinary_guide_teaches_and_uses_programming_without_consuming_name_slot(self):
        from .local_commands import guide, interpret_for_owner

        self.assertEqual(guide(self.owner, "programación")["status"], "clarify")
        taught = guide(self.owner, "cuando diga programación, me refiero al calendario")
        self.assertEqual((taught["status"], taught["draft"], taught["intent"]), ("info", "", ""))
        for text in ("programación", "abre programación", "hola Gica abre programación"):
            with self.subTest(text=text):
                result = guide(self.owner, text)
                self.assertEqual((result["status"], result["intent"], result["draft"]), (
                    "ready", "calendar_open", "Abre calendario",
                ))
                self.assertEqual(interpret_for_owner(self.owner, text)["action"], "calendar_open")
                self.assertEqual(guide(self.other, text)["status"], "clarify")
        result = guide(self.owner, "Programación", context="person_name")
        self.assertEqual((result["status"], result["intent"], result["draft"]), (
            "ready", "people_search", "Busca a Programación",
        ))
        result = guide(self.owner, "programación", context="theme")
        self.assertEqual((result["status"], result["follow_up"]), ("clarify", "theme"))
        self.assertEqual(LearnedAlias.objects.count(), 1)
        self.assert_no_execution()

    def test_existing_commands_names_and_questions_cannot_be_overridden(self):
        self.learn()
        for text in (
            "abre calendario", "busca a Tablero", "busca Tablero", "modo oscuro",
            "¿abre tablero?", "quiero saber tablero", "como abrir tablero", "qué significa tablero",
        ):
            with self.subTest(text=text):
                self.assertIsNone(resolve_alias(self.owner, text))
        result = language.interpret("Busca a Tablero")
        self.assertEqual((result["action"], result["query"]), ("people_search", "Tablero"))

    def test_teaching_cannot_override_known_commands_social_or_controls(self):
        for alias in (
            "calendario", "eventos", "directorio", "modo claro", "abre", "abrir", "busca",
            "pon", "no", "nunca", "administrador", "api", "contraseña", "hola", "gracias",
            "Gica", "hablemos", "ejecuta", "yo", "persona", "comando", "instala", "token",
            "tablero y luz", "tablero no", "a" * 121, "uno dos tres cuatro", "tablero99",
            "<tablero>", "tablero; eventos", "https://example.com", "tablero\u200b",
        ):
            with self.subTest(alias=alias):
                definition = parse_teaching(f"cuando diga {alias}, me refiero a calendario")
                if definition is None:
                    self.assertIsNone(self.learn(alias))
                else:
                    with self.assertRaises(ValidationError):
                        self.learn(alias)
        self.assertFalse(LearnedAlias.objects.exists())

    def test_unsupported_or_multiple_targets_never_create_aliases(self):
        for target in (
            "busca a Jorge", "crea evento", "aprobar plan", "calendario y directorio", "no abras calendario",
            "abre calendario y cambia modo oscuro", "abre calendario si puedes", '"abre calendario"',
            "javascript:alert(1)", "admin", "inventar función",
        ):
            with self.subTest(target=target):
                # Questions in the target must not silently become definitions.
                with self.assertRaises(ValidationError):
                    self.learn(target=target)
        self.assertFalse(LearnedAlias.objects.exists())
        self.assert_no_execution()

    def test_original_guardrails_and_multiple_actions_remain_blocked(self):
        self.learn()
        for text in (
            "no abras tablero", "nunca tablero", "si abre tablero", "antes abre tablero",
            "abre tablero y calendario", "abre tablero y abre eventos", "abre tablero o tablero",
            "abre tablero y tablero", "abre tablero luego tablero", "me dijeron abre tablero",
            '"abre tablero"', "abre tablero; abre eventos", "abre tablero https://example.com",
            "abre tablero <script>", "abre tablero\nmodo claro", "abre tablero para Jorge",
            "abre tableros", "abre tablrro", "tablero de mañana", "busca a Tablero",
        ):
            with self.subTest(text=text):
                self.assertIsNone(resolve_alias(self.owner, text))
        self.assert_no_execution()

    def test_same_definition_is_idempotent_and_conflict_requires_review(self):
        entry = self.learn()
        updated_at = entry.updated_at
        self.assertEqual(self.learn().pk, entry.pk)
        entry.refresh_from_db()
        self.assertEqual(entry.updated_at, updated_at)
        with self.assertRaises(ValidationError):
            self.learn(target="directorio")
        entry.refresh_from_db()
        self.assertEqual(entry.intent, "calendar_open")
        self.assertEqual(LearnedAlias.objects.count(), 1)

    def test_disabled_stays_disabled_and_reviewed_can_be_used(self):
        entry = self.learn()
        entry.status = "disabled"
        entry.save(update_fields=["status"])
        self.assertIsNone(resolve_alias(self.owner, "abre tablero"))
        with self.assertRaises(ValidationError):
            self.learn()
        entry.refresh_from_db()
        self.assertEqual(entry.status, "disabled")
        entry.status, entry.reviewed_at = "reviewed", timezone.now()
        entry.save(update_fields=["status", "reviewed_at"])
        self.assertEqual(resolve_alias(self.owner, "tablero")["action"], "calendar_open")

    def test_manual_reviewed_pattern_has_priority_over_automatic_teaching(self):
        CommandPattern.objects.create(
            owner=self.owner, phrase="tablero", normalized_phrase="tablero",
            intent="events_open", reviewed_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            self.learn()
        self.assertFalse(LearnedAlias.objects.exists())

    def test_hundred_alias_limit_counts_disabled_and_is_per_owner(self):
        # Valid lexical labels, not a sequence of numbers or arbitrary commands.
        labels = [f"tablero {a}{b}" for a in "abcdefghij" for b in "klmnopqrst"]
        LearnedAlias.objects.bulk_create([
            LearnedAlias(
                owner=self.owner, alias=label, normalized_key=label,
                intent="calendar_open", status="disabled",
            ) for label in labels
        ])
        with self.assertRaises(ValidationError):
            self.learn()
        self.assertEqual(self.learn(actor=self.other).owner, self.other)

    def test_corrupt_or_stale_rows_fail_closed(self):
        entry = self.learn()
        for changes in (
            {"alias": "calendario"}, {"alias": "no tablero"}, {"alias": "tablero distinto"},
            {"normalized_key": "abre tablero", "alias": "abre tablero"},
        ):
            with self.subTest(changes=changes):
                LearnedAlias.objects.filter(pk=entry.pk).update(alias="tablero", normalized_key="tablero", **{
                    key: value for key, value in changes.items() if key not in {"alias", "normalized_key"}
                })
                LearnedAlias.objects.filter(pk=entry.pk).update(**changes)
                self.assertIsNone(resolve_alias(self.owner, "abre tablero"))

    def test_current_authority_and_agent_context_are_checked(self):
        for actor in (None, self.reviewer):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    try_learn(actor, "tablero significa calendario")
                with self.assertRaises(PermissionDenied):
                    resolve_alias(actor, "tablero")
        with agent_execution():
            with self.assertRaises(PermissionDenied):
                self.learn()
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.learn()
        self.assertFalse(LearnedAlias.objects.exists())

    def test_ordinary_questions_and_conversation_do_not_teach(self):
        for text in (
            "qué es mantenimiento", "hola", "abre calendario", "busca a Tablero",
            "¿programación significa calendario?", "¿tablero significa calendario?",
        ):
            with self.subTest(text=text):
                # Definition-like questions fail validation rather than being
                # accepted as a new human association.
                try:
                    result = try_learn(self.owner, text)
                except ValidationError:
                    result = None
                self.assertIsNone(result)
        self.assertFalse(LearnedAlias.objects.exists())
        self.assert_no_execution()
