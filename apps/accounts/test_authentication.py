"""Portal authentication, password and revocable-session behavior.

These use Django's isolated test database and never call an AI provider.
"""

from datetime import timedelta

from django.contrib.auth import SESSION_KEY, authenticate, get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EventReviewAssignment, LoginAttemptWindow, PortalAccount


PASSWORD = "Prueba-Segura!2947"
NEW_PASSWORD = "Cambio-Privado!8364"
FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class IdentityResolutionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="adminjorge", email="jorge@example.test", password=PASSWORD,
        )

    def test_legacy_username_and_email_resolve_the_same_user(self):
        for identity in ("adminjorge", "ADMINJORGE", "jorge@example.test", "JORGE@EXAMPLE.TEST"):
            with self.subTest(identity=identity):
                self.assertEqual(authenticate(username=identity, password=PASSWORD), self.user)

    def test_a_users_email_matching_their_own_username_is_not_ambiguous(self):
        user = get_user_model().objects.create_user(
            username="one@example.test", email="one@example.test", password=PASSWORD,
        )
        self.assertEqual(authenticate(username="ONE@EXAMPLE.TEST", password=PASSWORD), user)

    def test_email_and_another_users_username_collision_fails_closed(self):
        get_user_model().objects.create_user(username="jorge@example.test", password=PASSWORD)
        self.assertIsNone(authenticate(username="jorge@example.test", password=PASSWORD))

    def test_duplicate_email_case_variants_fail_closed(self):
        get_user_model().objects.create_user(
            username="another", email="JORGE@EXAMPLE.TEST", password=PASSWORD,
        )
        self.assertIsNone(authenticate(username="jorge@example.test", password=PASSWORD))

    def test_duplicate_username_case_variants_fail_closed(self):
        get_user_model().objects.create_user(username="ADMINJORGE", password=PASSWORD)
        self.assertIsNone(authenticate(username="adminjorge", password=PASSWORD))

    def test_inactive_wrong_password_and_unknown_user_do_not_authenticate(self):
        self.assertIsNone(authenticate(username=self.user.username, password="incorrect"))
        self.assertIsNone(authenticate(username="unknown", password=PASSWORD))
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(authenticate(username=self.user.username, password=PASSWORD))

    def test_legacy_password_policy_does_not_lock_existing_users_out(self):
        self.user.set_password("legacy-short")
        self.user.save(update_fields=["password"])
        self.assertEqual(authenticate(username=self.user.username, password="legacy-short"), self.user)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, LOGIN_MAX_ATTEMPTS=50)
class LoginAndSessionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="adminjorge", email="jorge@example.test", password=PASSWORD,
        )
        self.profile, _ = PortalAccount.objects.update_or_create(
            user=self.user, defaults={"role": "organizer", "must_change_password": False},
        )

    def login(self, client=None, **extra):
        return (client or self.client).post(
            reverse("login"), {"username": self.user.username, "password": PASSWORD, **extra},
        )

    def test_login_accepts_email_and_stamps_session_version(self):
        response = self.client.post(reverse("login"), {
            "username": "JORGE@EXAMPLE.TEST", "password": PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertEqual(self.client.session["portal_auth_version"], self.profile.session_version)

    def test_untrusted_next_cannot_redirect_outside_the_portal(self):
        for target in ("https://attacker.example/steal", "//attacker.example/steal"):
            with self.subTest(target=target):
                self.client.logout()
                response = self.login(next=target)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("events:index"))

    def test_login_rejects_missing_csrf_and_does_not_authenticate(self):
        client = Client(enforce_csrf_checks=True)
        response = self.login(client=client)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(SESSION_KEY, client.session)

    def test_login_error_does_not_disclose_whether_identity_exists(self):
        errors = []
        for identity in (self.user.username, "nonexistent@example.test"):
            response = self.client.post(reverse("login"), {"username": identity, "password": "wrong"})
            self.assertEqual(response.status_code, 200)
            errors.append(list(response.context["form"].non_field_errors()))
        self.assertEqual(errors[0], errors[1])

    def test_failed_login_never_redisplays_the_password(self):
        response = self.client.post(reverse("login"), {
            "username": self.user.username, "password": "Never-Redisplay!1984",
        })
        self.assertNotContains(response, "Never-Redisplay!1984")
        self.assertNotIn("Never-Redisplay!1984", response.get("Location", ""))
        self.assertIn("no-store", response.get("Cache-Control", ""))

    @override_settings(LOGIN_MAX_ATTEMPTS=2)
    def test_repeated_attempts_are_throttled_before_authentication(self):
        for _ in range(2):
            self.client.post(reverse("login"), {"username": self.user.username, "password": "wrong"})
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotContains(response, PASSWORD, status_code=429)

    @override_settings(LOGIN_MAX_ATTEMPTS=2, LOGIN_WINDOW_SECONDS=300)
    def test_login_throttle_expires_instead_of_permanently_locking_the_user(self):
        for _ in range(2):
            self.client.post(reverse("login"), {"username": self.user.username, "password": "wrong"})
        self.assertEqual(self.login().status_code, 429)
        LoginAttemptWindow.objects.update(started_at=timezone.now() - timedelta(seconds=301))
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_login_throttle_storage_contains_no_plain_login_or_ip(self):
        self.client.post(reverse("login"), {
            "username": "private-login@example.test", "password": "Never-Store!5678",
        }, REMOTE_ADDR="192.0.2.74")
        windows = list(LoginAttemptWindow.objects.values())
        self.assertTrue(windows)
        stored = str(windows)
        for sensitive in ("private-login@example.test", "192.0.2.74", "Never-Store!5678"):
            self.assertNotIn(sensitive, stored)

    def test_session_version_change_revokes_an_existing_session(self):
        self.login()
        PortalAccount.objects.filter(pk=self.profile.pk).update(session_version=self.profile.session_version + 1)
        response = self.client.get(reverse("events:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_legacy_unstamped_session_can_bootstrap_only_version_one(self):
        self.client.force_login(self.user)
        self.assertNotIn("portal_auth_version", self.client.session)
        self.assertEqual(self.client.get(reverse("events:index")).status_code, 200)
        self.assertEqual(self.client.session["portal_auth_version"], 1)
        PortalAccount.objects.filter(pk=self.profile.pk).update(session_version=2)
        self.client.logout()
        self.client.force_login(self.user)
        self.assertNotIn("portal_auth_version", self.client.session)
        self.assertEqual(self.client.get(reverse("events:index")).status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_inactive_user_session_cannot_continue(self):
        self.login()
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.get(reverse("events:index"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_is_post_only(self):
        self.login()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, LOGIN_MAX_ATTEMPTS=50)
class MandatoryPasswordChangeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="new@example.test", email="new@example.test", password=PASSWORD,
        )
        self.profile, _ = PortalAccount.objects.update_or_create(
            user=self.user, defaults={"role": "organizer", "must_change_password": True},
        )
        self.client.login(username=self.user.username, password=PASSWORD)

    def test_new_account_is_forced_to_change_password_before_private_pages(self):
        for url in (reverse("events:index"), reverse("ai_management:index")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("password_change"))
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 200)

    def test_new_password_has_at_least_sixteen_characters_and_no_echo(self):
        response = self.client.post(reverse("password_change"), {
            "old_password": PASSWORD,
            "new_password1": "Short-42!", "new_password2": "Short-42!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["new_password2"])
        self.assertNotContains(response, "Short-42!")
        self.assertIn("no-store", response.get("Cache-Control", ""))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.must_change_password)

    def test_password_change_keeps_only_current_session_valid(self):
        other = Client()
        other.login(username=self.user.username, password=PASSWORD)
        old_epoch = self.profile.session_version
        old_version = self.profile.version
        response = self.client.post(reverse("password_change"), {
            "old_password": PASSWORD,
            "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.profile.must_change_password)
        self.assertGreater(self.profile.version, old_version)
        self.assertGreater(self.profile.session_version, old_epoch)
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertEqual(self.client.session["portal_auth_version"], self.profile.session_version)
        self.assertEqual(self.client.get(reverse("events:index")).status_code, 200)
        self.assertEqual(other.get(reverse("events:index")).status_code, 302)
        self.assertNotIn(SESSION_KEY, other.session)
        self.assertNotIn(NEW_PASSWORD, response.get("Location", ""))

    def test_reviewers_first_password_change_preserves_assigned_event_access(self):
        from apps.events.services import create_event

        owner = get_user_model().objects.create_user(username="event-owner", password=PASSWORD)
        event = create_event(actor=owner, title="Evento para revisar", brief="Ficha autorizada para revisión")
        self.profile.role = "reviewer"
        self.profile.save(update_fields=["role"])
        access_version = self.profile.access_version
        EventReviewAssignment.objects.create(
            event=event, reviewer=self.user, assigned_by=owner, reviewer_version=access_version,
        )
        response = self.client.post(reverse("password_change"), {
            "old_password": PASSWORD, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.access_version, access_version)
        detail_url = reverse("events:detail", kwargs={"event_id": event.pk})
        self.assertContains(self.client.get(detail_url), "Evento para revisar")

    def test_wrong_current_password_cannot_clear_the_mandatory_change(self):
        response = self.client.post(reverse("password_change"), {
            "old_password": "wrong", "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(self.profile.must_change_password)
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_forced_password_change_does_not_prevent_logout(self):
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)
