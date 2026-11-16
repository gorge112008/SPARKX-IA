"""Task completion closes the editor and offers a read-only next step.

These requests use Django's isolated test database. No AI provider or real event
is involved; navigation never completes or reopens another task implicitly.
"""

import json
import uuid
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import EventReviewAssignment, PortalAccount
from apps.ai_management.models import AIUsage
from apps.jobs.models import Job
from apps.planning.models import TaskProgress, TaskProgressChange
from apps.planning.progress_ui import task_tracking_context
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan

from apps.events.services import create_event
from apps.events.tests.test_task_progress_views import _Markup


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TaskCompletionFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="completion-owner")
        cls.reviewer = get_user_model().objects.create_user(username="completion-reviewer")
        PortalAccount.objects.update_or_create(user=cls.reviewer, defaults={"role": "reviewer"})

    def setUp(self):
        self.event = create_event(actor=self.owner, title="Ensayo de seguimiento", brief="Datos ficticios para probar tareas")
        payload = valid_plan()
        payload["tasks"].append({
            "id": "t3", "title": "Preparar material", "depends_on": [],
            "status": "pending", "purpose": "Revisar el material de la demostración.",
        })
        candidate = create_candidate(event=self.event, actor=self.owner, payload=payload, base_revision=1)
        self.plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        self.client.force_login(self.owner)

    def tearDown(self):
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(AIUsage.objects.count(), 0)

    def url(self, name="detail"):
        return reverse("events:" + name, kwargs={"event_id": self.event.pk})

    def command(self, task_id="t1", **changes):
        record = TaskProgress.objects.filter(plan=self.plan, task_id=task_id).first()
        return {
            "task_id": task_id, "expected_plan": str(self.plan.pk),
            "expected_version": record.version if record else 0,
            "request_key": str(uuid.uuid4()), "status": "completed",
            "note": "Prueba ficticia: preparación revisada.", **changes,
        }

    def post(self, data=None, *, htmx=True, task_id="t1", **changes):
        return self.client.post(self.url("task_progress"), data or self.command(task_id, **changes),
                                **({"HTTP_HX_REQUEST": "true"} if htmx else {}))

    def tracking(self, *, task_id=None, result="", feedback=""):
        self.event.refresh_from_db()
        return task_tracking_context(self.event, task_id=task_id, result=result, feedback=feedback)

    def row(self, task_id="t1", tracking=None):
        return next(row for row in (tracking or self.tracking())["rows"] if row["id"] == task_id)

    def next_url(self, task_id):
        target = self.row(task_id)
        return self.url() + "?" + urlencode({"task": task_id}) + "#" + target["tracking"]["dom_id"]

    def followup(self, response, task_id="t1"):
        markup = _Markup(response)
        row = markup.task_row(task_id)
        return next(node for node in markup.find("details")
                    if "data-task-followup" in node.attrs and self.inside(node, row))

    @staticmethod
    def inside(node, ancestor):
        while node is not None:
            if node is ancestor:
                return True
            node = node.parent
        return False

    def test_saved_completion_closes_editor_and_offers_unfinished_next_task(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("open", self.followup(response).attrs)
        tracking = self.tracking(task_id="t1", result="saved", feedback="Estado guardado.")
        row = self.row(tracking=tracking)["tracking"]
        self.assertTrue(row["is_completed"])
        self.assertFalse(row["editor_open"])
        self.assertEqual(row["next_task"]["id"], "t2")
        self.assertEqual(row["next_task"]["url"], self.next_url("t2"))
        self.assertTrue(_Markup(response).find("a", href=self.next_url("t2")))
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        self.assertFalse(TaskProgress.objects.filter(plan=self.plan, task_id="t2").exists())

    def test_htmx_task_updates_keep_the_strict_csp_without_restoring_inline_styles(self):
        # HTMX's default settle attributes include "style". Restoring that
        # attribute during outerHTML/OOB swaps violates our self-only style
        # policy even if the server's markup has no inline CSS. Keep the
        # rendered configuration compatible without weakening that policy.
        page = self.client.get(self.url())
        meta = _Markup(page).find("meta", name="htmx-config")
        self.assertEqual(len(meta), 1)
        config = json.loads(meta[0].attrs["content"])
        self.assertNotIn("style", config["attributesToSettle"])
        self.assertIs(config["includeIndicatorStyles"], False)
        self.assertIs(config["allowEval"], False)
        self.assertIs(config["allowScriptTags"], False)
        fragment = self.post()
        for response in (page, fragment):
            with self.subTest(is_fragment=response is fragment):
                self.assertEqual(response.status_code, 200)
                policy = response["Content-Security-Policy"]
                directives = {
                    parts[0]: parts[1:]
                    for directive in policy.split(";") if (parts := directive.split())
                }
                self.assertEqual(directives["style-src"], ["'self'"])
                self.assertEqual(directives["script-src"], ["'self'"])
                self.assertNotIn("'unsafe-inline'", policy)
                self.assertNotIn("'unsafe-eval'", policy)
                self.assertFalse([node for node in _Markup(response).elements if "style" in node.attrs])

    def test_next_task_skips_completed_rows_and_wraps_to_first_unfinished(self):
        self.post(task_id="t2")
        self.post(task_id="t3")
        tracking = self.tracking(task_id="t3", result="saved", feedback="Estado guardado.")
        self.assertEqual(self.row("t3", tracking)["tracking"]["next_task"]["id"], "t1")
        self.assertFalse(TaskProgress.objects.filter(plan=self.plan, task_id="t1").exists())

    def test_next_task_skips_an_already_completed_middle_row(self):
        self.post(task_id="t2")
        response = self.post(task_id="t1")
        self.assertTrue(_Markup(response).find("a", href=self.next_url("t3")))
        self.assertFalse(_Markup(response).find("a", href=self.next_url("t2")))
        self.assertFalse(TaskProgress.objects.filter(plan=self.plan, task_id="t3").exists())

    def test_historical_plan_never_offers_a_next_edit_even_with_saved_feedback(self):
        self.post()
        candidate = create_candidate(event=self.event, actor=self.owner, payload=valid_plan(),
                                     base_revision=self.event.revision, base_plan_id=self.plan.pk)
        approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        tracking = task_tracking_context(self.event, plan=self.plan, task_id="t1",
                                          result="saved", feedback="Estado guardado.")
        row = self.row(tracking=tracking)["tracking"]
        self.assertFalse(row["editable"])
        self.assertFalse(row["next_task"])
        self.assertFalse(row["editor_open"])

    def test_next_task_does_not_appear_on_initial_read_error_or_in_progress_save(self):
        self.post()
        for result in ("", "error", "conflict"):
            with self.subTest(result=result):
                tracking = self.tracking(task_id="t1", result=result, feedback="Aviso" if result else "")
                self.assertFalse(self.row(tracking=tracking)["tracking"].get("next_task"))
        response = self.post(task_id="t2", status="in_progress", note="")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("open", self.followup(response, "t2").attrs)
        self.assertFalse(self.row("t2", self.tracking(task_id="t2", result="saved"))["tracking"].get("next_task"))

    def test_completion_without_note_stays_open_and_does_not_save(self):
        response = self.post(note="")
        self.assertEqual(response.status_code, 200)
        self.assertIn("open", self.followup(response).attrs)
        markup = _Markup(response)
        self.assertTrue(markup.find(**{"data-task-result": "error"}))
        self.assertTrue([node for node in markup.find("option", value="completed") if "selected" in node.attrs])
        self.assertFalse(markup.find("a", href=self.next_url("t2")))
        self.assertFalse(TaskProgress.objects.exists())
        self.assertFalse(TaskProgressChange.objects.exists())

    def test_stale_command_keeps_editor_open_current_state_and_typed_note(self):
        stale = self.command(note="Explicación escrita antes del otro cambio.")
        self.post(status="in_progress", note="Primer cambio")
        response = self.post(stale)
        self.assertEqual(response.status_code, 200)
        self.assertIn("open", self.followup(response).attrs)
        markup = _Markup(response)
        self.assertTrue(markup.find(**{"data-task-result": "conflict"}))
        self.assertEqual(markup.find("textarea", name="note")[0].text.strip(), stale["note"])
        self.assertEqual(markup.find("input", name="expected_version")[0].attrs["value"], "1")
        current = TaskProgress.objects.get(plan=self.plan, task_id="t1")
        self.assertEqual((current.status, current.version), ("in_progress", 1))
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_completed_task_has_explicit_reopen_form_without_another_completion_choice(self):
        self.post()
        before = list(TaskProgress.objects.values())
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("open", self.followup(response).attrs)
        tracking = self.row(tracking=response.context["task_tracking"])["tracking"]
        self.assertTrue(tracking["is_completed"])
        self.assertEqual({value for value, _label in tracking["form"].fields["status"].choices},
                         {"in_progress", "not_started"})
        self.assertEqual(tracking["form"].initial["status"], "in_progress")
        self.assertIn("Reabrir", self.followup(response).text)
        self.assertEqual(list(TaskProgress.objects.values()), before)
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_reopening_requires_a_reason_then_closes_editor_after_save(self):
        self.post()
        invalid = self.post(status="in_progress", note="")
        self.assertIn("open", self.followup(invalid).attrs)
        self.assertEqual(TaskProgress.objects.get(plan=self.plan, task_id="t1").status, "completed")
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        saved = self.post(status="in_progress", note="Prueba ficticia: necesitamos revisar el material.")
        self.assertNotIn("open", self.followup(saved).attrs)
        current = TaskProgress.objects.get(plan=self.plan, task_id="t1")
        self.assertEqual((current.status, current.version), ("in_progress", 2))
        self.assertEqual(TaskProgressChange.objects.get(progress=current, version=2).from_status, "completed")

    def test_no_script_completion_redirects_to_and_opens_only_next_task(self):
        response = self.post(htmx=False)
        self.assertRedirects(response, self.next_url("t2"), fetch_redirect_response=False)
        before = list(TaskProgress.objects.values())
        page = self.client.get(response.url)
        self.assertEqual(page.context["active_panel"], "preparation")
        self.assertNotIn("open", self.followup(page, "t1").attrs)
        self.assertIn("open", self.followup(page, "t2").attrs)
        self.assertNotIn("open", self.followup(page, "t3").attrs)
        self.assertEqual(list(TaskProgress.objects.values()), before)
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_get_can_open_completed_task_for_review_without_reopening_its_state(self):
        self.post()
        before = list(TaskProgress.objects.values())
        page = self.client.get(self.url(), {"task": "t1"})
        self.assertIn("open", self.followup(page).attrs)
        self.assertEqual(list(TaskProgress.objects.values()), before)
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_unknown_open_target_does_not_open_any_editor_or_create_progress(self):
        page = self.client.get(self.url(), {"task": "unknown-task"})
        for task_id in ("t1", "t2", "t3"):
            self.assertNotIn("open", self.followup(page, task_id).attrs)
        self.assertFalse(TaskProgress.objects.exists())

    def test_all_completed_has_hundred_percent_banner_and_no_next_task(self):
        self.post()
        self.post(task_id="t2")
        response = self.post(task_id="t3")
        tracking = self.tracking(task_id="t3", result="saved", feedback="Estado guardado.")
        self.assertTrue(tracking["all_completed"])
        self.assertEqual(tracking["percentage"], 100)
        self.assertFalse(self.row("t3", tracking)["tracking"].get("next_task"))
        self.assertTrue(_Markup(response).find(**{"data-task-all-completed": None}))
        self.assertTrue(_Markup(response).find(**{"data-task-percentage": "100"}))
        page = self.client.get(self.url())
        self.assertTrue(_Markup(page).find(**{"data-task-all-completed": None}))
        self.assertTrue(_Markup(page).find("a", href=self.url() + "#plan"))
        self.assertEqual(TaskProgressChange.objects.count(), 3)

    def test_empty_plan_is_not_announced_as_all_completed(self):
        payload = valid_plan()
        payload["tasks"] = []
        candidate = create_candidate(event=self.event, actor=self.owner, payload=payload,
                                     base_revision=self.event.revision, base_plan_id=self.plan.pk)
        approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        page = self.client.get(self.url())
        self.assertFalse(page.context["task_tracking"]["all_completed"])
        self.assertFalse(_Markup(page).find(**{"data-task-all-completed": None}))

    def test_last_completion_without_javascript_stays_in_preparation_and_persists(self):
        self.post()
        self.post(task_id="t2")
        response = self.post(task_id="t3", htmx=False)
        self.assertRedirects(response, self.url() + "#preparation", fetch_redirect_response=False)
        page = self.client.get(response.url)
        self.assertEqual(page.context["task_tracking"]["percentage"], 100)
        self.assertTrue(page.context["task_tracking"]["all_completed"])
        for task_id in ("t1", "t2", "t3"):
            self.assertNotIn("open", self.followup(page, task_id).attrs)
        self.assertEqual(TaskProgressChange.objects.count(), 3)

    def test_exact_retry_does_not_duplicate_history_or_change_the_next_task(self):
        command = self.command()
        self.post(command)
        self.post(command)
        before = list(TaskProgress.objects.values())
        response = self.post(command)
        self.assertNotIn("open", self.followup(response).attrs)
        self.assertTrue(_Markup(response).find("a", href=self.next_url("t2")))
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        self.assertEqual(list(TaskProgress.objects.values()), before)
        self.assertFalse(TaskProgress.objects.filter(plan=self.plan, task_id="t2").exists())

    def test_assigned_reviewer_never_receives_reopening_or_next_task_controls(self):
        self.post()
        profile = PortalAccount.objects.get(user=self.reviewer)
        EventReviewAssignment.objects.create(event=self.event, reviewer=self.reviewer,
                                             assigned_by=self.owner, reviewer_version=profile.access_version)
        before = list(TaskProgress.objects.values())
        self.client.force_login(self.reviewer)
        page = self.client.get(self.url(), {"task": "t1"})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(_Markup(page).find("form", action=self.url("task_progress")))
        self.assertNotContains(page, "Reabrir")
        self.assertEqual(self.post(status="not_started", note="Sin autoridad").status_code, 403)
        self.assertEqual(list(TaskProgress.objects.values()), before)
        self.assertEqual(TaskProgressChange.objects.count(), 1)
