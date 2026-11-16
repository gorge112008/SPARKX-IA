from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings

from apps.events.models import Event

from .access import can_organize, can_view_event, get_role, is_portal_admin, visible_events
from .models import AdminRosterLock, EventReviewAssignment, PortalAccount
from .services import create_portal_user, normalize_identifier, set_event_reviewers, update_portal_user


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PortalAccountCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        AdminRosterLock.objects.get_or_create(pk=1)
        users = get_user_model()
        cls.admin = users.objects.create_user(username="portal-admin", email="admin@example.test")
        cls.organizer = users.objects.create_user(username="portal-owner", email="owner@example.test")
        cls.other = users.objects.create_user(username="another-owner", email="other@example.test")
        cls.reviewer = users.objects.create_user(username="portal-reviewer", email="reviewer@example.test")
        cls.technical = users.objects.create_superuser(username="technical-root", email="root@example.test", password="technical-test-password")
        PortalAccount.objects.create(user=cls.admin, role=PortalAccount.Role.ADMIN)
        PortalAccount.objects.create(user=cls.organizer)
        PortalAccount.objects.create(user=cls.reviewer, role=PortalAccount.Role.REVIEWER)
        cls.event = Event.objects.create(owner=cls.organizer, title="Evento asignable", brief="Prueba de permisos")
        cls.other_event = Event.objects.create(owner=cls.other, title="Evento privado", brief="Prueba de aislamiento")

    def create(self, **values):
        return create_portal_user(**{
            "actor": self.admin, "full_name": "Persona de prueba", "email": "new-account@example.test",
            "role": PortalAccount.Role.ORGANIZER, "password": "A-test-password-4!long",
            **values,
        })

    def assign(self, ids=None, **values):
        self.event.refresh_from_db()
        return set_event_reviewers(**{
            "actor": self.organizer, "event_id": self.event.pk,
            "reviewer_ids": [self.reviewer.pk] if ids is None else ids,
            "expected_version": self.event.review_access_version, **values,
        })

    def update(self, user=None, **values):
        user = user or self.reviewer
        profile = PortalAccount.objects.get(user=user)
        return update_portal_user(**{
            "actor": self.admin, "user_id": user.pk, "expected_version": profile.version,
            "role": profile.role, "is_active": user.is_active, **values,
        })

    def test_legacy_role_reads_create_no_profiles(self):
        before = PortalAccount.objects.count()
        self.assertEqual(get_role(self.other), PortalAccount.Role.ORGANIZER)
        self.assertTrue(can_organize(self.other))
        self.assertFalse(is_portal_admin(self.other))
        self.assertEqual(PortalAccount.objects.count(), before)
        self.assertIsNone(get_role(AnonymousUser()))
        self.assertFalse(can_organize(AnonymousUser()))

    def test_technical_admin_role_cannot_be_reduced_by_portal_profile(self):
        PortalAccount.objects.create(user=self.technical, role=PortalAccount.Role.REVIEWER)
        self.assertTrue(is_portal_admin(self.technical))
        self.assertTrue(can_organize(self.technical))
        self.assertEqual(get_role(self.technical), PortalAccount.Role.ADMIN)

    def test_portal_admin_is_independent_of_technical_permissions(self):
        user = self.create(role=PortalAccount.Role.ADMIN)
        self.assertTrue(is_portal_admin(user))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.groups.count(), 0)
        self.assertEqual(user.user_permissions.count(), 0)

    def test_new_account_hashes_password_and_requires_initial_change(self):
        password = "A-test-password-4!long"
        user = self.create(password=password)
        self.assertEqual(user.username, "new-account@example.test")
        self.assertEqual(user.first_name, "Persona de prueba")
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.check_password(password))
        profile = PortalAccount.objects.get(user=user)
        self.assertTrue(profile.must_change_password)
        self.assertEqual((profile.version, profile.session_version, profile.access_version), (1, 1, 1))
        self.assertFalse(any(password in str(value) for value in vars(profile).values()))

    def test_manual_password_policy_and_standard_validators_are_enforced(self):
        for password in ("short", "1234567890123456", "q" * 129):
            with self.subTest(password_length=len(password)), self.assertRaises(ValidationError):
                self.create(password=password)
        self.assertFalse(get_user_model().objects.filter(email="new-account@example.test").exists())

    def test_unauthorized_or_stale_admin_cannot_create_users(self):
        for actor in (self.organizer, self.reviewer, AnonymousUser()):
            with self.subTest(actor=str(actor)), self.assertRaises(PermissionDenied):
                self.create(actor=actor)
        PortalAccount.objects.filter(user=self.admin).update(role=PortalAccount.Role.ORGANIZER)
        with self.assertRaises(PermissionDenied):
            self.create(actor=self.admin)

    def test_case_and_cross_namespace_collisions_are_rejected(self):
        users = get_user_model()
        users.objects.create_user(username="CaseUser", email="SharedAddress@example.test")
        for values in (
            {"email": "sharedaddress@EXAMPLE.TEST"},
            {"email": "unique@example.test", "username": "caseuser"},
            {"email": "unique@example.test", "username": "SHAREDADDRESS@example.test"},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.create(**values)
        users.objects.create_user(username="alias@example.test", email="another@example.test")
        with self.assertRaises(ValidationError):
            self.create(email="ALIAS@example.test")

    def test_unicode_normalization_cannot_create_second_alias(self):
        get_user_model().objects.create_user(username="Straße", email="unicode@example.test")
        with self.assertRaises(ValidationError):
            self.create(username="STRASSE")
        self.assertEqual(normalize_identifier(" ＡＤＭＩＮ "), "admin")

    def test_invalid_account_inputs_make_no_partial_user(self):
        for values in ({"full_name": " "}, {"full_name": "N" * 151}, {"email": "invalid"},
                       {"email": "a" * 141 + "@example.test"}, {"role": "superuser"}):
            before = get_user_model().objects.count()
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.create(**values)
            self.assertEqual(get_user_model().objects.count(), before)

    def test_update_uses_cas_and_increments_session_epoch_only_on_change(self):
        unchanged = self.update()
        profile = PortalAccount.objects.get(user=unchanged)
        self.assertEqual((profile.version, profile.session_version, profile.access_version), (1, 1, 1))
        updated = self.update(role=PortalAccount.Role.ORGANIZER)
        profile.refresh_from_db()
        self.assertEqual((profile.role, profile.version, profile.session_version, profile.access_version), (PortalAccount.Role.ORGANIZER, 2, 2, 2))
        with self.assertRaisesMessage(ValidationError, "otra pestaña"):
            self.update(user=updated, expected_version=1, role=PortalAccount.Role.REVIEWER)
        profile.refresh_from_db()
        self.assertEqual((profile.version, profile.session_version, profile.access_version), (2, 2, 2))

    def test_cannot_self_disable_or_remove_own_admin_role(self):
        for values in ({"is_active": False}, {"role": PortalAccount.Role.ORGANIZER}):
            with self.subTest(values=values), self.assertRaises(PermissionDenied):
                self.update(user=self.admin, **values)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(is_portal_admin(self.admin))

    def test_last_portal_admin_stays_active_even_without_technical_admin(self):
        get_user_model().objects.filter(pk=self.technical.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.update(user=self.admin, is_active=False)
        self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk, is_active=True).exists())

    def test_second_portal_admin_can_be_demoted_without_elevating_staff(self):
        second = self.create(role=PortalAccount.Role.ADMIN)
        self.update(user=second, role=PortalAccount.Role.ORGANIZER)
        second.refresh_from_db()
        self.assertFalse(is_portal_admin(second))
        self.assertFalse(second.is_staff or second.is_superuser)

    def test_technical_accounts_are_protected_even_for_portal_admin(self):
        for actor in (self.admin, self.technical):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                update_portal_user(actor=actor, user_id=self.technical.pk, expected_version=1,
                                   role=PortalAccount.Role.ADMIN, is_active=False)
        self.technical.refresh_from_db()
        self.assertTrue(self.technical.is_active)

    def test_inactive_admin_cannot_manage_accounts(self):
        get_user_model().objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.update()

    def test_reviewer_sees_only_explicit_assignments_not_other_owner_events(self):
        self.assertFalse(can_organize(self.reviewer))
        self.assertFalse(can_view_event(self.reviewer, self.event))
        self.assign()
        self.assertTrue(can_view_event(self.reviewer, self.event))
        self.assertFalse(can_view_event(self.reviewer, self.other_event))
        self.assertEqual(list(visible_events(self.reviewer).values_list("pk", flat=True)), [self.event.pk])
        self.assertFalse(can_view_event(self.admin, self.event))
        self.assertFalse(can_view_event(self.technical, self.event))
        self.assertFalse(visible_events(AnonymousUser()).exists())

    def test_owner_grants_access_without_changing_event_content_revision(self):
        revision = self.event.revision
        assigned = self.assign()
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, revision)
        self.assertEqual(self.event.review_access_version, 2)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0].assigned_by_id, self.organizer.pk)
        self.assertEqual(assigned[0].reviewer_version, 1)
        self.assign()
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_access_version, 2)

    def test_only_event_owner_can_assign_and_selected_users_must_be_active_reviewers(self):
        for actor in (self.other, self.admin, self.technical, self.reviewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.assign(actor=actor)
        for ids in ([self.organizer.pk], [self.technical.pk], [999999], [True], ["1"]):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                self.assign(ids=ids)
        get_user_model().objects.filter(pk=self.reviewer.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.assign()
        self.assertEqual(EventReviewAssignment.objects.count(), 0)

    def test_stale_assignment_request_cannot_overwrite_newer_grants(self):
        self.assign()
        with self.assertRaisesMessage(ValidationError, "otra pestaña"):
            self.assign(ids=[], expected_version=1)
        self.assertTrue(can_view_event(self.reviewer, self.event))

    def test_explicit_revoke_removes_access(self):
        self.assign()
        self.assign(ids=[])
        self.assertFalse(can_view_event(self.reviewer, self.event))
        self.assertEqual(EventReviewAssignment.objects.count(), 0)

    def test_disable_then_reactivate_does_not_revive_old_assignment(self):
        self.assign()
        self.update(is_active=False)
        self.assertFalse(can_view_event(self.reviewer, self.event))
        self.reviewer.refresh_from_db()
        self.update(is_active=True)
        self.reviewer.refresh_from_db()
        self.assertFalse(can_view_event(self.reviewer, self.event))
        grant = EventReviewAssignment.objects.get(event=self.event, reviewer=self.reviewer)
        self.assertEqual(grant.reviewer_version, 1)
        self.assertEqual(self.reviewer.portal_account.access_version, 3)
        self.assign()
        self.assertTrue(can_view_event(self.reviewer, self.event))
        grant.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual((grant.reviewer_version, self.event.review_access_version), (3, 3))

    def test_role_round_trip_requires_owner_to_grant_again(self):
        self.assign()
        self.update(role=PortalAccount.Role.ORGANIZER)
        self.assertFalse(can_view_event(self.reviewer, self.event))
        self.update(role=PortalAccount.Role.REVIEWER)
        self.assertFalse(can_view_event(self.reviewer, self.event))
        self.assign()
        self.assertTrue(can_view_event(self.reviewer, self.event))

    def test_password_session_rotation_does_not_revoke_review_assignment(self):
        self.assign()
        profile = PortalAccount.objects.get(user=self.reviewer)
        profile.session_version += 1
        profile.save(update_fields=["session_version"])
        self.assertTrue(can_view_event(self.reviewer, self.event))
        self.assertEqual(EventReviewAssignment.objects.get(event=self.event).reviewer_version, profile.access_version)


@skipUnless(connection.vendor == "postgresql", "La carrera de administradores requiere PostgreSQL.")
class PostgreSQLPortalAdminConcurrencyTests(TransactionTestCase):
    def test_concurrent_cross_demotions_preserve_one_active_administrator(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        AdminRosterLock.objects.get_or_create(pk=1)
        users = [get_user_model().objects.create_user(username="admin-race-" + str(index)) for index in range(2)]
        for user in users:
            PortalAccount.objects.create(user=user, role=PortalAccount.Role.ADMIN)
        start = Barrier(2)

        def demote(actor_id, target_id):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '10s'")
                # Both threads capture an administrator before either command;
                # the service must recheck under the serialization lock.
                actor = get_user_model().objects.get(pk=actor_id)
                start.wait(timeout=10)
                try:
                    update_portal_user(actor=actor, user_id=target_id, expected_version=1,
                                       role=PortalAccount.Role.ORGANIZER, is_active=True)
                    return "updated"
                except PermissionDenied:
                    return "denied"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(demote, users[0].pk, users[1].pk),
                       executor.submit(demote, users[1].pk, users[0].pk)]
            outcomes = [future.result(timeout=15) for future in futures]
        self.assertCountEqual(outcomes, ["updated", "denied"])
        self.assertEqual(PortalAccount.objects.filter(role=PortalAccount.Role.ADMIN, user__is_active=True).count(), 1)
