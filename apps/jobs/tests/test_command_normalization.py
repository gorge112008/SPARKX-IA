"""Grammar-only morphology and spelling; no HTTP, database or model calls."""

from copy import deepcopy
import json
from unittest import TestCase
from unittest.mock import patch

from apps.jobs import command_language as language
from apps.jobs import command_normalization as normalization


class CommandNormalizationTests(TestCase):
    def setUp(self):
        language._catalog.cache_clear()
        self.addCleanup(language._catalog.cache_clear)
        self.bank = language._catalog()
        self.rules = self.bank["normalization"]

    def assert_action(self, command, action, query=""):
        result = language.interpret(command)
        self.assertEqual((result["status"], result["action"], result["query"]),
                         ("understood", action, query), command)

    def test_morphology_and_reviewed_inflections_cover_the_same_six_actions(self):
        cases = (
            ("abre caldenarios", "calendar_open"),
            ("caldenarios", "calendar_open"),
            ("abran los calendarios de eventos", "calendar_open"),
            ("muéstranos las vistas calendarios", "calendar_open"),
            ("abre evento", "events_open"),
            ("abre listas de evento", "events_open"),
            ("abre directorios", "directory_open"),
            ("abre contacto", "directory_open"),
            ("abre agendas de contactos", "directory_open"),
            ("pongan temas claros", "theme_light"),
            ("activen los modos oscuros", "theme_dark"),
        )
        for command, action in cases:
            with self.subTest(command=command):
                self.assert_action(command, action)
        self.assert_action("busquen personas Ana", "people_search", "Ana")

    def test_generated_morphology_matrix_has_96_contextual_forms(self):
        count = 0
        destinations = (
            ("calendarios", "calendar_open"), ("caldenarios", "calendar_open"),
            ("evento", "events_open"), ("directorios", "directory_open"),
            ("contacto", "directory_open"), ("personas", "directory_open"),
        )
        for prefix in ("", "Hola Gica ", "por favor ", "me puedes "):
            for verb in ("abre", "muestra"):
                for noun, action in destinations:
                    for suffix in ("", " por favor"):
                        command = f"{prefix}{verb} {noun}{suffix}"
                        with self.subTest(command=command):
                            self.assert_action(command, action)
                        count += 1
        self.assertEqual(count, 96)

    def test_search_scopes_are_grammar_but_names_stay_raw_nfc(self):
        for command in (
            "busca en los directorios a José", "busca a José en mis directorios",
            "busca en el directorrio a José", "busca a José en el directorios",
            "busca persona José", "busca personas José", "busca contacto José",
        ):
            with self.subTest(command=command):
                self.assert_action(command, "people_search", "José")
        for name in ("Caldenarios", "Evento", "Calendario", "Directorios", "Temas Claros",
                     "Ana Directorios Pérez", "Graccias", "Vista", "Clara"):
            with self.subTest(name=name):
                self.assert_action("Busca a " + name, "people_search", name)
        self.assert_action("busca a Jose\u0301 en mis directorios", "people_search", "José")

    def test_original_guards_and_unsupported_filters_survive_normalization(self):
        for command in (
            "no abras caldenarios", "si puedes abre caldenarios", '"abre caldenarios"',
            "dijo que abre caldenarios", "abre caldenarios y evento", "abre eventos; muestra directorios",
            "abre caldenarios por empresa", "abre directorios de expositores", "cambia usuarios",
            "abre admin", "abre https://example.invalid", "abree calendario", "abree caldenarios",
            "busca a Jorge en el calendario", "buscar eventos de Jorge", "buscar calendario",
            "busca a Ana en el directorio López", "busca en las agendas a Ana",
        ):
            with self.subTest(command=command):
                result = language.interpret(command)
                self.assertNotEqual(result["status"], "understood")
                self.assertIsNone(result["action"])
                self.assertEqual(result["query"], "")
        for command in ("agendas", "abre programas", "programaciones", "cronogramas"):
            with self.subTest(command=command):
                self.assertEqual(language.interpret(command)["status"], "clarify")

    def test_fixed_point_is_idempotent_preserves_offsets_and_original_edit_budget(self):
        tokens = (("caldenarios", 5, 16), ("eventos", 20, 27))
        first = normalization.normalize_tokens(tokens, self.rules, strong_context=True)
        self.assertEqual(first.tokens, (("calendario", 5, 16), ("eventos", 20, 27)))
        self.assertTrue(first.bounded)
        self.assertFalse(first.ambiguous)
        self.assertLessEqual(first.passes, 3)
        second = normalization.normalize_tokens(first.tokens, self.rules, strong_context=True)
        self.assertEqual(first.tokens, second.tokens)
        weak = normalization.normalize_tokens(tokens, self.rules)
        self.assertEqual(weak.tokens[0][0], "caldenarios")
        for word in ("no", "si", "borra", "abree", "programasss"):
            self.assertEqual(normalization.canonical_word(word, self.rules)[0], word)
        self.assertEqual(normalization.canonical_word("clrao", self.rules)[0], "claro")
        self.assertEqual(normalization.canonical_word("calendarioxxx", self.rules, strong_context=True)[0],
                         "calendarioxxx")

    def test_candidates_tied_between_concepts_clarify_instead_of_choosing_order(self):
        ambiguous = deepcopy(self.rules)
        ambiguous["concepts"] = {
            "claro": {"variants": ("claro",), "max_distance": 1},
            "oscuro": {"variants": ("cloro",), "max_distance": 1},
        }
        word, uncertain = normalization.canonical_word("cliro", ambiguous)
        self.assertEqual((word, uncertain), ("cliro", True))
        result = normalization.normalize_tokens((("cliro", 0, 5),), ambiguous)
        self.assertTrue(result.ambiguous)
        bank = {**self.bank, "normalization": ambiguous}
        with patch.object(language, "_catalog", return_value=bank):
            self.assertEqual(language.interpret("pon cliro")["status"], "clarify")

    def test_bounds_and_invalid_normalization_data_fail_closed(self):
        too_many = tuple(("x", index, index + 1) for index in range(81))
        self.assertFalse(normalization.normalize_tokens(too_many, self.rules).bounded)
        for tokens in ((("evento", -1, 2),), (("evento", 0, 301),), ((True, 0, 1),)):
            self.assertFalse(normalization.normalize_tokens(tokens, self.rules).bounded)
        source = json.loads((language.BANK_PATH.parent / "gica_normalization.es.json").read_text(encoding="utf-8"))
        changes = (
            {"catalog_version": "es-2020-01-01.1"},
            {"limits": {**source["limits"], "max_passes": 100}},
            {"concepts": {**source["concepts"], "admin": source["concepts"]["calendar"]}},
            {"scope_determiners": {"no": "el"}},
            {"grammar_variants": {**source["grammar_variants"], "agenda": ["agenda", "admin"]}},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalization.compile_rules({**source, **change}, version=self.bank["version"])
