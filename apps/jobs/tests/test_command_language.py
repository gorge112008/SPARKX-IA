"""Pure language acceptance and adversarial cases: no Django setup or database."""

from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from apps.jobs import command_language as language


class CommandLanguageTests(TestCase):
    def setUp(self):
        language._catalog.cache_clear()
        self.addCleanup(language._catalog.cache_clear)

    def assert_contract(self, result):
        self.assertEqual(set(result), {"status", "action", "query", "message", "options", "catalog_version"})
        self.assertIn(result["status"], {"understood", "clarify", "refused"})
        self.assertIsInstance(result["message"], str)
        self.assertLessEqual(len(result["message"]), 500)
        self.assertLessEqual(len(result["options"]), 3)
        if result["status"] == "understood":
            self.assertIn(result["action"], language.ACTION_IDS)
            self.assertEqual(bool(result["query"]), result["action"] == "people_search")
            self.assertLessEqual(len(result["query"]), 100)
        else:
            self.assertIsNone(result["action"])
            self.assertEqual(result["query"], "")
        for option in result["options"]:
            self.assertEqual(set(option), {"label", "command"})
            self.assertLessEqual(len(option["label"]), 150)
            self.assertLessEqual(len(option["command"]), 300)
            canonical = language.interpret(option["command"])
            self.assertEqual(canonical["status"], "understood")

    def test_reviewable_spanish_corpus_covers_acceptance_and_nonexecution(self):
        examples = []
        version = language._catalog()["version"]
        for filename in ("romeo_intent_examples.es.json", "gica_intent_examples.es.json"):
            corpus = json.loads(
                (Path(__file__).resolve().parents[1] / "data" / filename).read_text(encoding="utf-8")
            )
            self.assertEqual(corpus["catalog_version"], version)
            examples.extend(corpus["examples"])
        self.assertGreaterEqual(len(examples), 150)
        self.assertLessEqual(len(examples), 300)
        self.assertEqual(len({row["id"] for row in examples}), len(examples))
        self.assertEqual(len({row["command"] for row in examples}), len(examples))
        for example in examples:
            with self.subTest(case=example["id"]):
                result = language.interpret(example["command"])
                self.assert_contract(result)
                self.assertEqual(result["catalog_version"], version)
                self.assertEqual(result["status"], example["status"])
                self.assertEqual(result["action"], example.get("action"))
                self.assertEqual(result["query"], example.get("query", ""))

    def test_names_are_preserved_without_interpreting_words_as_theme_or_negation(self):
        for name in ("Claro García", "Rosa del Valle", "Ana María", "Noé Díaz", "De la Cruz", "José O'Connor", "Este López", "María Gracias", "Julio Romeo", "Julio Gica", "Ana Jica", "Rosa Yica", "Rosa Por Favor López"):
            with self.subTest(name=name):
                result = language.interpret("Busca a " + name)
                self.assertEqual((result["action"], result["query"]), ("people_search", name))

    def test_new_public_name_and_legacy_aliases_share_the_same_bounded_intent(self):
        for alias in ("Gica", "Gica-1", "Gica 1", "Gica uno", "Jica", "Yica", "Romeo", "Romeo-1", "Romeo uno"):
            with self.subTest(alias=alias):
                understood = language.interpret(f"Hola {alias}, abre calendario")
                self.assertEqual((understood["status"], understood["action"], understood["query"]),
                                 ("understood", "calendar_open", ""))
                for command in (f"{alias}, no abras calendario", f"{alias}, cambia permisos", f"{alias}, abre calendario y directorio"):
                    refused = language.interpret(command)
                    self.assertNotEqual(refused["status"], "understood")
                    self.assertIsNone(refused["action"])

    def test_directory_scope_is_grammar_at_edges_only_and_never_a_new_action(self):
        for command in ("busca a Jorge en el directorio", "buscar en el directorio a Jorge", "búsqueda de Jorge en mi directorio"):
            with self.subTest(command=command):
                result = language.interpret(command)
                self.assertEqual((result["status"], result["action"], result["query"]), ("understood", "people_search", "Jorge"))
        for command in ("busca a Jorge en el calendario", "buscar eventos de Jorge", "busca a Ana en el directorio López"):
            with self.subTest(command=command):
                self.assertEqual(language.interpret(command)["status"], "clarify")
        for command, expected in (("Busca Nose García", "Nose García"), ("Busca a Nose García", "Nose García"),
                                  ("Busca Este López", "Este López"), ("Busca a Rosa Por Favor López", "Rosa Por Favor López")):
            self.assertEqual(language.interpret(command)["query"], expected)

    def test_negation_quotes_and_conditions_never_return_an_executable_partial_intent(self):
        for command in ("no abre calendario", "abre calendario sin cambiar el tema", "no sólo abre calendario", "si puedes, abre calendario",
                        "abre calendario cuando puedas", "el texto dice abre calendario", "«abre calendario»", "abre calendario; muestra eventos",
                        "Busca a Ana y después abre directorio", "No sé si abre calendario"):
            with self.subTest(command=command):
                result = language.interpret(command)
                self.assertNotEqual(result["status"], "understood")
                self.assertIsNone(result["action"])
                self.assertEqual(result["query"], "")

    def test_limits_and_controls_are_checked_before_normalizing_or_trimming(self):
        for value in (None, [], {}, 1, True, " " * 301, "\nAbre calendario", "Abre calendario\t", "Abre\x00calendario", "Busca a A\ud800"):
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(language.interpret(value)["status"], "refused")
        self.assertEqual(language.interpret("Busca a " + "Á" * 100)["status"], "understood")
        too_long = language.interpret("Busca a " + "Á" * 101)
        self.assertEqual((too_long["status"], too_long["action"]), ("clarify", None))

    def test_interpretation_is_idempotent_and_returns_independent_results_without_side_effects(self):
        language.interpret("Abre calendario")  # Load the immutable vocabulary before checking side effects.
        with patch("builtins.open", side_effect=AssertionError("no writes or secondary files")), \
                patch("subprocess.Popen", side_effect=AssertionError("no child processes")), \
                patch("socket.socket", side_effect=AssertionError("no network")):
            first = language.interpret("Hola Romeo, busca a María Pérez")
            second = language.interpret("Hola Romeo, busca a María Pérez")
        self.assertEqual(first, second)
        first["options"].append({"label": "tampered", "command": "apaga"})
        first["query"] = "Changed"
        self.assertEqual(language.interpret("Hola Romeo, busca a María Pérez"), second)

    def test_missing_or_invalid_bank_fails_closed_without_an_embedded_fallback(self):
        folder = language.BANK_PATH.parent
        originals = {
            filename: (folder / filename).read_text(encoding="utf-8")
            for filename in [language.BANK_PATH.name, *language._MODULE_FILES.values()]
        }
        manifest = json.loads(originals[language.BANK_PATH.name])
        cases = [(language.BANK_PATH.name, source) for source in ("not-json", "[]", "{}")]
        unknown = json.loads(originals["gica_intents.es.json"])
        unknown["actions"]["admin_open"] = {"label": "Admin", "command": "Abre admin", "targets": ["admin"]}
        cases.append(("gica_intents.es.json", json.dumps(unknown)))
        dynamic = deepcopy(manifest)
        dynamic["regex"] = ".*"
        cases.append((language.BANK_PATH.name, json.dumps(dynamic)))
        invalid_limits = deepcopy(manifest)
        invalid_limits["limits"]["query"] = 10000
        cases.append((language.BANK_PATH.name, json.dumps(invalid_limits)))
        path_escape = deepcopy(manifest)
        path_escape["modules"]["vocabulary"] = "../../private.json"
        cases.append((language.BANK_PATH.name, json.dumps(path_escape)))
        negative_prefix = json.loads(originals["gica_vocabulary.es.json"])
        negative_prefix["prefixes"].append("no abras")
        cases.append(("gica_vocabulary.es.json", json.dumps(negative_prefix)))
        bad_dialogue = json.loads(originals["gica_dialogues.es.json"])
        bad_dialogue["catalog_version"] = "es-2020-01-01.1"
        cases.append(("gica_dialogues.es.json", json.dumps(bad_dialogue)))
        duplicate = originals["gica_dialogues.es.json"].replace(
            '"language": "es"', '"language": "es", "language": "es"'
        )
        cases.append(("gica_dialogues.es.json", duplicate))
        invalid_normalization = json.loads(originals["gica_normalization.es.json"])
        invalid_normalization["limits"]["max_distance"] = 20
        cases.append(("gica_normalization.es.json", json.dumps(invalid_normalization)))
        for filename, source in cases:
            modified = {**originals, filename: source}

            def read_module(path, *args, **kwargs):
                return modified[path.name]

            with self.subTest(module=filename, source=source[:30]), patch.object(
                Path, "read_text", read_module
            ):
                language._catalog.cache_clear()
                result = language.interpret("Abre calendario")
                self.assertEqual((result["status"], result["action"], result["catalog_version"]), ("refused", None, "unavailable"))
        with patch.object(Path, "read_text", side_effect=FileNotFoundError):
            language._catalog.cache_clear()
            self.assertEqual(language.interpret("Abre calendario")["status"], "refused")

    def test_catalog_is_only_finite_vocabulary_and_does_not_expand_action_authority(self):
        bank = language._catalog()
        self.assertIsNotNone(bank)
        self.assertEqual(set(bank["actions"]), language.ACTION_IDS)
        self.assertEqual(len(bank["actions"]), 6)
        for forbidden in ("Abre admin", "Crea un evento", "Envia correo", "Ejecuta powershell", "Cambia presupuesto", "Abre https://example.invalid"):
            with self.subTest(command=forbidden):
                self.assertEqual(language.interpret(forbidden)["status"], "refused")

    def test_modular_catalogue_preserves_slots_dialogues_and_ambiguous_agenda(self):
        bank = language._catalog()
        self.assertEqual(bank["slots"], {"person_name": {"kind": "person_name", "max_length": 100}})
        self.assertIn("hola chica", bank["greetings"])
        self.assertEqual(set(bank["dialogues"]), language._DIALOGUE_KEYS)
        for command in ("agenda", "abre el programa del evento", "pon mi agenda", "cronograma"):
            with self.subTest(command=command):
                result = language.interpret(command)
                self.assertEqual((result["status"], result["action"]), ("clarify", None))
                self.assertEqual(result["message"], bank["dialogues"]["ambiguous_agenda"])
        explicit_contacts = language.interpret("abre agenda de contactos")
        self.assertEqual(explicit_contacts["action"], "directory_open")

    def test_public_greeting_helper_is_exact_bounded_and_fails_closed(self):
        for greeting in ("Hola Chica", "¿Hola, Gica?", "buenos días", "ayuda", "¿Qué puedes hacer?"):
            with self.subTest(greeting=greeting):
                self.assertTrue(language.is_greeting(greeting))
        for text in (
            "Hola Chica abre eventos", "no hola", '"Hola Chica"', "hola\n", "hola " * 100,
            "Hola https://example.invalid", None, [],
        ):
            with self.subTest(text=text):
                self.assertFalse(language.is_greeting(text))
        with patch.object(language, "_catalog", return_value=None):
            self.assertFalse(language.is_greeting("Hola Chica"))
