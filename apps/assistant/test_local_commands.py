"""Read-only guidance and explicitly reviewed owner-scoped phrase memory."""

from unittest.mock import patch
from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.jobs.command_language import ACTION_IDS, normalize_pattern_phrase
from apps.jobs.models import Job, UIAction

from .execution import agent_execution
from .local_commands import guide, human_organizer
from .models import CommandPattern, Message


class LocalCommandTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="guided-owner")
        self.other = get_user_model().objects.create_user(username="guided-other")
        self.reviewer = get_user_model().objects.create_user(username="guided-reviewer")
        for user in (self.owner, self.other, self.reviewer):
            PortalAccount.objects.create(
                user=user, role="reviewer" if user == self.reviewer else "organizer"
            )
        self.guide_url = reverse("assistant:guide")
        self.list_url = reverse("assistant:patterns")
        self.save_url = reverse("assistant:pattern_save")
        self.interpret_url = reverse("events:romeo_interpret")
        self.login(self.owner)
        for target in (
            "apps.assistant.provider._opener.open",
            "apps.assistant.free_harness.run_free_harness",
            "apps.jobs.services.enqueue",
        ):
            blocked = patch(
                target,
                side_effect=AssertionError("Local guidance must not call a model or create jobs"),
            )
            mocked = blocked.start()
            self.addCleanup(blocked.stop)
            self.addCleanup(mocked.assert_not_called)

    def login(self, user, client=None):
        client = client or self.client
        client.force_login(user)
        session = client.session
        session["portal_auth_version"] = 1
        session.save()

    def check_envelope(self, response, status_code=200):
        self.assertEqual(response.status_code, status_code)
        data = response.json()
        self.assertEqual(set(data), {"status", "reply", "draft", "intent", "follow_up"})
        self.assertIn(data["status"], {"ready", "clarify", "refused", "info"})
        self.assertLessEqual(len(data["reply"]), 280)
        self.assertLessEqual(len(data["draft"]), 300)
        self.assertIn(data["intent"], ACTION_IDS | {""})
        self.assertIn(data["follow_up"], {"", "person_name", "theme"})
        if data["status"] != "ready":
            self.assertEqual(data["draft"], "")
        if data["status"] != "clarify":
            self.assertEqual(data["follow_up"], "")
        return data

    def reply(self, text, context=""):
        return self.check_envelope(
            self.client.post(self.guide_url, {"text": text, "context": context})
        )

    def save(
        self, phrase="Llévame a mi agenda semanal", intent="calendar_open", reviewed="on", **kwargs
    ):
        return self.client.post(
            self.save_url,
            {"phrase": phrase, "intent": intent, "reviewed": reviewed, **kwargs},
            HTTP_ACCEPT="application/json",
        )

    def pattern(self, owner=None, phrase="mi vista semanal", intent="calendar_open"):
        return CommandPattern.objects.create(
            owner=owner or self.owner,
            phrase=phrase,
            normalized_phrase=normalize_pattern_phrase(phrase),
            intent=intent,
            reviewed_at=timezone.now(),
        )

    def assert_no_execution(self):
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(UIAction.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_six_actions_prepare_canonical_drafts_without_execution_or_user_names_in_reply(self):
        cases = [
            ("Hola Gica abre calendario", "calendar_open", "Abre calendario"),
            ("Muéstrame el directorio", "directory_open", "Abre directorio"),
            ("Quiero ver mis eventos", "events_open", "Abre eventos"),
            ("Pon modo claro", "theme_light", "Modo claro"),
            ("Pon modo oscuro", "theme_dark", "Modo oscuro"),
            ("Busca a Julio Romeo", "people_search", "Busca a Julio Romeo"),
        ]
        for text, intent, draft in cases:
            with self.subTest(text=text):
                data = self.reply(text)
                self.assertEqual(
                    (data["status"], data["intent"], data["draft"]), ("ready", intent, draft)
                )
                self.assertTrue(data["reply"].endswith("Identifiqué la orden."))
                self.assertNotIn("Julio Romeo", data["reply"])
        self.assertFalse(CommandPattern.objects.exists())
        self.assert_no_execution()

    def test_guidance_and_interpretation_are_read_only_sql_and_never_save_turns(self):
        with CaptureQueriesContext(connection) as captured:
            data = self.reply("busca")
        self.assertEqual(data["follow_up"], "person_name")
        self.assertTrue(captured.captured_queries)
        self.assertTrue(
            all(item["sql"].lstrip().upper().startswith("SELECT") for item in captured),
            captured.captured_queries,
        )
        with CaptureQueriesContext(connection) as interpreted:
            self.client.post(self.interpret_url, {"command": "mi vista semanal"})
        self.assertTrue(
            all(
                item["sql"].lstrip().upper().startswith(
                    ("SELECT", "SAVEPOINT", "RELEASE SAVEPOINT")
                )
                for item in interpreted
            ),
            interpreted.captured_queries,
        )
        self.assertFalse(CommandPattern.objects.exists())
        self.assert_no_execution()

    def test_social_replies_are_read_only_and_do_not_steal_pending_name_slots(self):
        for text in ("buenos días", "cómo estás", "gracias", "manda un saludo a Ana"):
            with self.subTest(text=text):
                data = self.reply(text)
                self.assertEqual((data["status"], data["intent"], data["draft"]), ("info", "", ""))
        self.assertTrue(self.reply("buenos días")["reply"].startswith("Buenos días"))
        self.assertIn("Ana", self.reply("manda un saludo a Ana")["reply"])
        self.assertEqual(self.reply("Buenos Días", "person_name")["draft"], "Busca a Buenos Días")
        self.assertEqual(self.reply("Chica", "person_name")["draft"], "Busca a Chica")
        self.assertEqual(self.reply("no mandes un saludo a Ana")["status"], "refused")
        self.assertNotEqual(self.reply("saluda a Ana y abre calendario")["status"], "ready")
        mixed = self.reply("buenos días abre calendario")
        self.assertEqual((mixed["status"], mixed["intent"], mixed["draft"]), ("ready", "calendar_open", "Abre calendario"))
        self.assertTrue(mixed["reply"].startswith("Buenos días."))
        self.assert_no_execution()

    def test_complete_courtesies_answer_in_every_context_without_becoming_a_name(self):
        for text in (
            "muchas gracias", "O k muchas gracias.", "Listo, muchas gracias.",
            "Gracias por tu ayuda", "no hay de qué", "hasta luego",
        ):
            for context in ("", "person_name", "theme"):
                with self.subTest(text=text, context=context):
                    data = self.reply(text, context)
                    self.assertEqual(
                        (data["status"], data["draft"], data["intent"], data["follow_up"]),
                        ("info", "", "", ""),
                    )
                    self.assertTrue(data["reply"])
        # A real person's name remains searchable when the search is explicit.
        self.assertEqual(self.reply("Busca a Gracias")["draft"], "Busca a Gracias")
        self.assertEqual(self.reply("Buenos Días", "person_name")["draft"], "Busca a Buenos Días")
        self.assertEqual(self.reply("Chica", "person_name")["draft"], "Busca a Chica")
        self.assertFalse(CommandPattern.objects.exists())
        self.assert_no_execution()

    def test_courtesy_does_not_hide_an_action_negation_quote_or_report(self):
        for text in (
            "O k muchas gracias y abre calendario", "no gracias abre calendario",
            '"muchas gracias"', "me dijeron muchas gracias", "si muchas gracias abre eventos",
        ):
            with self.subTest(text=text):
                data = self.reply(text)
                self.assertNotIn(data["status"], {"ready", "info"})
        self.assert_no_execution()

    def test_social_concepts_generalize_without_rewriting_search_names(self):
        for text in (
            "graccias", "oye te doy las graccias por ayudarme con esto",
            "perfecto de verdad muchas gracias Gica",
            "gracias por todo lo que me has ayudado", "gracias por abrir calendario",
            "Por tu ayuda, muchísimas graccias", "me has ayudado mucho gracias",
        ):
            for context in ("", "person_name", "theme"):
                with self.subTest(text=text, context=context):
                    result = self.reply(text, context)
                    self.assertEqual(
                        (result["status"], result["draft"], result["intent"], result["follow_up"]),
                        ("info", "", "", ""),
                    )
        for text in (
            "se llama Gracias", "el botón dice gracias", "no digas gracias",
            "gracias y abre calendario", "desgracias", "Gracia",
        ):
            with self.subTest(text=text):
                self.assertNotIn(self.reply(text)["status"], {"info", "ready"})
        self.assertEqual(self.reply("Busca a Graccias")["draft"], "Busca a Graccias")
        self.assertEqual(self.reply("Graccias Pérez", "person_name")["draft"], "Busca a Graccias Pérez")
        self.assert_no_execution()
        self.assertFalse(CommandPattern.objects.exists())

    def test_normalized_destinations_and_contextual_theme_prepare_the_same_six_actions(self):
        for text, action, draft in (
            ("calendarios", "calendar_open", "Abre calendario"),
            ("Hola Gica abre los caldenarios", "calendar_open", "Abre calendario"),
            ("abre los calendarios de eventos", "calendar_open", "Abre calendario"),
            ("evento", "events_open", "Abre eventos"),
            ("abre el evento", "events_open", "Abre eventos"),
            ("directorios", "directory_open", "Abre directorio"),
            ("abre un contacto", "directory_open", "Abre directorio"),
            ("pon temas claros", "theme_light", "Modo claro"),
            ("pon temas oscuros", "theme_dark", "Modo oscuro"),
            ("busca en los directorios a José", "people_search", "Busca a José"),
        ):
            with self.subTest(text=text):
                data = self.reply(text)
                self.assertEqual((data["status"], data["intent"], data["draft"]), ("ready", action, draft))
        for answer, draft in (("claras", "Modo claro"), ("temas oscuros", "Modo oscuro")):
            with self.subTest(answer=answer):
                data = self.reply(answer, "theme")
                self.assertEqual((data["status"], data["draft"]), ("ready", draft))
        for name in ("Caldenarios", "Evento", "Ana Directorios Pérez"):
            with self.subTest(name=name):
                self.assertEqual(self.reply("Busca a " + name)["draft"], "Busca a " + name)
                self.assertEqual(self.reply(name, "person_name")["draft"], "Busca a " + name)
        for phrase in (
            "no abras caldenarios", "si puedes abre eventos", "dijo que abra caldenarios",
            '"abre caldenarios"', "abre caldenarios y eventos", "crea el evento",
            "hablamos sobre los caldenarios", "busca eventos de Jorge", "agenda",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(self.reply(phrase)["status"], "ready")
        self.assertFalse(CommandPattern.objects.exists())
        self.assert_no_execution()

    def test_time_comes_from_the_clock_in_peru_without_reading_event_or_browser_time(self):
        # UTC midnight is still the preceding evening in Lima.
        with patch("apps.assistant.local_commands.timezone.now", return_value=datetime(2026, 11, 16, 0, 30, tzinfo=datetime_timezone.utc)):
            data = self.reply("me dices la hora")
        self.assertEqual(data["status"], "info")
        self.assertIn("19:30", data["reply"])
        self.assertIn("Perú", data["reply"])
        with patch("apps.assistant.local_commands.timezone.now", return_value=datetime(2026, 11, 16, 6, 5, tzinfo=datetime_timezone.utc)):
            data = self.reply("buenos días qué hora es")
        self.assertTrue(data["reply"].startswith("Buenos días."))
        self.assertIn("Es la 01:05", data["reply"])
        self.assert_no_execution()

    def test_history_paraphrases_and_explicit_topic_changes_keep_names_and_authority(self):
        for text in (
            'Puedes mandarle un saludo a Manu.', 'Quiero saludar.',
            'O buenas noches.', '¿Puedes decirme la hora?',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.reply(text)['status'], 'info')
        self.assertTrue(self.reply('O buenas noches.')['reply'].startswith('Buenas noches.'))
        self.assertIn('Manu', self.reply('Puedes mandarle un saludo a Manu.')['reply'])
        for text, context in (
            ('buenas noches', 'theme'), ('¿Puedes decirme la hora?', 'person_name'),
            ('Puedes mandarle un saludo a Ana', 'person_name'),
        ):
            with self.subTest(text=text, context=context):
                data = self.reply(text, context)
                self.assertEqual((data['status'], data['follow_up'], data['draft']), ('info', '', ''))
        self.assertEqual(self.reply('Chica', 'person_name')['draft'], 'Busca a Chica')
        self.assertEqual(self.reply('Buenos Días', 'person_name')['draft'], 'Busca a Buenos Días')
        self.assert_no_execution()

    def test_composed_vocabulary_reaches_guidance_without_learning_or_execution(self):
        for text, intent in (
            ("Hola chica abre eventos", "events_open"),
            ("Ahora calendario", "calendar_open"),
            ("Haz clic en el directorio por favor", "directory_open"),
            ("Muéstrame mis contactos", "directory_open"),
        ):
            with self.subTest(text=text):
                data = self.reply(text)
                self.assertEqual((data["status"], data["intent"]), ("ready", intent))
        self.assertEqual(self.reply("Hola Chica")["status"], "info")
        self.assertEqual(self.reply("Chica Pérez", "person_name")["draft"], "Busca a Chica Pérez")
        self.assertEqual(self.reply("agenda")["status"], "clarify")
        self.assertEqual(self.reply("no abras eventos")["status"], "refused")
        self.assertFalse(CommandPattern.objects.exists())
        self.assert_no_execution()

    def test_greeting_help_and_slots_are_stateless_without_executing(self):
        for text in ("Hola Gica", "ayuda", "¿Qué puedes hacer?", ""):
            self.assertEqual(self.reply(text)["status"], "info")
        person = self.reply("busca")
        self.assertEqual(person["follow_up"], "person_name")
        answer = self.reply("José O'Connor", "person_name")
        self.assertEqual((answer["status"], answer["draft"]), ("ready", "Busca a José O'Connor"))
        self.assertNotIn("Connor", answer["reply"])
        theme = self.reply("cambia tema")
        self.assertEqual(theme["follow_up"], "theme")
        self.assertEqual(self.reply("oscuro", "theme")["draft"], "Modo oscuro")
        self.assertEqual(self.reply("claro")["status"], "clarify")
        self.assert_no_execution()
        self.assertFalse(CommandPattern.objects.exists())

    def test_person_context_cannot_turn_urls_negations_quotes_or_other_actions_into_names(self):
        for text in (
            "no", "https://example.invalid", "abre calendario", "Ana y Luis", "si puedes",
            '"Jorge"', "Me dijeron que abra calendario", "a" * 101,
        ):
            with self.subTest(text=text):
                self.assertNotEqual(self.reply(text, "person_name")["status"], "ready")
        long_name = self.reply("a" * 295, "person_name")
        self.assertEqual((long_name["status"], long_name["follow_up"]), ("refused", ""))
        self.assert_no_execution()

    def test_authorized_invalid_payloads_keep_five_fields_and_do_not_echo_input(self):
        for text in ("a" * 301, "hola\n", "<script>alert(1)</script>", "ß" * 300):
            self.assertEqual(self.reply(text)["status"], "refused")
        for payload in (
            {"text": ["calendario", "directorio"]},
            {"text": "calendario", "context": "admin"},
            {"context": ""},
        ):
            self.check_envelope(self.client.post(self.guide_url, payload), 400)
        self.assert_no_execution()

    def test_review_required_and_json_errors_do_not_reflect_dangerous_phrase(self):
        for reviewed in ("", "false", "no", "0"):
            response = self.save(reviewed=reviewed)
            self.assertEqual(response.status_code, 400)
            self.assertIn("reviewed", response.json()["errors"])
        attack = "<script>private-fixture()</script>"
        response = self.save(phrase=attack)
        self.assertEqual(set(response.json()), {"ok", "errors"})
        self.assertFalse(response.json()["ok"])
        self.assertNotIn(attack, response.content.decode())
        self.assertFalse(CommandPattern.objects.exists())

    def test_same_reviewed_phrase_is_idempotent_and_normalized_variants_share_one_owner_row(self):
        first = self.save()
        self.assertEqual(
            first.json(), {"ok": True, "message": "Frase revisada guardada sólo para tu cuenta."}
        )
        pattern = CommandPattern.objects.get()
        before = pattern.reviewed_at
        self.assertEqual(self.save().status_code, 200)
        pattern.refresh_from_db()
        self.assertEqual(pattern.reviewed_at, before)
        self.assertEqual(self.save(phrase="LLÉVAME A MI AGENDA SEMANAL").status_code, 200)
        self.assertEqual(CommandPattern.objects.count(), 1)
        self.assertEqual(CommandPattern.objects.get().pk, pattern.pk)
        self.assert_no_execution()

    def test_approved_custom_phrase_resolves_only_for_owner_without_replacing_known_intent(self):
        self.assertEqual(self.save().status_code, 200)
        interpreted = self.client.post(
            self.interpret_url, {"command": "Llévame a mi agenda semanal"}
        ).json()
        self.assertEqual(
            (interpreted["status"], interpreted["action"]), ("understood", "calendar_open")
        )
        self.assertEqual(self.reply("Llévame a mi agenda semanal")["draft"], "Abre calendario")
        self.login(self.other)
        self.assertEqual(
            self.client.post(
                self.interpret_url, {"command": "Llévame a mi agenda semanal"}
            ).json()["status"],
            "clarify",
        )
        self.assertEqual(self.reply("Llévame a mi agenda semanal")["status"], "clarify")
        self.assert_no_execution()

    def test_canonical_intent_cannot_be_overridden_and_multiple_unsafe_patterns_are_rejected(self):
        wrong = self.save(phrase="abre calendario", intent="events_open")
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("intent", wrong.json()["errors"])
        for phrase in (
            "No abras calendario", "Gica ejecuta", "sí", "no", "Si puedes abre calendario",
            '"abre calendario"', "Me dijeron que abra calendario", "abre calendario y directorio",
            "busca claves API", "abre https://example.invalid", "abre\ncalendario",
            "abre calendario de noviembre",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.save(phrase=phrase).status_code, 400)
        self.assertFalse(CommandPattern.objects.exists())

    def test_learned_person_search_only_asks_for_name_and_never_fabricates_one(self):
        self.assertEqual(
            self.save(phrase="localizar a alguien", intent="people_search").status_code, 200
        )
        data = self.reply("localizar a alguien")
        self.assertEqual(
            (data["status"], data["follow_up"], data["draft"]), ("clarify", "person_name", "")
        )
        interpreted = self.client.post(
            self.interpret_url, {"command": "localizar a alguien"}
        ).json()
        self.assertEqual(
            (interpreted["status"], interpreted["action"], interpreted["query"]),
            ("clarify", None, ""),
        )
        self.assertEqual(self.reply("Julio Romeo", "person_name")["draft"], "Busca a Julio Romeo")
        self.assert_no_execution()

    def test_malformed_bank_and_existing_unsafe_rows_cannot_bypass_guardrails(self):
        self.pattern(phrase="no abras calendario")
        self.assertEqual(self.reply("no abras calendario")["status"], "refused")
        self.assertEqual(
            self.client.post(self.interpret_url, {"command": "no abras calendario"}).json()[
                "status"
            ],
            "refused",
        )
        self.pattern()
        with patch("apps.jobs.command_language._catalog", return_value=None):
            self.assertEqual(self.reply("mi vista semanal")["status"], "refused")
            self.assertEqual(
                self.client.post(self.interpret_url, {"command": "mi vista semanal"}).json()[
                    "status"
                ],
                "refused",
            )
            self.assertEqual(self.save().status_code, 400)
        self.assert_no_execution()

    def test_quota_is_per_owner_and_existing_review_still_saves_at_capacity(self):
        now = timezone.now()
        CommandPattern.objects.bulk_create([
            CommandPattern(
                owner=self.owner,
                phrase=f"mi frase {index}",
                normalized_phrase=f"mi frase {index}",
                intent="calendar_open",
                reviewed_at=now,
            )
            for index in range(200)
        ])
        self.assertEqual(self.save(phrase="una frase nueva").status_code, 400)
        self.assertEqual(self.save(phrase="mi frase 0").status_code, 200)
        self.assertEqual(CommandPattern.objects.filter(owner=self.owner).count(), 200)
        self.login(self.other)
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(CommandPattern.objects.filter(owner=self.other).count(), 1)

    def test_list_delete_and_supplied_owner_are_scoped_to_current_human(self):
        mine = self.pattern()
        foreign = self.pattern(owner=self.other, phrase="frase ajena privada")
        response = self.client.get(self.list_url)
        self.assertEqual(list(response.context["patterns"]), [mine])
        self.assertNotContains(response, "frase ajena privada")
        self.assertEqual(
            self.client.post(reverse("assistant:pattern_delete", args=[foreign.pk])).status_code,
            404,
        )
        self.assertTrue(CommandPattern.objects.filter(pk=foreign.pk).exists())
        self.assertEqual(self.save(owner=self.other.pk).status_code, 200)
        self.assertEqual(CommandPattern.objects.filter(owner=self.other).count(), 1)
        self.assertEqual(
            self.client.post(
                reverse("assistant:pattern_delete", args=[mine.pk]), HTTP_ACCEPT="application/json"
            ).status_code,
            200,
        )
        self.assertFalse(CommandPattern.objects.filter(pk=mine.pk).exists())

    def test_human_role_and_active_status_are_rechecked_and_agent_context_cannot_manage_memory(
        self,
    ):
        pattern = self.pattern()
        targets = [
            (self.guide_url, {"text": "calendario"}),
            (self.save_url, {"phrase": "mi frase", "intent": "calendar_open", "reviewed": "on"}),
            (reverse("assistant:pattern_delete", args=[pattern.pk]), {}),
        ]
        self.login(self.reviewer)
        for url, payload in targets:
            self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.login(self.owner)
        PortalAccount.objects.filter(user=self.owner).update(role="reviewer")
        with self.assertRaises(PermissionDenied):
            human_organizer(self.owner)
        PortalAccount.objects.filter(user=self.owner).update(role="organizer")
        self.owner.is_staff = self.owner.is_superuser = True
        self.owner.save()
        with agent_execution():
            for url, payload in targets:
                self.assertEqual(self.client.post(url, payload).status_code, 403)
            self.assertEqual(self.client.get(self.list_url).status_code, 403)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            guide(self.owner, "calendario")
        self.assertTrue(CommandPattern.objects.filter(pk=pattern.pk).exists())

    def test_csrf_authentication_methods_and_cache_policy(self):
        protected = Client(enforce_csrf_checks=True)
        self.login(self.owner, protected)
        pattern = self.pattern()
        for url in (
            self.guide_url, self.save_url, reverse("assistant:pattern_delete", args=[pattern.pk])
        ):
            self.assertEqual(protected.post(url, {}).status_code, 403)
            self.assertEqual(self.client.get(url).status_code, 405)
        response = protected.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        token = protected.cookies["csrftoken"].value
        response = protected.post(
            self.guide_url, {"text": "calendario", "csrfmiddlewaretoken": token}
        )
        self.check_envelope(response)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.logout()
        self.assertEqual(self.client.post(self.guide_url, {"text": "calendario"}).status_code, 302)

    def test_invalid_html_is_escaped_and_catalog_failure_has_five_field_reply(self):
        attack = '<script>alert("private-fixture")</script>'
        response = self.client.post(
            self.save_url, {"phrase": attack, "intent": "calendar_open", "reviewed": "on"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, attack, status_code=400)
        self.assertContains(response, "&lt;script&gt;", status_code=400)
        with patch(
            "apps.jobs.command_language.interpret",
            side_effect=RuntimeError("private model configuration"),
        ):
            response = self.client.post(self.guide_url, {"text": "calendario"})
        self.check_envelope(response, 503)
        self.assertNotIn("private", response.content.decode())
