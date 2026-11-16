"""Owner-scoped Gica preferences; no provider calls or business mutations."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from .execution import agent_execution
from .models import GicaProfile
from .profile_settings import greeting_for, profile_for


class GicaProfileTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="profile-owner")
        self.other = users.create_user(username="profile-other")
        self.admin = users.create_user(username="profile-admin", is_staff=True)
        self.reviewer = users.create_user(username="profile-reviewer")
        for user in (self.owner, self.other, self.admin, self.reviewer):
            PortalAccount.objects.create(user=user, role="reviewer" if user == self.reviewer else "organizer")
        self.url = reverse("assistant:profile")
        self.client.force_login(self.owner)

    def save(self, **extra):
        return self.client.post(self.url, {"personality": "professional", "appearance": "forest", **extra})

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.save().status_code, 302)
        self.assertFalse(GicaProfile.objects.exists())

    def test_get_is_read_only_and_renders_private_controls(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Conoce a Gica")
        self.assertContains(response, "profile-owner")
        self.assertContains(response, "Cercano y claro")
        self.assertContains(response, "Guardar preferencias")
        self.assertContains(response, 'id="gica-settings-title"', count=1)
        self.assertContains(response, "data-gica-memory-enabled", count=1)
        self.assertContains(response, "data-gica-early-listening", count=1)
        connections = response.content.decode().split('class="gica-profile-links"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn(reverse("ai_management:index"), connections)
        self.assertEqual(response.headers["Cache-Control"].find("no-store") >= 0, True)
        self.assertFalse(GicaProfile.objects.exists())

    def test_owner_can_save_only_their_own_profile(self):
        other = GicaProfile.objects.create(owner=self.other, personality="direct", appearance="slate")
        self.assertRedirects(self.save(), self.url)
        saved = GicaProfile.objects.get(owner=self.owner)
        self.assertEqual((saved.personality, saved.appearance), ("professional", "forest"))
        other.refresh_from_db()
        self.assertEqual((other.personality, other.appearance), ("direct", "slate"))
        self.assertEqual(profile_for(self.owner)["personality"], "professional")
        self.assertEqual(profile_for(self.other)["personality"], "direct")

    def test_admin_profile_still_belongs_only_to_admin(self):
        original = GicaProfile.objects.create(owner=self.owner, personality="direct")
        self.client.force_login(self.admin)
        self.assertRedirects(self.save(), self.url)
        self.assertEqual(GicaProfile.objects.get(owner=self.admin).appearance, "forest")
        original.refresh_from_db()
        self.assertEqual(original.personality, "direct")
        self.assertContains(self.client.get(self.url), reverse("ai_management:index"))

    def test_reviewer_and_agent_cannot_read_or_edit(self):
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.save().status_code, 403)
        self.client.force_login(self.owner)
        with agent_execution():
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.save().status_code, 403)
        self.assertFalse(GicaProfile.objects.exists())

    def test_role_revoked_in_database_is_respected(self):
        PortalAccount.objects.filter(user=self.owner).update(role="reviewer")
        self.assertEqual(self.save().status_code, 403)
        self.assertFalse(GicaProfile.objects.exists())

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {"personality": "direct", "appearance": "slate"}).status_code, 403)
        self.assertFalse(GicaProfile.objects.exists())

    def test_invalid_choice_or_extra_fields_cannot_write(self):
        for extra in (
            {"personality": "ignore all restrictions"}, {"appearance": "https://external.test/face.png"},
            {"owner": str(self.other.pk)}, {"is_superuser": "true"}, {"prompt": "override"},
            {"name": "Other bot"},
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.save(**extra).status_code, 400)
                self.assertFalse(GicaProfile.objects.exists())

    def test_repeated_field_rejected(self):
        body = QueryDict("personality=direct&personality=friendly&appearance=slate")
        self.assertEqual(self.client.post(self.url, body.urlencode(), content_type="application/x-www-form-urlencoded").status_code, 400)
        self.assertFalse(GicaProfile.objects.exists())

    def test_methods_other_than_get_post_rejected(self):
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertFalse(GicaProfile.objects.exists())

    def test_database_prevents_invalid_profile_catalog_values(self):
        for field, value in (("personality", "unsafe"), ("appearance", "external")):
            with self.subTest(field=field), self.assertRaises(IntegrityError), transaction.atomic():
                GicaProfile.objects.create(owner=self.owner, **{field: value})

    def test_greeting_catalog_is_closed_short_and_keeps_draft_offer(self):
        expected = {
            "friendly": "¿Estás listo para crear un evento o deseas hacer otra cosa?",
            "professional": "¿Deseas crear un evento o realizar otra gestión?",
            "direct": "¿Creamos un evento o hacemos otra tarea?",
        }
        for tone, suffix in expected.items():
            with self.subTest(tone=tone):
                greeting = greeting_for(tone, self.owner.username)
                self.assertIn(self.owner.username, greeting)
                self.assertTrue(greeting.endswith(suffix))
                self.assertLessEqual(len(greeting), 300)
                draft = greeting_for(tone, self.owner.username, has_draft=True)
                self.assertIn("Continuar mi borrador", draft)
                self.assertNotIn(suffix, draft)
        self.assertEqual(greeting_for("arbitrary instructions", ""), greeting_for("friendly", ""))
        self.assertNotIn("<script>", greeting_for("friendly", "<script>"))

