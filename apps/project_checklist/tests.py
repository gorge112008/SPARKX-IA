"""Private manual checklist: scope, explicit writes and stale tab safety."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.events.models import Event
from apps.jobs.models import Job
from .catalog import GROUPS, ITEMS, OPTIONAL_KEYS
from .forms import ProgressForm
from .models import ChecklistProgress
from .services import StaleProgress, update_progress


@override_settings(SPARKX_CHECKLIST_ENABLED=True, SPARKX_CHECKLIST_OWNER_USERNAME="checklist-owner")
class ChecklistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username="checklist-owner", is_staff=True)
        cls.other = users.objects.create_user(username="checklist-other", is_staff=True)
        cls.member = users.objects.create_user(username="checklist-member")

    def setUp(self):
        self.client.force_login(self.owner)
        remote = patch("apps.assistant.provider._opener.open", side_effect=AssertionError("A checklist must never invoke AI"))
        self.remote = remote.start()
        self.addCleanup(remote.stop)
        self.addCleanup(self.remote.assert_not_called)

    def index_url(self):
        return reverse("project_checklist:index")

    def update_url(self, key="creditos_api"):
        return reverse("project_checklist:update", kwargs={"item_key": key})

    def post(self, status="completed", version=0, key="creditos_api", **extra):
        if status == "completed" and "confirmations" not in extra and key in ITEMS:
            extra["confirmations"] = [check.key for check in ITEMS[key].confirmations]
        return self.client.post(self.update_url(key), {"status": status, "expected_version": version, **extra})

    def items(self, response):
        return {item["key"]: item for group in response.context["checklist_groups"] for item in group["items"]}

    def test_catalog_has_fifteen_stable_items_and_explicit_conditions(self):
        self.assertEqual(len(GROUPS), 4)
        self.assertEqual([len(group.items) for group in GROUPS], [4, 3, 4, 4])
        self.assertEqual(len(ITEMS), 15)
        self.assertEqual(set(OPTIONAL_KEYS), {"demo_voz", "servicios_vps", "acceso_ssh", "password_publico", "datos_participantes"})
        for key in OPTIONAL_KEYS:
            self.assertTrue(ITEMS[key].condition)

    def test_catalog_cannot_be_changed_at_runtime(self):
        with self.assertRaises(TypeError):
            ITEMS["new"] = ITEMS["demo_voz"]
        with self.assertRaises(AttributeError):
            ITEMS["demo_voz"].title = "Changed"

    def test_get_lists_fifteen_defaults_without_creating_data(self):
        before = (AIAccount.objects.count(), AIProfile.objects.count(), AIUsage.objects.count(), Event.objects.count(), Job.objects.count())
        for _ in range(2):
            response = self.client.get(self.index_url())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.items(response)), 15)
            self.assertEqual(response.context["stats"], {"total": 15, "applicable": 15, "completed": 0, "in_progress": 0, "not_applicable": 0, "needs_review": 0, "percent": 0})
            self.assertTrue(all(row["version"] == 0 and row["status"] == "not_started" for row in self.items(response).values()))
        self.assertFalse(ChecklistProgress.objects.exists())
        self.assertEqual(before, (AIAccount.objects.count(), AIProfile.objects.count(), AIUsage.objects.count(), Event.objects.count(), Job.objects.count()))

    def test_forms_have_unique_ids_and_server_owned_update_urls(self):
        response = self.client.get(self.index_url())
        items = self.items(response)
        ids = [row["form"]["status"].id_for_label for row in items.values()]
        self.assertEqual(len(set(ids)), 15)
        for key, row in items.items():
            self.assertEqual(row["anchor"], "item-" + key)
            self.assertEqual(row["update_url"], self.update_url(key))

    def test_login_required_for_get_and_post(self):
        self.client.logout()
        for response in (self.client.get(self.index_url()), self.post()):
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_nonstaff_cannot_read_or_mutate(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.index_url()).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_superuser_without_staff_flag_has_access(self):
        self.owner.is_staff, self.owner.is_superuser = False, True
        self.owner.save(update_fields=["is_staff", "is_superuser"])
        self.assertEqual(self.client.get(self.index_url()).status_code, 200)

    @override_settings(SPARKX_CHECKLIST_ENABLED=False)
    def test_disabled_feature_refuses_get_and_post(self):
        self.assertEqual(self.client.get(self.index_url()).status_code, 404)
        self.assertEqual(self.post().status_code, 404)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_update_requires_post_and_index_requires_get(self):
        self.assertEqual(self.client.get(self.update_url()).status_code, 405)
        self.assertEqual(self.client.put(self.update_url(), {}).status_code, 405)
        self.assertEqual(self.client.post(self.index_url(), {}).status_code, 405)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_csrf_required_and_valid_token_allows_local_write(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.update_url(), {"status": "completed", "expected_version": 0}).status_code, 403)
        self.assertFalse(ChecklistProgress.objects.exists())
        self.assertEqual(client.get(self.index_url()).status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post(self.update_url(), {"status": "completed", "expected_version": 0, "csrfmiddlewaretoken": token, "confirmations": [check.key for check in ITEMS["creditos_api"].confirmations]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChecklistProgress.objects.get().owner_id, self.owner.pk)

    def test_post_creates_owned_status_and_redirects_to_its_open_section(self):
        response = self.post(status="in_progress", key="demo_voz")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.index_url() + "?section=demo#item-demo_voz")
        row = ChecklistProgress.objects.get()
        self.assertEqual((row.owner_id, row.item_key, row.status, row.version), (self.owner.pk, "demo_voz", "in_progress", 1))
        self.assertIsNotNone(row.updated_at)

    def test_initial_noop_does_not_create_row(self):
        self.assertEqual(self.post(status="not_started").status_code, 302)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_owned_progress_is_never_shared_between_admins(self):
        self.post()
        self.client.force_login(self.other)
        page = self.client.get(self.index_url())
        self.assertEqual(page.status_code, 403)
        self.assertEqual(self.post(status="in_progress").status_code, 403)
        self.assertEqual(ChecklistProgress.objects.count(), 1)
        self.assertEqual(ChecklistProgress.objects.get(owner=self.owner).status, "completed")

    def test_client_owner_and_arbitrary_notes_are_refused(self):
        for extra in ({"owner": self.other.pk}, {"owner_id": self.other.pk}, {"note": "unsolicited"}, {"api_key": "not-an-actual-key"}):
            with self.subTest(extra=tuple(extra)):
                self.assertEqual(self.post(**extra).status_code, 400)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_unknown_key_has_no_writes(self):
        self.assertEqual(self.post(key="unknown-point").status_code, 404)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_invalid_or_missing_status_version_has_no_writes(self):
        for data in ({}, {"status": "completed"}, {"status": "bad", "expected_version": 0},
                     {"status": "completed", "expected_version": -1}, {"status": "completed", "expected_version": "x"},
                     {"status": "completed", "expected_version": 2147483648}):
            with self.subTest(data=data):
                response = self.client.post(self.update_url(), data)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(self.items(response)["creditos_api"]["form"].errors)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_duplicate_fields_are_refused(self):
        self.assertEqual(self.client.post(self.update_url(), {"status": ["completed", "in_progress"], "expected_version": 0}).status_code, 400)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_no_aplica_is_limited_to_conditional_points(self):
        self.assertEqual(self.post(status="not_applicable").status_code, 400)
        self.assertFalse(ChecklistProgress.objects.exists())
        for key in OPTIONAL_KEYS:
            self.assertEqual(self.post(status="not_applicable", key=key).status_code, 302)
        self.assertEqual(ChecklistProgress.objects.filter(status="not_applicable").count(), 5)

    def test_same_request_replay_does_not_change_version_or_time(self):
        self.post()
        before = ChecklistProgress.objects.values().get()
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(before, ChecklistProgress.objects.values().get())
        self.assertEqual(self.post(version=1).status_code, 302)
        self.assertEqual(before, ChecklistProgress.objects.values().get())

    def test_change_increments_version_and_stale_opposite_status_is_rejected(self):
        self.post(status="in_progress")
        self.assertEqual(self.post(status="completed", version=1).status_code, 302)
        before = ChecklistProgress.objects.values().get()
        self.assertEqual(before["version"], 2)
        response = self.post(status="not_started", version=1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(before, ChecklistProgress.objects.values().get())
        self.assertEqual(self.items(response)["creditos_api"]["version"], 2)
        self.assertEqual(self.items(response)["creditos_api"]["form"].initial["expected_version"], 2)
        self.assertTrue(response.context["checklist_error"])

    def test_long_stale_replay_does_not_override_or_claim_success(self):
        self.post(status="completed")
        self.post(status="in_progress", version=1)
        self.post(status="completed", version=2)
        before = ChecklistProgress.objects.values().get()
        self.assertEqual(self.post(status="completed", version=0).status_code, 409)
        self.assertEqual(before, ChecklistProgress.objects.values().get())

    def test_nonexistent_row_rejects_nonzero_expected_version(self):
        self.assertEqual(self.post(version=2).status_code, 409)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_applicable_denominator_excludes_only_explicit_no_aplica(self):
        self.post(key="demo_voz", status="not_applicable")
        self.post(status="completed")
        self.post(key="credencial_privada", status="in_progress")
        page = self.client.get(self.index_url())
        self.assertEqual(page.context["stats"], {"total": 15, "applicable": 14, "completed": 1, "in_progress": 1, "not_applicable": 1, "needs_review": 0, "percent": 7})
        group = next(group for group in page.context["checklist_groups"] if group["key"] == "demo")
        self.assertEqual((group["completed"], group["applicable"], group["not_applicable"]), (0, 2, 1))
        self.post(key="demo_voz", status="not_started", version=1)
        self.assertEqual(self.client.get(self.index_url()).context["stats"]["applicable"], 15)

    def test_one_hundred_percent_requires_all_applicable_items_completed(self):
        for key in ITEMS:
            self.post(key=key, status="not_applicable" if key in OPTIONAL_KEYS else "completed")
        stats = self.client.get(self.index_url()).context["stats"]
        self.assertEqual((stats["completed"], stats["applicable"], stats["percent"]), (10, 10, 100))

    def test_section_is_catalog_scoped_and_error_opens_correct_group(self):
        self.assertEqual(self.client.get(self.index_url(), {"section": "demo"}).context["active_group"], "demo")
        self.assertEqual(self.client.get(self.index_url(), {"section": "foreign"}).context["active_group"], "conexion")
        self.assertEqual(self.post(status="bad", key="demo_voz").context["active_group"], "demo")
        self.post(status="in_progress", key="demo_voz")
        self.assertEqual(self.post(status="completed", version=9, key="demo_voz").context["active_group"], "demo")

    def test_mutation_never_changes_ai_accounts_or_creates_jobs(self):
        account = AIAccount.objects.create(owner=self.owner, monthly_budget_usd="0.250000", monthly_token_limit=12345, paid_enabled=False)
        before = (AIAccount.objects.values().get(pk=account.pk), AIProfile.objects.count(), AIUsage.objects.count(), Job.objects.count(), Event.objects.count())
        self.post()
        after = (AIAccount.objects.values().get(pk=account.pk), AIProfile.objects.count(), AIUsage.objects.count(), Job.objects.count(), Event.objects.count())
        self.assertEqual(before, after)

    def test_database_guards_owner_item_uniqueness_and_eligibility(self):
        ChecklistProgress.objects.create(owner=self.owner, item_key="creditos_api", status="completed")
        for changes in ({"item_key": "creditos_api"}, {"item_key": "nonexistent"}, {"item_key": "credencial_privada", "status": "not_applicable"}, {"item_key": "demo_voz", "status": "invalid"}, {"item_key": "demo_voz", "version": 0}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                ChecklistProgress.objects.create(owner=self.owner, **changes)

    def test_service_validates_inputs_even_without_form(self):
        from django.core.exceptions import ValidationError
        for data in ({"item_key": "unknown", "status": "completed", "expected_version": 0},
                     {"item_key": "creditos_api", "status": "not_applicable", "expected_version": 0},
                     {"item_key": "creditos_api", "status": "bad", "expected_version": 0},
                     {"item_key": "creditos_api", "status": "completed", "expected_version": True}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                update_progress(owner=self.owner, **data)
        self.assertFalse(ChecklistProgress.objects.exists())

    def test_atomic_compare_and_update_rejects_interleaved_other_change(self):
        self.post(status="in_progress")
        row = ChecklistProgress.objects.get()
        from .services import _existing_update
        ChecklistProgress.objects.filter(pk=row.pk).update(status="not_started", version=2)
        with self.assertRaises(StaleProgress):
            _existing_update(row=row, status="completed", expected_version=1)
        row.refresh_from_db()
        self.assertEqual((row.status, row.version), ("not_started", 2))

    def test_exact_interleaved_result_is_idempotent(self):
        self.post(status="in_progress")
        row = ChecklistProgress.objects.get()
        from .services import _existing_update
        ChecklistProgress.objects.filter(pk=row.pk).update(status="completed", version=2)
        current, changed = _existing_update(row=row, status="completed", expected_version=1)
        self.assertFalse(changed)
        self.assertEqual((current.status, current.version), ("completed", 2))
