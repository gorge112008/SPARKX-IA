"""Integrity of the private manual guides; requires no database or provider."""
from dataclasses import FrozenInstanceError
import re
from unittest import TestCase
from urllib.parse import urlsplit

from .catalog import (
    GROUPS,
    ITEMS,
    OPTIONAL_KEYS,
    ChecklistConfirmation,
    ChecklistLink,
)


class ChecklistGuideCatalogTests(TestCase):
    def test_persisted_item_and_group_keys_keep_their_original_meaning(self):
        expected = {
            "conexion": (
                "creditos_api", "credencial_privada", "presupuesto_ia",
                "prueba_recorrido",
            ),
            "demo": ("supuestos_gica", "revision_usuario", "demo_voz"),
            "despliegue": (
                "servicios_vps", "acceso_ssh", "password_publico",
                "datos_participantes",
            ),
            "concurso": (
                "equipo_contribuciones", "horarios_concurso",
                "repositorio_licencia", "entrega_ensayo",
            ),
        }
        self.assertEqual(
            {group.key: tuple(item.key for item in group.items) for group in GROUPS},
            expected,
        )
        item_keys = [item.key for group in GROUPS for item in group.items]
        self.assertEqual(len(item_keys), len(set(item_keys)))
        self.assertEqual(set(ITEMS), set(item_keys))
        self.assertEqual(len(GROUPS), len({group.key for group in GROUPS}))
        self.assertEqual(set(OPTIONAL_KEYS), {
            "demo_voz", "servicios_vps", "acceso_ssh", "password_publico",
            "datos_participantes",
        })

    def test_every_guide_has_steps_and_specific_confirmation_keys(self):
        confirmation_keys = []
        for item in ITEMS.values():
            with self.subTest(item=item.key):
                self.assertIsInstance(item.steps, tuple)
                self.assertGreaterEqual(len(item.steps), 2)
                self.assertTrue(all(isinstance(step, str) and step.strip() for step in item.steps))
                self.assertIsInstance(item.confirmations, tuple)
                self.assertGreaterEqual(len(item.confirmations), 2)
                self.assertLessEqual(len(item.confirmations), 4)
                for confirmation in item.confirmations:
                    self.assertIsInstance(confirmation, ChecklistConfirmation)
                    self.assertRegex(confirmation.key, r"^[a-z][a-z0-9_]{1,95}$")
                    self.assertTrue(confirmation.key.startswith(item.key + "_"))
                    self.assertTrue(confirmation.label.strip())
                    confirmation_keys.append(confirmation.key)
        self.assertEqual(len(confirmation_keys), len(set(confirmation_keys)))

    def test_instruction_and_confirmation_text_has_no_rendered_html(self):
        for item in ITEMS.values():
            with self.subTest(item=item.key):
                texts = (*item.steps, *(confirmation.label for confirmation in item.confirmations))
                for value in texts:
                    self.assertFalse(re.search(r"<\s*/?\s*[a-zA-Z]", value))

    def test_external_links_are_fixed_https_documentation_destinations(self):
        allowed_hosts = {
            "developers.openai.com", "platform.openai.com", "docs.github.com",
        }
        for item in ITEMS.values():
            with self.subTest(item=item.key):
                self.assertIsInstance(item.links, tuple)
                for link in item.links:
                    self.assertIsInstance(link, ChecklistLink)
                    self.assertTrue(link.label.strip())
                    parsed = urlsplit(link.url)
                    self.assertEqual(parsed.scheme, "https")
                    self.assertIn(parsed.hostname, allowed_hosts)
                    self.assertIsNone(parsed.username)
                    self.assertIsNone(parsed.password)
                    self.assertIsNone(parsed.port)
                    self.assertFalse(parsed.query)
                    self.assertFalse(parsed.fragment)
                    self.assertNotIn("\\", link.url)

    def test_nested_metadata_is_immutable(self):
        item = ITEMS["creditos_api"]
        with self.assertRaises(FrozenInstanceError):
            item.steps = ()
        with self.assertRaises(FrozenInstanceError):
            item.confirmations[0].label = "changed"
        with self.assertRaises(FrozenInstanceError):
            item.links[0].url = "https://example.com/"
        with self.assertRaises(TypeError):
            ITEMS["creditos_api"] = item

    def test_completion_declarations_do_not_claim_external_verification(self):
        # These distinctions must remain visible even if the status is completed.
        credits = ITEMS["creditos_api"]
        self.assertIn("no consulta ni verifica", credits.description)
        self.assertIn("no cambia ni autoriza", ITEMS["presupuesto_ia"].description)
        delivery = ITEMS["entrega_ensayo"]
        self.assertIn("no publica ni env", delivery.description)
        self.assertTrue(any("recepci" in step for step in delivery.steps))
        self.assertTrue(any("recepcion" in row.key for row in delivery.confirmations))
