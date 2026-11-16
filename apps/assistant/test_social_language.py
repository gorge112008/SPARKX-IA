"""Pure social grammar checks, without Django, microphones or remote services."""

from copy import deepcopy
import json
from unittest import TestCase
from unittest.mock import patch
import unicodedata

from . import social_language as social


class SocialLanguageTests(TestCase):
    def tearDown(self):
        social._catalog.cache_clear()

    def assert_social(self, text, kind):
        result = social.resolve(text)
        self.assertIsNotNone(result, text)
        self.assertEqual(set(result), {"kind", "reply", "person_name"})
        self.assertEqual(result["kind"], kind)
        self.assertLessEqual(len(result["reply"]), 280)
        self.assertLessEqual(len(result["person_name"]), 80)
        return result

    def test_greetings_have_finite_canonical_responses_and_aliases(self):
        cases = {
            "¡Hola!": "Hola.", "Holi": "Hola.", "Hey": "Hola.",
            "buenosdias": "Buenos días.", "BUEN DÍA": "Buenos días.",
            "Buenas tardes": "Buenas tardes.", "buenasnoches": "Buenas noches.",
            "Muy buenas": "Buenas.",
        }
        for phrase, reply in cases.items():
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "greeting")
                self.assertEqual(result["reply"], reply)
                self.assertTrue(social.greet_only(phrase))
        for alias in ("Gica", "Jica", "Yica", "Yika", "Llica", "Ilica", "Chica"):
            for phrase in (f"Hola {alias}", f"{alias}, buenos días", f"Hola {alias} uno"):
                with self.subTest(phrase=phrase):
                    self.assert_social(phrase, "greeting")

    def test_courtesies_wellbeing_and_farewell_are_whole_turns(self):
        for phrase in ("gracias", "muchísimas gracias", "por favor", "perdón", "de nada",
                       "no hay de qué", "Gica, gracias"):
            with self.subTest(phrase=phrase):
                self.assert_social(phrase, "courtesy")
        for phrase in ("¿Cómo estás?", "cómo te va", "qué tal", "Gica, todo bien"):
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "wellbeing")
                self.assertIn("Estoy bien", result["reply"])
                self.assertFalse(social.greet_only(phrase))
        for phrase in ("adiós", "hasta luego", "nos vemos", "chau Gica"):
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "farewell")
                self.assertNotIn("cerrada", result["reply"])

    def test_safe_greeting_composition_does_not_invent_clock_time(self):
        result = self.assert_social("Buenos días Gica, ¿cómo estás?", "wellbeing")
        self.assertTrue(result["reply"].startswith("Buenos días. Estoy bien"))
        for phrase in ("qué hora es", "Gica, dime la hora", "¿Cuál es la hora?"):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.assert_social(phrase, "time")["reply"], "")
        result = self.assert_social("Hola Gica, ¿qué hora es?", "time")
        self.assertEqual(result["reply"], "Hola.")
        self.assertEqual(result["person_name"], "")
        self.assertTrue(self.assert_social("Hola, gracias", "courtesy")["reply"].startswith("Hola."))
        result = self.assert_social("Buenos días, manda un saludo a Ana", "person_greeting")
        self.assertEqual(result["person_name"], "Ana")
        self.assertTrue(result["reply"].startswith("Buenos días."))
        self.assertIn("Ana", result["reply"])

    def test_named_greeting_preserves_real_names_including_agent_aliases(self):
        for name in (
            "Ana", "Chica", "Jica", "Yika", "Rosa Yika", "Gica del Valle",
            "Ana María", "José O'Connor", "María-José", "Ángel de la Cruz", "王明", "लीला",
        ):
            for prefix in ("manda un saludo a", "envía un saludo para", "dale un saludo a",
                           "saluda a"):
                with self.subTest(name=name, prefix=prefix):
                    result = self.assert_social(prefix + " " + name, "person_greeting")
                    self.assertEqual(result["person_name"], name)
                    self.assertIn(name, result["reply"])
                    self.assertNotIn("enviado", result["reply"])
        decomposed = unicodedata.normalize("NFD", "José Pérez")
        result = self.assert_social("saluda a " + decomposed, "person_greeting")
        self.assertEqual(result["person_name"], "José Pérez")

    def test_missing_name_invites_a_complete_new_request(self):
        for phrase in ("manda un saludo a", "envía un saludo para", "saluda a"):
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "person_greeting")
                self.assertEqual(result["person_name"], "")
                self.assertIn("manda un saludo a Ana", result["reply"])
        self.assertIsNone(social.resolve("Ana"))

    def test_person_names_do_not_accept_contacts_code_or_concatenated_orders(self):
        names = (
            "Ana y Pedro", "Ana y abre calendario", "Ana; abre directorio", "Ana, borra todo",
            "Ana que cambie permisos", "Ana después ejecuta", "admin@example.invalid",
            "https://example.invalid", "<script>alert</script>", "Ana_1", "Ana123",
            "Ana = borra", "Ana\\carpeta", "'Ana'", '"Ana"', "Ana\nabre calendario",
            "Ana\u202e", "Ana / Pedro", "Ana (ejecuta)", "Ana\tPérez",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIsNone(social.resolve("manda un saludo a " + name))
        for phrase in (
            "no manda un saludo a Ana", "manda un saludo a No", "si puedes saluda a Ana",
            "dijo saluda a Ana", "supongamos saluda a Ana", "saluda Juan y abre calendario",
            "manda un saludo a Ana o María", "saluda a Ana si quieres", "saluda a Ana nunca",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
        self.assertEqual(social.resolve("saluda a Noelia")["person_name"], "Noelia")

    def test_social_mixtures_never_swallow_an_action_or_refusal(self):
        for phrase in (
            "hola abre calendario", "gracias abre eventos", "hola cómo estás y abre eventos",
            "hola no abras calendario", "hola abre calendario y directorio", "no hola",
            'dijo "hola"', "si puedes buenos días", "gracias; borra mis datos",
            "hola cambia permisos", "hola necesito pagar", "saluda a Ana y gracias",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
                self.assertFalse(social.greet_only(phrase))

    def test_greeting_prefix_requires_the_same_single_understood_action(self):
        for greeting, reply in (
            ("Hola", "Hola."), ("Buenos días", "Buenos días."),
            ("Buenas tardes", "Buenas tardes."), ("Buenas noches", "Buenas noches."),
            ("Buenas", "Buenas."),
        ):
            with self.subTest(greeting=greeting):
                self.assertEqual(social.greeting_prefix(greeting + " Gica abre calendario"), reply)
        self.assertEqual(social.greeting_prefix("Hola Chica, busca a Yika"), "Hola.")
        for phrase in (
            "Hola", "hola qué hora es", "hola no abras eventos", "hola abre eventos y calendario",
            "hola si puedes abre eventos", 'hola dijo "abre calendario"',
            "hola cambia permisos", "hola abre calendario por empresa", "hola busca a alguien",
            "gracias abre calendario", "hola https://example.invalid",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(social.greeting_prefix(phrase), "")

    def test_bounds_and_unknown_text_fail_closed(self):
        for phrase in (None, 1, {}, "", " " * 301, "hola" + " " * 297, "necesito otra cosa"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
                self.assertEqual(social.greeting_prefix(phrase), "")
        self.assert_social("saluda a " + "A" * 80, "person_greeting")
        self.assertIsNone(social.resolve("saluda a " + "A" * 81))

    def test_observed_paraphrases_compose_without_new_actions(self):
        result = self.assert_social("Puedes mandarle un saludo a Manu.", "person_greeting")
        self.assertEqual(result["person_name"], "Manu")
        self.assertIn("¡Hola, Manu!", result["reply"])
        result = self.assert_social("Quiero saludar.", "person_greeting")
        self.assertEqual(result["person_name"], "")
        self.assertIn("manda un saludo a Ana", result["reply"])
        self.assertEqual(self.assert_social("O buenas noches.", "greeting")["reply"],
                         "Buenas noches.")
        self.assertEqual(self.assert_social("¿Puedes decirme la hora?", "time")["reply"], "")

    def test_modal_and_infinitive_grammar_preserves_the_name_slot(self):
        cases = (
            ("Me puedes mandar un saludo a Chica", "Chica"),
            ("Podrías enviar un saludo para Jica", "Jica"),
            ("Me gustaría saludar a Yika", "Yika"),
            ("Quisiera darle un saludo a Ana María", "Ana María"),
            ("Por favor Gica saluda a Ana", "Ana"),
            ("Un saludo para Manu", "Manu"),
            ("Quiero saludar a Gica del Valle", "Gica del Valle"),
            ("Puedes mandarle un saludo a Noelia por favor", "Noelia"),
            ("Buenos días Gica puedes enviar un saludo para Rosa Yika", "Rosa Yika"),
        )
        for phrase, name in cases:
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "person_greeting")
                self.assertEqual(result["person_name"], name)
                if phrase.startswith("Buenos días"):
                    self.assertTrue(result["reply"].startswith("Buenos días. ¡Hola, Rosa Yika!"))
        result = self.assert_social("Buenas noches, quiero saludar", "person_greeting")
        self.assertTrue(result["reply"].startswith("Buenas noches. Claro."))

    def test_time_grammar_accepts_explicit_questions_not_arbitrary_hour_mentions(self):
        for phrase in (
            "Puedes decir la hora", "Podrías decirme la hora", "Me puedes decirnos la hora",
            "Quiero saber qué hora es", "Me gustaría conocer la hora actual", "Dame la hora",
            "Puedes darme la hora", "Podrías dar la hora", "Por favor dime la hora",
            "Hola Gica me puedes decirme qué hora es por favor",
        ):
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "time")
                self.assertEqual(result["person_name"], "")
                self.assertEqual(result["reply"], "Hola." if phrase.startswith("Hola") else "")
        for phrase in (
            "Organiza una hora", "Puedes abrir la hora", "Una hora de eventos",
            "Dame la hora y abre calendario", "Quiero saber la hora de la reunión",
            "Dime la hora en https://example.invalid", "Ahora voy a decirme la hora",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))

    def test_wrappers_never_remove_negation_conditions_quotes_or_other_clauses(self):
        for phrase in (
            "No puedes decirme la hora", "Puedes no decirme la hora", "Puedes nunca saludar a Ana",
            "Si puedes mandarle un saludo a Manu", "Dijo puedes saludar a Ana",
            "Puedes decirme la hora si quieres", 'Puedes decirme "la hora"',
            "Puedes mandar un saludo a Ana y luego abre eventos",
            "Quiero saludar a Ana o Pedro", "Me puedes mandar un saludo a Ana; pulsa calendario",
            "Por favor puedes ejecutar un script", "Puedes saludar a Manu que abre permisos",
            "Quiero saludar a Ana después borra todo", "Puedes darme la hora o abrir eventos",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
                self.assertFalse(social.greet_only(phrase))

    def test_stt_o_filler_is_limited_to_an_entire_greeting(self):
        for phrase in ("O buenasnoches", "O Gica buenas tardes", "O hola Gica"):
            with self.subTest(phrase=phrase):
                self.assert_social(phrase, "greeting")
        for phrase in (
            "O puedes decirme la hora", "O buenas noches abre eventos", "Buenas noches o buenos días",
            "Abre calendario o directorio", "Hola O abre calendario", "O saluda a Ana",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
                self.assertEqual(social.greeting_prefix(phrase), "")

    def test_real_stt_acknowledgement_and_usual_courtesies(self):
        for phrase in (
            "O k muchas gracias.", "Muchas gracias Gica", "Muchas gracias por tu ayuda",
            "muchísimas gracias por todo", "Te agradezco mucho por tu ayuda",
            "Te lo agradezco de corazón", "Gracias por tu apoyo de verdad", "Gracias por favor",
            "muchas, muchas gracias", "con permiso", "disculpa la molestia",
            "ya gracias", "chévere gracias", "bacán gracias", "okey muchas gracias",
        ):
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "courtesy")
                self.assertEqual(result["person_name"], "")
                self.assertFalse(social.greet_only(phrase))
        self.assertIsNone(social.resolve("Busca a Gracias"))
        self.assertIsNone(social.resolve("Gracias Pérez"))

    def test_bounded_courtesy_matrix_has_96_independent_forms(self):
        count = 0
        for acknowledgement in ("O k", "vale", "chévere", "listo"):
            for thanks in ("gracias", "muchas gracias", "muchísimas gracias", "mil gracias"):
                for reason in ("", " por tu ayuda", " por todo"):
                    for ending in (" Gica.", ", Jica!"):
                        phrase = acknowledgement + ", " + thanks + reason + ending
                        with self.subTest(phrase=phrase):
                            result = self.assert_social(phrase, "courtesy")
                            self.assertEqual(result["person_name"], "")
                            self.assertIn("Con gusto.", result["reply"])
                        count += 1
        self.assertEqual(count, 96)

    def test_only_complete_social_atoms_may_compose_or_contain_lexical_negation(self):
        cases = (
            ("Hola, gracias y hasta luego", "farewell"),
            ("Gica, no hay de qué", "courtesy"),
            ("Hola, no hay de qué", "courtesy"),
            ("Gracias y de nada", "courtesy"),
            ("Disculpa, por favor", "courtesy"),
            ("No, gracias", "courtesy"),
            ("No muchas gracias", "courtesy"),
            ("Sí gracias", "courtesy"),
            ("Sí, muchas gracias por tu ayuda", "courtesy"),
            ("Hola muchas gracias y chau", "farewell"),
            ("Saludos, gracias", "courtesy"),
        )
        for phrase, kind in cases:
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, kind)
                self.assertEqual(result["person_name"], "")
        reply = social.resolve("gracias gracias gracias")["reply"]
        self.assertEqual(reply.count("Con gusto."), 1)

    def test_reciprocity_is_a_complete_atom_with_safe_composition(self):
        for phrase in (
            "igualmente", "igual", "para ti igualmente", "igualmente para ti",
            "para ti también", "también para ti", "a ti también", "lo mismo para ti",
            "gracias, igualmente", "muchas gracias y para ti igualmente",
            "Hola, gracias, igualmente",
        ):
            with self.subTest(phrase=phrase):
                result = self.assert_social(phrase, "courtesy")
                self.assertIn("Lo mismo para ti.", result["reply"])
                self.assertEqual(result["person_name"], "")
        for phrase in (
            "gracias, igualmente abre eventos", "igualmente no abras calendario",
            "dijo igualmente", "igualborra", "igualmente para Chica", "no igualmente",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
        result = self.assert_social("saluda a Igual", "person_greeting")
        self.assertEqual(result["person_name"], "Igual")
        self.assertIsNone(social.resolve("Busca a Igualmente"))

    def test_social_examples_promised_in_current_documentation(self):
        cases = (
            ("Buenos días", "greeting"), ("cómo estás", "wellbeing"), ("gracias", "courtesy"),
            ("Manda un saludo a Ana", "person_greeting"), ("Qué hora es", "time"),
            ("O k muchas gracias", "courtesy"), ("listo, gracias por tu ayuda", "courtesy"),
            ("gracias, igualmente", "courtesy"), ("no, gracias", "courtesy"),
            ("no hay de qué", "courtesy"), ("¿Podrías decirme la hora, por favor?", "time"),
            ("Puedes mandarle un saludo a Ana", "person_greeting"),
        )
        for phrase, kind in cases:
            with self.subTest(phrase=phrase):
                self.assert_social(phrase, kind)
        self.assertEqual(social.greeting_prefix("buenos días, abre calendario"), "Buenos días.")

    def test_unstored_concept_context_and_variable_nucleus_position(self):
        examples = (
            "oye te doy las graccias por ayudarme con esto",
            "perfecto de verdad muchas gracias Gica",
            "gracias por todo lo que me has ayudado",
            "Por tu ayuda, muchísimas graccias",
            "me has ayudado mucho gracias",
            "gracias por abrir calendario",
            "gracias por abrir el calendario",
            "por abrir calendario muchas gracias",
        )
        raw = social.BANK_PATH.read_text(encoding="utf-8").casefold()
        for phrase in examples:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.casefold(), raw)
                result = self.assert_social(phrase, "courtesy")
                self.assertEqual(result["person_name"], "")
                self.assertIn("Con gusto.", result["reply"])
                self.assertNotIn("abrí", result["reply"])
        for phrase in ("abrir calendario gracias", "por calendario abrir gracias"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))

    def test_only_reviewed_social_nuclei_receive_bounded_typo_tolerance(self):
        for phrase in (
            "graccias", "graciass", "agradezcco", "te doy las graciqs por ayudarme",
            "muchas gracis", "te agradezo por tu ayuda",
        ):
            with self.subTest(phrase=phrase):
                self.assert_social(phrase, "courtesy")
        for phrase in ("Gracia", "gacias", "agradezo", "desgracias", "grac", "graciiios"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
        bank = social._catalog()
        for word in ("no", "si", "lo", "ya", "abre", "abree", "Gracia", "x" * 33):
            with self.subTest(word=word):
                self.assertIsNone(social._nucleus(word.casefold(), bank))

    def test_typo_tolerance_never_changes_names_commands_or_original_text(self):
        for name in ("Graccias", "Gracia", "Chica", "Yika", "Graccias Pérez"):
            source = "saluda a " + name
            with self.subTest(name=name):
                result = self.assert_social(source, "person_greeting")
                self.assertEqual(result["person_name"], name)
                self.assertEqual(source, "saluda a " + name)
                self.assertIsNone(social.resolve("Busca a " + name))
                self.assertEqual(social.command_language.interpret("Busca a " + name)["query"], name)
        self.assertEqual(social.greeting_prefix("Hola busca a Graccias"), "Hola.")
        self.assertIsNone(social.resolve("abree calendario"))
        self.assertEqual(social.greeting_prefix("Hola abree calendario"), "")

    def test_a_keyword_in_mentions_negations_or_mixed_actions_is_not_gratitude(self):
        for phrase in (
            "se llama Gracias", "el botón dice gracias", "la palabra gracias", "qué significa gracias",
            "no digas gracias", "no quiero dar las graccias", "no te doy las gracias",
            "no me has ayudado gracias", "si me has ayudado gracias", 'dijo "graccias"',
            "gracias y abre calendario", "gracias por favor abre calendario",
            "gracias por ayudarme y abre calendario", "gracias, abre calendario",
            "gracias por borrar eventos", "gracias por tu ayuda no abras eventos",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
                self.assertFalse(social.greet_only(phrase))
        for phrase in ("no gracias", "sí gracias", "no hay de qué"):
            with self.subTest(phrase=phrase):
                self.assert_social(phrase, "courtesy")

    def test_social_families_are_lexeme_concepts_not_complete_phrase_lists(self):
        bank = json.loads(social.BANK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(bank["catalog_version"], "social-es-2026-11-15.4")
        self.assertFalse(set(bank) & {"greetings", "courtesies", "wellbeing", "farewells", "gratitude"})
        for family, concept in bank["social_concepts"].items():
            for role, value in concept.items():
                if isinstance(value, list):
                    with self.subTest(family=family, role=role):
                        self.assertTrue(all(len(word.split()) == 1 for word in value))

    def test_extra_social_parts_or_action_text_invalidate_the_whole_composition(self):
        for phrase in (
            "ok hola gracias y chau", "gracias gracias gracias gracias",
            "hola muchas muchas muchas gracias", "O k muchas gracias abre calendario",
            "gracias y abre eventos", "no gracias abre calendario", "sí gracias abre calendario",
            "O k no abras calendario", "no muchas gracias y borra todo",
            "gracias y no abras eventos", "No hay de qué abre directorio",
            "gracias si puedes", 'dijo "muchas gracias"', "supongamos que gracias",
            "gracias o abre calendario", "muchas gracias a https://example.invalid",
            "gracias por tu ayuda y saluda a Chica", "gracias y Chica", "no gracias no",
            "Gracias Ana", "O k muchas gracias si puedes borrar", "gracias y",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(social.resolve(phrase))
                self.assertFalse(social.greet_only(phrase))
                self.assertEqual(social.greeting_prefix(phrase), "")

    def test_invalid_or_missing_bank_never_resolves_or_prefixes(self):
        original = json.loads(social.BANK_PATH.read_text(encoding="utf-8"))

        def concept_change(family, **changes):
            return {"social_concepts": {
                **original["social_concepts"],
                family: {**original["social_concepts"][family], **changes},
            }}

        changes = (
            {"catalog_version": "unreviewed"}, {"language": "en"}, {"extra": "selector"},
            {"agent_aliases": ["Gica", "unknown"]}, {"time": [{"phrases": ["hora"], "reply": "12:00"}]},
            concept_change("greeting", hello=["hola", "HOLA"]),
            concept_change("greeting", hello_reply="Otra respuesta."),
            {"person_greeting": {"prefixes": ["saluda a"], "reply_template": "{evil}",
                                 "missing_reply": "Nombre"}},
            {"guards": {**original["guards"], "negations": ["nunca"]}},
            {"catalog_version": "social-es-2026-11-15.1"},
            {"wrappers": {**original["wrappers"], "prefixes": ["no"]}},
            {"wrappers": {**original["wrappers"], "greeting_fillers": ["o", "y"]}},
            {"person_greeting": {**original["person_greeting"], "verbs": []}},
            {"catalog_version": "social-es-2026-11-15.2"},
            {"composition": {"max_parts": 4, "connectors": ["y", "e"]}},
            {"composition": {"max_parts": 3, "connectors": ["y", "abre"]}},
            {"catalog_version": "social-es-2026-11-15.3"},
            concept_change("gratitude", help=["por tu ayuda"]),
            concept_change("typos", max_distance=2),
            concept_change("typos", eligible=["gracias", "abre"]),
            concept_change("typos", excluded=[]),
        )
        payloads = ["{", '{"catalog_version":"x","catalog_version":"y"}', "NaN"]
        for change in changes:
            corrupted = deepcopy(original)
            corrupted.update(change)
            payloads.append(json.dumps(corrupted, ensure_ascii=False))
        for payload in payloads:
            social._catalog.cache_clear()
            with self.subTest(payload=payload[:60]), patch.object(
                type(social.BANK_PATH), "read_text", return_value=payload
            ):
                self.assertIsNone(social.resolve("hola"))
                self.assertEqual(social.greeting_prefix("hola abre calendario"), "")
        social._catalog.cache_clear()
        with patch.object(type(social.BANK_PATH), "read_text", side_effect=OSError):
            self.assertIsNone(social.resolve("hola"))
