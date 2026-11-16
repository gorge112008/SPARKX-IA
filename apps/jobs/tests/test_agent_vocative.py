"""Agent pronunciations at grammar edges never rewrite a person's name."""

from unittest import TestCase

from apps.jobs import command_language as language


class AgentVocativeTests(TestCase):
    def test_pronunciations_normalize_only_vocative_edges(self):
        for alias in (
            "Gica", "Jica", "Yica", "Yika", "Llica", "Ilica", "Yika-1", "Yika uno", "Chica",
        ):
            with self.subTest(alias=alias):
                self.assertEqual(
                    language.normalize_agent_vocative(f"Hola {alias}, abre calendario"),
                    "Hola Gica, abre calendario",
                )
                self.assertEqual(
                    language.normalize_agent_vocative(f"Busca a Ana, {alias}"),
                    "Busca a Ana, Gica",
                )
                result = language.interpret(f"Hola {alias}, abre calendario")
                self.assertEqual((result["status"], result["action"]), ("understood", "calendar_open"))

    def test_person_names_and_internal_words_are_preserved(self):
        for name in (
            "Yika", "Llica", "Ilica", "Rosa Yika", "Yika Pérez", "Gica del Valle",
            "Yika Uno", "Ana Gica 1", "Rosa Llica-1", "Chica", "María Chica", "Jica",
        ):
            command = "Busca a " + name
            with self.subTest(name=name):
                self.assertEqual(language.normalize_agent_vocative(command), command)
                result = language.interpret(command)
                self.assertEqual((result["action"], result["query"]), ("people_search", name))
        self.assertEqual(language.normalize_agent_vocative("Yika Pérez"), "Yika Pérez")

    def test_aliases_do_not_hide_negation_quotes_conditions_or_multiple_actions(self):
        for alias in ("Yika", "Llica", "Ilica", "Chica"):
            for suffix in (
                "no abre calendario", "abre calendario y directorio", "cambia permisos",
                "si puedes abre calendario", 'dijo que "abre calendario"',
            ):
                with self.subTest(alias=alias, suffix=suffix):
                    result = language.interpret(f"Hola {alias}, {suffix}")
                    self.assertNotEqual(result["status"], "understood")
                    self.assertIsNone(result["action"])
        unsafe = "Hola Yika, abre https://example.invalid"
        self.assertEqual(language.normalize_agent_vocative(unsafe), unsafe)
