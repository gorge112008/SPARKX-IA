"""Portal account administration and assigned-event authorization contracts."""

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_management.models import AIAccount, AIUsage
from apps.assistant.models import Message
from apps.events.models import Event
from apps.events.services import create_event, require_event_owner, update_event
from apps.jobs.models import Job
from apps.planning.models import TaskProgressChange
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan

from .models import EventReviewAssignment, PortalAccount


PASSWORD = "Prueba-Segura!2947"
INITIAL_PASSWORD = "Inicial-Aleatoria!9257"
FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def portal_user(username, role="organizer", **kwargs):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD, **kwargs)
    PortalAccount.objects.update_or_create(user=user, defaults={"role": role, "must_change_password": False})
    return user


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class AccountAdministrationTests(TestCase):
    def setUp(self):
        self.admin = portal_user("portal-admin", role="admin", email="admin@example.test")
        self.organizer = portal_user("organizer", email="organizer@example.test")
        self.reviewer = portal_user("reviewer", role="reviewer", email="reviewer@example.test")
        self.client.force_login(self.admin)

    def create_data(self, **extra):
        return {
            "full_name": "Nueva Organizadora", "email": "new@example.test",
            "role": "organizer", "password": INITIAL_PASSWORD, **extra,
        }

    def update_url(self, user=None):
        return reverse("accounts:update_user", kwargs={"user_id": (user or self.organizer).pk})

    def update_data(self, user=None, **extra):
        profile = PortalAccount.objects.get(user=user or self.organizer)
        return {"action": "role", "role": "reviewer", "expected_version": profile.version, **extra}

    def test_user_management_requires_login_and_administrator_role(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:users"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        for user in (self.organizer, self.reviewer):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertEqual(self.client.get(reverse("accounts:users")).status_code, 403)
                self.assertEqual(self.client.post(reverse("accounts:create_user"), self.create_data()).status_code, 403)
                self.assertEqual(self.client.post(self.update_url(), self.update_data()).status_code, 403)

    def test_administrator_page_is_private_and_does_not_expose_password_hashes(self):
        response = self.client.get(reverse("accounts:users"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "organizer@example.test")
        self.assertNotContains(response, self.organizer.password)
        self.assertIn("no-store", response.get("Cache-Control", ""))

    def test_creating_an_account_hashes_password_and_requires_a_change(self):
        response = self.client.post(reverse("accounts:create_user"), self.create_data())
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email="new@example.test")
        profile = PortalAccount.objects.get(user=user)
        self.assertEqual(user.username, "new@example.test")
        self.assertTrue(user.check_password(INITIAL_PASSWORD))
        self.assertNotEqual(user.password, INITIAL_PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(profile.role, "organizer")
        self.assertTrue(profile.must_change_password)
        self.assertNotIn(INITIAL_PASSWORD, response.get("Location", ""))
        self.assertNotContains(self.client.get(response.url), INITIAL_PASSWORD)
        self.assertIn("no-store", response.get("Cache-Control", ""))

    def test_portal_admin_is_not_a_django_superuser_or_staff_member(self):
        response = self.client.post(reverse("accounts:create_user"), self.create_data(
            role="admin", is_staff="1", is_superuser="1",
        ))
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email="new@example.test")
        self.assertEqual(user.portal_account.role, "admin")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotContains(self.client.get(response.url), INITIAL_PASSWORD)

    def test_invalid_or_weak_creation_does_not_write_or_echo_password(self):
        before = get_user_model().objects.count()
        for changes in ({"password": "short"}, {"role": "superuser"}, {"email": "not-an-email"}):
            with self.subTest(changes=changes):
                response = self.client.post(reverse("accounts:create_user"), self.create_data(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertNotContains(response, INITIAL_PASSWORD, status_code=400)
                self.assertEqual(get_user_model().objects.count(), before)

    def test_case_insensitive_existing_email_and_username_cannot_be_reused(self):
        before = get_user_model().objects.count()
        get_user_model().objects.create_user(username="legacy@example.test", password=PASSWORD)
        for email in ("ORGANIZER@EXAMPLE.TEST", "LEGACY@EXAMPLE.TEST"):
            with self.subTest(email=email):
                response = self.client.post(reverse("accounts:create_user"), self.create_data(email=email))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), before + 1)

    def test_mutations_are_post_only_and_csrf_protected(self):
        self.assertEqual(self.client.get(reverse("accounts:create_user")).status_code, 405)
        self.assertEqual(self.client.get(self.update_url()).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        before = get_user_model().objects.count()
        self.assertEqual(client.post(reverse("accounts:create_user"), self.create_data()).status_code, 403)
        self.assertEqual(client.post(self.update_url(), self.update_data()).status_code, 403)
        self.assertEqual(get_user_model().objects.count(), before)

    def test_changing_a_role_versions_the_profile_and_revokes_its_sessions(self):
        victim = Client()
        victim.force_login(self.organizer)
        victim.get(reverse("events:index"))
        old = PortalAccount.objects.get(user=self.organizer)
        response = self.client.post(self.update_url(), self.update_data())
        self.assertEqual(response.status_code, 302)
        current = PortalAccount.objects.get(user=self.organizer)
        self.assertEqual(current.role, "reviewer")
        self.assertGreater(current.version, old.version)
        self.assertGreater(current.session_version, old.session_version)
        self.assertEqual(victim.get(reverse("events:index")).status_code, 302)

    def test_stale_role_change_conflicts_without_overwriting(self):
        data = self.update_data()
        self.assertEqual(self.client.post(self.update_url(), data).status_code, 302)
        profile = PortalAccount.objects.get(user=self.organizer)
        snapshot = (profile.role, profile.version, profile.session_version)
        response = self.client.post(self.update_url(), {**data, "role": "admin"})
        self.assertEqual(response.status_code, 409)
        profile.refresh_from_db()
        self.assertEqual((profile.role, profile.version, profile.session_version), snapshot)

    def test_missing_or_invalid_version_cannot_update_account(self):
        for version in (None, "not-int", 0):
            with self.subTest(version=version):
                data = self.update_data(expected_version=version)
                if version is None:
                    del data["expected_version"]
                self.assertEqual(self.client.post(self.update_url(), data).status_code, 400)
        self.assertEqual(PortalAccount.objects.get(user=self.organizer).role, "organizer")

    def test_status_change_disables_access_and_versions_the_account(self):
        old = PortalAccount.objects.get(user=self.organizer)
        response = self.client.post(self.update_url(), self.update_data(action="status", is_active="0"))
        self.assertEqual(response.status_code, 302)
        self.organizer.refresh_from_db()
        profile = PortalAccount.objects.get(user=self.organizer)
        self.assertFalse(self.organizer.is_active)
        self.assertGreater(profile.session_version, old.session_version)
        self.assertGreater(profile.version, old.version)

    def test_administrator_cannot_deactivate_or_demote_self(self):
        for changes in ({"action": "status", "is_active": "0"}, {"role": "reviewer"}):
            with self.subTest(changes=changes):
                response = self.client.post(self.update_url(self.admin), self.update_data(self.admin, **changes))
                self.assertIn(response.status_code, (400, 403))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(PortalAccount.objects.get(user=self.admin).role, "admin")

    def test_staff_and_superuser_accounts_are_protected_from_portal_changes(self):
        staff = portal_user("legacy-staff", role="admin", is_staff=True)
        for changes in ({"role": "reviewer"}, {"action": "status", "is_active": "0"}):
            with self.subTest(changes=changes):
                response = self.client.post(self.update_url(staff), self.update_data(staff, **changes))
                self.assertIn(response.status_code, (400, 403))
        staff.refresh_from_db()
        self.assertTrue(staff.is_active)
        self.assertTrue(staff.is_staff)
        self.assertEqual(PortalAccount.objects.get(user=staff).role, "admin")


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class AssignedReviewerTests(TestCase):
    def setUp(self):
        self.admin = portal_user("access-admin", role="admin")
        self.owner = portal_user("event-owner")
        self.other = portal_user("other-owner")
        self.reviewer = portal_user("assigned-reviewer", role="reviewer")
        self.event = create_event(actor=self.owner, title="Evento asignado visible", brief="Ficha confirmada del seminario")
        self.foreign = create_event(actor=self.other, title="Evento ajeno secreto", brief="Contexto privado ajeno")
        candidate = create_candidate(
            event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision,
        )
        self.plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        self.pending = create_candidate(
            event=self.event, actor=self.owner,
            payload={**valid_plan(), "summary": "BORRADOR PRIVADO NO COMPARTIDO"},
            base_revision=self.event.revision, base_plan_id=self.plan.pk,
        )
        Message.objects.create(event=self.event, role="user", content="CONVERSACION PRIVADA DEL ORGANIZADOR")
        EventReviewAssignment.objects.create(
            event=self.event, reviewer=self.reviewer, assigned_by=self.admin,
            reviewer_version=self.reviewer.portal_account.access_version,
        )
        self.client.force_login(self.reviewer)

    def event_url(self, name="detail", **kwargs):
        return reverse("events:" + name, kwargs={"event_id": self.event.pk, **kwargs})

    def assignment_url(self):
        return reverse("accounts:event_reviewers", kwargs={"event_id": self.event.pk})

    def effect_snapshot(self):
        return (
            Event.objects.count(), Job.objects.count(), AIUsage.objects.count(), AIAccount.objects.count(),
            Message.objects.count(), TaskProgressChange.objects.count(),
        )

    def test_reviewer_index_and_calendar_only_show_assigned_events(self):
        for url in (reverse("events:index"), reverse("events:calendar")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Evento ajeno secreto")
        self.assertContains(self.client.get(reverse("events:index")), "Evento asignado visible")
        url = reverse("events:detail", kwargs={"event_id": self.foreign.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_assigned_detail_exposes_approved_plan_but_not_private_work(self):
        before = self.effect_snapshot()
        response = self.client.get(self.event_url())
        self.assertContains(response, "Evento asignado visible")
        self.assertContains(response, "Apertura")
        self.assertNotContains(response, "BORRADOR PRIVADO NO COMPARTIDO")
        self.assertNotContains(response, "CONVERSACION PRIVADA DEL ORGANIZADOR")
        self.assertNotContains(response, self.event_url("generate"))
        self.assertNotContains(response, self.event_url("chat"))
        self.assertNotContains(response, self.event_url("task_progress"))
        self.assertNotContains(response, self.event_url("edit"))
        self.assertEqual(self.effect_snapshot(), before)

    def test_reviewer_cannot_reach_edit_interview_or_account_assignment(self):
        for url in (
            reverse("events:create"), self.event_url("edit"), self.event_url("interview"),
            self.assignment_url(), reverse("accounts:users"),
        ):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (403, 404))

    def test_reviewer_forged_posts_cannot_change_event_plan_or_finances(self):
        before = self.effect_snapshot()
        original_revision = self.event.revision
        posts = (
            (reverse("events:create"), {"title": "No autorizado", "brief": "Texto no autorizado"}),
            (self.event_url("edit"), {"title": "Sobrescrito", "brief": "Cambio no autorizado"}),
            (self.event_url("interview"), {"expected_revision": original_revision, "question_key": "objective", "status": "confirmed", "value": "Cambiar"}),
            (self.event_url("generate"), {"expected_revision": original_revision, "idempotency_key": str(uuid.uuid4())}),
            (self.event_url("chat"), {"content": "Acción no autorizada", "idempotency_key": str(uuid.uuid4())}),
            (self.event_url("task_progress"), {"task_id": "t1", "status": "completed", "expected_version": 0}),
            (self.event_url("approve", candidate_id=self.pending.pk), {}),
            (self.event_url("reject", candidate_id=self.pending.pk), {}),
        )
        for url, data in posts:
            with self.subTest(url=url):
                self.assertIn(self.client.post(url, data).status_code, (403, 404))
        self.event.refresh_from_db()
        self.pending.refresh_from_db()
        self.assertEqual(self.event.title, "Evento asignado visible")
        self.assertEqual(self.event.revision, original_revision)
        self.assertEqual(self.pending.status, "pending")
        self.assertEqual(self.effect_snapshot(), before)

    def test_every_ai_management_page_is_denied_to_reviewers_without_side_effects(self):
        before = self.effect_snapshot()
        for name in ("index", "providers", "profile_create", "budget", "calculator", "compare", "usage"):
            url = reverse("ai_management:" + name)
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertEqual(self.effect_snapshot(), before)

    def test_reviewer_has_no_service_write_authority_even_for_previously_owned_event(self):
        owned_before_role_change = Event.objects.create(
            owner=self.reviewer, title="Antiguo evento propio", brief="Conservar sin permiso de escritura",
        )
        with self.assertRaises(PermissionDenied):
            create_event(actor=self.reviewer, title="No permitido", brief="Nuevo evento")
        with self.assertRaises(PermissionDenied):
            require_event_owner(owned_before_role_change, self.reviewer)
        with self.assertRaises(PermissionDenied):
            update_event(event_id=owned_before_role_change.pk, actor=self.reviewer, title="Cambio")

    def test_revoked_assignment_immediately_removes_read_access(self):
        EventReviewAssignment.objects.filter(event=self.event, reviewer=self.reviewer).delete()
        self.assertEqual(self.client.get(self.event_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("events:index")), "Evento asignado visible")

    def test_old_grant_does_not_revive_after_reviewer_account_version_changes(self):
        profile = PortalAccount.objects.get(user=self.reviewer)
        PortalAccount.objects.filter(pk=profile.pk).update(
            session_version=profile.session_version + 1, access_version=profile.access_version + 1,
        )
        self.client.logout()
        response = self.client.post(reverse("login"), {
            "username": self.reviewer.username, "password": PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(self.event_url()).status_code, 404)
        EventReviewAssignment.objects.filter(event=self.event, reviewer=self.reviewer).update(
            reviewer_version=profile.access_version + 1,
        )
        self.assertEqual(self.client.get(self.event_url()).status_code, 200)

    def test_organizer_can_manage_only_their_own_event_reviewers(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.assignment_url()).status_code, 200)
        self.assertEqual(self.client.post(self.assignment_url(), {
            "reviewers": [self.reviewer.pk], "expected_version": self.event.review_access_version,
        }).status_code, 302)
        foreign_access_url = reverse("accounts:event_reviewers", kwargs={"event_id": self.foreign.pk})
        self.assertEqual(self.client.get(foreign_access_url).status_code, 404)
        self.assertEqual(self.client.post(foreign_access_url, {
            "reviewers": [self.reviewer.pk], "expected_version": self.foreign.review_access_version,
        }).status_code, 404)
        self.assertEqual(self.client.get(reverse("events:detail", kwargs={"event_id": self.foreign.pk})).status_code, 404)

    def test_admin_does_not_gain_assignment_access_to_another_organizers_event(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.assignment_url()).status_code, 404)
        self.assertEqual(self.client.post(self.assignment_url(), {
            "reviewers": [], "expected_version": self.event.review_access_version,
        }).status_code, 404)
        self.assertTrue(EventReviewAssignment.objects.filter(event=self.event, reviewer=self.reviewer).exists())

    def test_owner_assigns_only_active_reviewers_without_changing_event_revision(self):
        second = portal_user("second-reviewer", role="reviewer")
        self.client.force_login(self.owner)
        before_revision = self.event.revision
        response = self.client.post(self.assignment_url(), {
            "reviewers": [second.pk], "expected_version": self.event.review_access_version,
        })
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, before_revision)
        self.assertTrue(EventReviewAssignment.objects.filter(event=self.event, reviewer=second).exists())
        self.assertFalse(EventReviewAssignment.objects.filter(event=self.event, reviewer=self.reviewer).exists())
        second_client = Client()
        second_client.force_login(second)
        self.assertEqual(second_client.get(self.event_url()).status_code, 200)

    def test_stale_assignment_update_returns_conflict_and_preserves_current_grants(self):
        self.client.force_login(self.owner)
        version = self.event.review_access_version
        self.assertEqual(self.client.post(self.assignment_url(), {
            "reviewers": [], "expected_version": version,
        }).status_code, 302)
        response = self.client.post(self.assignment_url(), {
            "reviewers": [self.reviewer.pk], "expected_version": version,
        })
        self.assertEqual(response.status_code, 409)
        self.assertFalse(EventReviewAssignment.objects.filter(event=self.event).exists())

    def test_assignment_rejects_nonreviewer_inactive_and_cross_role_injection(self):
        inactive = portal_user("inactive-reviewer", role="reviewer", is_active=False)
        self.client.force_login(self.owner)
        for user in (self.owner, self.admin, inactive):
            with self.subTest(user=user.username):
                response = self.client.post(self.assignment_url(), {
                    "reviewers": [user.pk], "expected_version": self.event.review_access_version,
                })
                self.assertEqual(response.status_code, 400)
                self.assertFalse(EventReviewAssignment.objects.filter(event=self.event, reviewer=user).exists())

    def test_assignment_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(self.assignment_url(), {
            "reviewers": [], "expected_version": self.event.review_access_version,
        })
        self.assertEqual(response.status_code, 403)
        self.assertTrue(EventReviewAssignment.objects.filter(event=self.event, reviewer=self.reviewer).exists())
