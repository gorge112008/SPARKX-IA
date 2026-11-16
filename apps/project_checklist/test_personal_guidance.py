"""Personal access, confirmations and observations stay separate from actions."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ai_management.models import AIAccount
from config.context_processors import project_tools
from .catalog import ITEMS
from .models import ChecklistProgress
from .services import update_progress


@override_settings(SPARKX_CHECKLIST_ENABLED=True, SPARKX_CHECKLIST_OWNER_USERNAME="personal-owner")
class PersonalChecklistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username="personal-owner", is_staff=True)
        cls.other = users.objects.create_superuser(username="other-admin")

    def setUp(self):
        self.client.force_login(self.owner)
        self.index = reverse("project_checklist:index")
        self.check = reverse("project_checklist:check")
        self.save = reverse("project_checklist:update", args=["creditos_api"])
        self.confirmations = [check.key for check in ITEMS["creditos_api"].confirmations]

    def post(self, status="completed", confirmations=None, version=0):
        return self.client.post(self.save, {
            "status": status, "expected_version": version,
            "confirmations": self.confirmations if confirmations is None else confirmations,
        })

    def test_other_superuser_has_no_read_update_check_or_navigation_access(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.index).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.post(self.check).status_code, 403)
        request = type("Request", (), {"user": self.other})()
        self.assertFalse(project_tools(request)["project_checklist_visible"])
        with self.assertRaises(PermissionDenied):
            update_progress(owner=self.other, item_key="creditos_api", status="in_progress", expected_version=0)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_completion_requires_all_specific_confirmations_and_preserves_partial_input(self):
        partial = self.confirmations[:1]
        response = self.post(confirmations=partial)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Revisa y marca todas", status_code=400)
        self.assertEqual(response.context["checklist_groups"][0]["items"][0]["confirmed_checks"], partial)
        self.assertFalse(ChecklistProgress.objects.exists())
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(ChecklistProgress.objects.get().confirmed_checks, self.confirmations)

    def test_confirmations_are_saved_in_progress_and_survive_reload(self):
        self.assertEqual(self.post(status="in_progress", confirmations=self.confirmations[:1]).status_code, 302)
        response = self.client.get(self.index)
        row = response.context["checklist_groups"][0]["items"][0]
        self.assertEqual(row["confirmed_checks"], self.confirmations[:1])
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(response.context["stats"]["completed"], 0)

    def test_unknown_duplicate_and_foreign_confirmation_ids_are_rejected(self):
        foreign = ITEMS["credencial_privada"].confirmations[0].key
        for values in (["unknown"], [foreign], [self.confirmations[0]] * 2):
            with self.subTest(values=values):
                self.assertEqual(self.post(confirmations=values).status_code, 400)
                with self.assertRaises(ValidationError):
                    update_progress(owner=self.owner, item_key="creditos_api", status="completed",
                                    expected_version=0, confirmations=values)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_only_confirmation_change_increments_version_and_stale_tabs_cannot_erase_it(self):
        self.post(status="in_progress", confirmations=[])
        self.post(status="in_progress", confirmations=self.confirmations[:1], version=1)
        row = ChecklistProgress.objects.get()
        self.assertEqual((row.version, row.confirmed_checks), (2, self.confirmations[:1]))
        self.assertEqual(self.post(status="in_progress", confirmations=[], version=1).status_code, 409)
        self.assertEqual(self.post(status="in_progress", confirmations=self.confirmations[:1], version=1).status_code, 302)
        row.refresh_from_db()
        self.assertEqual((row.version, row.confirmed_checks), (2, self.confirmations[:1]))

    def test_legacy_completed_progress_is_preserved_but_requests_review(self):
        row = ChecklistProgress.objects.create(owner=self.owner, item_key="creditos_api", status="completed", version=4)
        response = self.client.get(self.index)
        self.assertEqual(response.context["stats"]["needs_review"], 1)
        self.assertEqual(response.context["stats"]["completed"], 0)
        self.assertContains(response, "Tu estado anterior se conserva")
        row.refresh_from_db()
        self.assertEqual((row.status, row.version, row.confirmed_checks), ("completed", 4, []))
        self.assertEqual(self.post(version=4).status_code, 302)
        self.assertEqual(self.client.get(self.index).context["stats"]["completed"], 1)

    def test_check_endpoint_requires_csrf_post_and_rejects_arbitrary_input(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(self.check).status_code, 403)
        self.assertEqual(self.client.get(self.check).status_code, 405)
        with patch("apps.project_checklist.checks.collect_local_checks") as probe:
            self.assertEqual(self.client.post(self.check, {"owner": self.other.pk}).status_code, 400)
            probe.assert_not_called()

    def test_local_check_is_scoped_and_never_completes_or_creates_an_account(self):
        now = timezone.now()
        checks = {"creditos_api": {"status": "ready", "message": "Dato de prueba local", "checked_at": now}}
        with patch("apps.project_checklist.checks.collect_local_checks", return_value=checks) as probe:
            response = self.client.post(self.check)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(probe.call_args.kwargs["owner"].pk, self.owner.pk)
        self.assertEqual(response.context["stats"]["completed"], 0)
        self.assertContains(response, "Dato de prueba local")
        self.assertFalse(ChecklistProgress.objects.exists())
        self.assertFalse(AIAccount.objects.exists())

    @override_settings(SPARKX_CHECKLIST_ENABLED=False)
    def test_hiding_module_retains_progress_and_blocks_check(self):
        ChecklistProgress.objects.create(owner=self.owner, item_key="creditos_api", status="in_progress")
        self.assertEqual(self.client.post(self.check).status_code, 404)
        self.assertEqual(self.client.get(self.index).status_code, 404)
        self.assertEqual(ChecklistProgress.objects.count(), 1)
