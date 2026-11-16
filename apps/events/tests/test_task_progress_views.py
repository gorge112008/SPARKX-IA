"""Manual preparation workflow: HTTP authority, safe retries and useful HTMX errors."""

from copy import deepcopy
from html.parser import HTMLParser
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.planning.models import TaskProgress, TaskProgressChange
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan
from apps.events.services import create_event


class _Element:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    @property
    def text(self):
        return "".join(child if isinstance(child, str) else child.text for child in self.children)


class _Markup(HTMLParser):
    """Small HTML reader so assertions do not depend on attribute order or row hashes."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, response):
        super().__init__()
        self.root = _Element("root")
        self.stack, self.elements = [self.root], []
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        node = _Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.elements.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for position in range(len(self.stack) - 1, 0, -1):
            if self.stack[position].tag == tag:
                del self.stack[position:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def find(self, tag=None, **attrs):
        return [node for node in self.elements if (tag is None or node.tag == tag)
                and all(key in node.attrs and node.attrs[key] == value for key, value in attrs.items())]

    def task_row(self, task_id):
        field = next(node for node in self.find("input", name="task_id") if node.attrs.get("value") == task_id)
        node = field.parent
        while node is not None and "data-task-row" not in node.attrs:
            node = node.parent
        return node


class TaskProgressEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="task-owner", password="task-test-password")
        cls.other = get_user_model().objects.create_user(username="task-other", password="task-test-password")

    def setUp(self):
        self.event = create_event(actor=self.owner, title="Preparación propia", brief="Preparación manual del seminario")
        self.foreign = create_event(actor=self.other, title="Evento ajeno privado", brief="Información privada ajena")
        self.candidate, self.plan = self.approve()
        self.client.force_login(self.owner)

    def approve(self, payload=None):
        self.event.refresh_from_db()
        candidate = create_candidate(event=self.event, actor=self.owner, payload=payload or valid_plan(),
                                     base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)
        plan = approve_candidate(candidate_id=candidate.pk, actor=self.owner)
        self.event.refresh_from_db()
        return candidate, plan

    def url(self, name="task_progress", event=None):
        return reverse("events:" + name, kwargs={"event_id": (event or self.event).pk})

    def command(self, **extra):
        data = {"task_id": "t1", "expected_plan": str(self.plan.pk), "expected_version": 0,
                "request_key": str(uuid.uuid4()), "status": "in_progress", "note": ""}
        data.update(extra)
        return data

    def post(self, data=None, *, htmx=True, **extra):
        headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
        return self.client.post(self.url(), data or self.command(**extra), **headers)

    def progress(self):
        return TaskProgress.objects.get(plan=self.plan, task_id="t1")

    def assert_result(self, response, result):
        self.assertEqual(response.status_code, 200)
        feedback = _Markup(response).find(**{"data-task-result": result})
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0].attrs["role"], "status" if result == "saved" else "alert")
        return _Markup(response)

    def assert_untouched(self):
        self.assertFalse(TaskProgress.objects.exists())
        self.assertFalse(TaskProgressChange.objects.exists())

    def test_detail_is_read_only_and_has_explicit_initial_states(self):
        for _ in range(2):
            response = self.client.get(self.url("detail"))
            self.assertEqual(response.status_code, 200)
            markup = _Markup(response)
            forms = markup.find("form", action=self.url())
            self.assertEqual(len(forms), 2)
            for form in forms:
                self.assertEqual(form.attrs["method"], "post")
                self.assertEqual(form.attrs["hx-target"], "closest li")
                self.assertEqual(form.attrs["hx-swap"], "outerHTML")
            self.assertEqual([node.attrs["value"] for node in markup.find("input", name="task_id")], ["t1", "t2"])
            self.assertEqual([node.attrs["value"] for node in markup.find("input", name="expected_version")], ["0", "0"])
            self.assertEqual(len(markup.find(**{"data-task-state": "not_started"})), 2)
            self.assertContains(response, "No iniciado")
            self.assertContains(response, "En proceso")
            self.assertContains(response, "Completado")
            self.assertEqual(len(markup.find(**{"data-task-percentage": "0"})), 1)
        self.assert_untouched()

    def test_percentage_uses_completed_tasks_and_follows_manual_reopening(self):
        in_progress = self.assert_result(self.post(), "saved")
        self.assertEqual(len(in_progress.find(**{"data-task-percentage": "0"})), 1)
        half = self.assert_result(self.post(status="completed", expected_version=1,
                                           note="Preparación terminada"), "saved")
        self.assertEqual(len(half.find(**{"data-task-percentage": "50"})), 1)
        complete = self.assert_result(self.post(task_id="t2", status="completed",
                                               note="Agenda revisada"), "saved")
        self.assertEqual(len(complete.find(**{"data-task-percentage": "100"})), 1)
        response = self.post(htmx=False, status="in_progress", expected_version=2,
                             note="Se necesita una nueva confirmación")
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.url)
        self.assertEqual(len(_Markup(page).find(**{"data-task-percentage": "50"})), 1)
        self.assertContains(page, "1 de 2 tareas completadas")

    def test_empty_approved_plan_displays_zero_without_an_invalid_progress_bar(self):
        payload = valid_plan()
        payload["tasks"] = []
        self.approve(payload)
        response = self.client.get(self.url("detail"))
        self.assertEqual(response.status_code, 200)
        markup = _Markup(response)
        self.assertEqual(len(markup.find(**{"data-task-percentage": "0"})), 1)
        self.assertContains(response, "0 de 0 tareas completadas")
        self.assertFalse(markup.find("progress"))
        self.assert_untouched()

    def test_anonymous_mutation_requires_login(self):
        self.client.logout()
        response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assert_untouched()

    def test_authenticated_endpoint_requires_post(self):
        for method in ("get", "put", "delete", "patch"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url()).status_code, 405)
        self.assert_untouched()

    def test_foreign_event_and_foreign_plan_are_not_disclosed(self):
        self.assertEqual(self.client.post(self.url(event=self.foreign), self.command()).status_code, 404)
        foreign_candidate = create_candidate(event=self.foreign, actor=self.other, payload=valid_plan(), base_revision=1)
        foreign_plan = approve_candidate(candidate_id=foreign_candidate.pk, actor=self.other)
        response = self.post(self.command(expected_plan=str(foreign_plan.pk)))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Información privada ajena", status_code=404)
        self.assert_untouched()

    def test_csrf_token_is_required_and_a_real_token_allows_the_command(self):
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url(), self.command()).status_code, 403)
        self.assert_untouched()
        secured.get(self.url("detail"))
        command = self.command(csrfmiddlewaretoken=secured.cookies["csrftoken"].value)
        response = secured.post(self.url(), command)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.progress().status, "in_progress")

    def test_manual_update_persists_actor_receipt_and_preserves_plan_content(self):
        original = deepcopy(self.plan.payload)
        revision = self.event.revision
        command = self.command(note="Confirmación solicitada", actor=self.other.pk, updated_by=self.other.pk,
                               owner=self.other.pk, updated_at="1999-01-01T00:00:00Z")
        self.assert_result(self.post(command), "saved")
        progress = self.progress()
        self.assertEqual((progress.status, progress.version, progress.updated_by_id), ("in_progress", 1, self.owner.pk))
        self.assertEqual(progress.note, "Confirmación solicitada")
        self.assertIsNotNone(progress.updated_at)
        change = TaskProgressChange.objects.get(progress=progress)
        self.assertEqual((change.from_status, change.to_status, change.version), ("not_started", "in_progress", 1))
        self.assertEqual(change.actor_id, self.owner.pk)
        self.assertEqual(change.request_key, uuid.UUID(command["request_key"]))
        self.assertEqual(change.note, progress.note)
        self.plan.refresh_from_db()
        self.candidate.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.plan.payload, original)
        self.assertEqual(self.candidate.payload, original)
        self.assertEqual((self.event.active_plan_id, self.event.revision), (self.plan.pk, revision))
        self.assertFalse(TaskProgress.objects.filter(plan=self.plan, task_id="t2").exists())

    def test_success_without_javascript_redirects_to_preparation(self):
        target = _Markup(self.client.get(self.url("detail"))).task_row("t2")
        response = self.post(htmx=False, status="completed", note="Ponente confirmó por correo.")
        next_url = self.url("detail") + "?task=t2#" + target.attrs["id"]
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertEqual(self.progress().status, "completed")
        page = self.client.get(response.url)
        self.assertContains(page, "Estado guardado.")
        self.assertContains(page, "Ponente confirmó por correo.")
        self.assertEqual(len(_Markup(page).find(**{"data-task-percentage": "50"})), 1)
        self.assertContains(page, "1 de 2 tareas completadas")

    def test_htmx_replaces_the_same_row_and_updates_the_authoritative_summary(self):
        initial_row = _Markup(self.client.get(self.url("detail"))).task_row("t1")
        response = self.post(status="completed", note="Trabajo confirmado por el organizador.")
        markup = self.assert_result(response, "saved")
        self.assertEqual(markup.task_row("t1").attrs["id"], initial_row.attrs["id"])
        self.assertEqual(len(markup.find("li", **{"data-task-row": None})), 1)
        self.assertEqual(len(markup.find(**{"data-task-state": "completed"})), 1)
        self.assertEqual(markup.find("input", name="expected_version")[0].attrs["value"], "1")
        summary = markup.find("div", id="task-progress-summary")
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0].attrs["hx-swap-oob"], "outerHTML")
        progress = markup.find("progress")[0]
        self.assertEqual((progress.attrs["value"], progress.attrs["max"]), ("1", "2"))
        self.assertEqual(len(markup.find(**{"data-task-percentage": "50"})), 1)
        self.assertEqual(progress.attrs["aria-valuetext"], "50 %: 1 de 2 tareas completadas")
        self.assertNotContains(response, '<main id="main-content"')

    def test_exact_retry_never_duplicates_or_restores_a_historical_state(self):
        first = self.command(note="Solicitud inicial")
        self.assert_result(self.post(first), "saved")
        self.assert_result(self.post(first), "saved")
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        second = self.command(status="completed", expected_version=1, note="Confirmación recibida")
        self.assert_result(self.post(second), "saved")
        response = self.post(first)
        markup = self.assert_result(response, "saved")
        self.assertEqual((self.progress().status, self.progress().version), ("completed", 2))
        self.assertEqual(TaskProgressChange.objects.count(), 2)
        self.assertEqual(len(markup.find(**{"data-task-state": "completed"})), 1)
        self.assertEqual(markup.find("input", name="expected_version")[0].attrs["value"], "2")

    def test_conflicting_reuse_of_request_key_has_no_new_effect(self):
        command = self.command(note="Primera solicitud")
        self.post(command)
        response = self.post({**command, "status": "completed", "note": "Distinto contenido"})
        self.assert_result(response, "error")
        self.assertContains(response, "ya se utilizó")
        self.assertEqual((self.progress().status, self.progress().version), ("in_progress", 1))
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_stale_version_keeps_current_state_and_returns_a_fresh_command(self):
        self.post()
        stale = self.command(status="completed", note="Nota todavía útil")
        markup = self.assert_result(self.post(stale), "conflict")
        self.assertEqual((self.progress().status, self.progress().version), ("in_progress", 1))
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        self.assertEqual(markup.find("input", name="expected_version")[0].attrs["value"], "1")
        self.assertNotEqual(markup.find("input", name="request_key")[0].attrs["value"], stale["request_key"])
        self.assertEqual(len(markup.find(**{"data-task-state": "in_progress"})), 1)
        self.assertEqual(markup.find("textarea", name="note")[0].text.strip(), stale["note"])

    def test_old_plan_is_read_only_after_approval_and_cannot_update_new_plan(self):
        command = self.command(note="Antes de aprobar otro plan")
        self.post(command)
        _candidate, current_plan = self.approve()
        before = list(TaskProgress.objects.order_by("pk").values())
        response = self.post(command)
        markup = self.assert_result(response, "conflict")
        self.assertFalse(markup.find("form", action=self.url()))
        self.assertFalse(markup.find("div", id="task-progress-summary"))
        links = markup.find("a", href=self.url("detail") + "#preparation")
        self.assertTrue(links)
        self.assertContains(response, "plan vigente cambió")
        self.assertEqual(list(TaskProgress.objects.order_by("pk").values()), before)
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        self.event.refresh_from_db()
        self.assertEqual(self.event.active_plan_id, current_plan.pk)

    def test_completion_requires_a_nonblank_note(self):
        for note in ("", "   "):
            with self.subTest(note=note):
                self.assert_result(self.post(status="completed", note=note), "error")
                self.assert_untouched()
        self.assert_result(self.post(status="completed", note="Confirmado por el organizador"), "saved")
        self.assertEqual(self.progress().status, "completed")

    def test_reopening_requires_a_note_and_records_the_manual_reason(self):
        self.post(status="completed", note="Preparación terminada")
        self.assert_result(self.post(status="not_started", expected_version=1), "error")
        self.assertEqual((self.progress().status, self.progress().version), ("completed", 1))
        self.assertEqual(TaskProgressChange.objects.count(), 1)
        self.assert_result(self.post(status="not_started", expected_version=1, note="El ponente cambió su disponibilidad"), "saved")
        self.assertEqual((self.progress().status, self.progress().version), ("not_started", 2))
        self.assertEqual(TaskProgressChange.objects.get(version=2).from_status, "completed")

    def test_invalid_identifiable_forms_return_local_errors_without_writes(self):
        for changes in ({"status": "verified"}, {"expected_version": -1}, {"expected_version": "one"},
                        {"request_key": "not-a-uuid"}, {"note": "x" * 1001}):
            with self.subTest(changes=changes):
                response = self.post(self.command(**changes))
                markup = self.assert_result(response, "error")
                self.assertIsNotNone(markup.task_row("t1"))
                self.assertTrue([node for node in markup.elements if "field-error" in node.attrs.get("class", "").split()])
                self.assert_untouched()

    def test_bound_note_and_status_survive_escaped_htmx_validation_error(self):
        note = '<script>alert("unsafe")</script>' + "x" * 1000
        command = self.command(status="completed", note=note)
        response = self.post(command)
        markup = self.assert_result(response, "error")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
        self.assertEqual(markup.find("textarea", name="note")[0].text.strip(), note)
        selected = [node for node in markup.find("option") if "selected" in node.attrs]
        self.assertEqual([node.attrs["value"] for node in selected], ["completed"])
        self.assertEqual(markup.find("input", name="request_key")[0].attrs["value"], command["request_key"])
        self.assertEqual(len(markup.find(**{"data-task-state": "not_started"})), 1)
        self.assert_untouched()

    def test_non_htmx_invalid_input_keeps_full_bound_form_in_preparation(self):
        note = "Conservar nota " + "x" * 1000
        response = self.post(self.command(status="completed", note=note), htmx=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context["active_panel"], "preparation")
        markup = _Markup(response)
        self.assertEqual(markup.find("textarea", name="note")[0].text.strip(), note)
        self.assertContains(response, '<main id="main-content"', status_code=400)
        self.assert_untouched()

    def test_non_htmx_stale_version_shows_current_state_and_a_fresh_form(self):
        self.post()
        stale = self.command(status="completed", note="Conservar esta explicación")
        response = self.post(stale, htmx=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context["active_panel"], "preparation")
        markup = _Markup(response)
        self.assertEqual(markup.find("input", name="expected_version")[0].attrs["value"], "1")
        self.assertNotEqual(markup.find("input", name="request_key")[0].attrs["value"], stale["request_key"])
        self.assertEqual(markup.find("textarea", name="note")[0].text.strip(), stale["note"])
        self.assertEqual((self.progress().status, self.progress().version), ("in_progress", 1))
        self.assertEqual(TaskProgressChange.objects.count(), 1)

    def test_saved_notes_are_escaped_in_both_history_and_htmx_fragments(self):
        note = '<img src="x" onerror="alert(1)">Confirmación manual'
        response = self.post(status="completed", note=note)
        self.assert_result(response, "saved")
        self.assertEqual(self.progress().note, note)
        for page in (response, self.client.get(self.url("detail"))):
            with self.subTest(fragment=page is response):
                self.assertContains(page, "&lt;img")
                self.assertNotContains(page, note)
                self.assertNotContains(page, '<img src="x"')
                self.assertContains(page, self.owner.username)

    def test_recent_history_is_limited_to_five_current_plan_changes(self):
        for version in range(7):
            self.post(status="in_progress" if version % 2 == 0 else "not_started",
                      expected_version=version, note=f"Registro manual {version + 1}")
        self.assertEqual(TaskProgressChange.objects.count(), 7)
        response = self.client.get(self.url("detail"))
        self.assertNotContains(response, "Registro manual 1")
        self.assertNotContains(response, "Registro manual 2")
        for number in range(3, 8):
            self.assertContains(response, f"Registro manual {number}", count=1)
        self.assertEqual(self.progress().version, 7)

    def test_inherited_note_keeps_its_origin_after_a_new_manual_transition(self):
        self.assert_result(self.post(status="completed", note="Nota original"), "saved")
        original_progress = self.progress()
        _candidate, current_plan = self.approve()
        inherited = TaskProgress.objects.get(plan=current_plan, task_id="t1")
        self.assertEqual(inherited.carried_from_id, original_progress.pk)
        response = self.post(self.command(expected_plan=str(current_plan.pk), expected_version=1,
                                          status="in_progress", note="Nota reapertura"))
        self.assert_result(response, "saved")
        inherited.refresh_from_db()
        original_progress.refresh_from_db()
        self.assertEqual(original_progress.note, "Nota original")
        self.assertEqual(inherited.note, "Nota reapertura")
        self.assertEqual(inherited.changes.get().note, "Nota reapertura")
        for page in (response, self.client.get(self.url("detail"))):
            with self.subTest(fragment=page is response):
                markup = _Markup(page)
                origin_notes = [node for node in markup.find("p")
                                if "task-carried-note" in node.attrs.get("class", "").split()]
                self.assertEqual([node.text.strip() for node in origin_notes], ["Nota original"])
                current_notes = [node for node in markup.find("p")
                                 if "task-history-note" in node.attrs.get("class", "").split()
                                 and "task-carried-note" not in node.attrs.get("class", "").split()]
                self.assertEqual([node.text.strip() for node in current_notes], ["Nota reapertura"])

    def test_malformed_or_missing_identity_is_bad_request(self):
        for changes in ({"task_id": ""}, {"task_id": "x" * 65}, {"expected_plan": ""}, {"expected_plan": "not-a-uuid"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(self.command(**changes)).status_code, 400)
                self.assert_untouched()

    def test_unknown_task_is_not_found(self):
        self.assertEqual(self.post(task_id="unknown-task").status_code, 404)
        self.assert_untouched()

    def test_a_candidate_alone_has_no_editable_execution_controls(self):
        event = create_event(actor=self.owner, title="Sólo una propuesta", brief="Sin plan aprobado todavía")
        candidate = create_candidate(event=event, actor=self.owner, payload=valid_plan(), base_revision=1)
        response = self.client.get(self.url("detail", event))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["candidate"].pk, candidate.pk)
        self.assertFalse(_Markup(response).find("form", action=self.url(event=event)))
        self.assertFalse(_Markup(response).find(**{"data-task-row": None}))
        self.assert_untouched()

    def test_candidate_preview_does_not_add_editable_controls_to_approved_tasks(self):
        self.event.refresh_from_db()
        create_candidate(event=self.event, actor=self.owner, payload=valid_plan(),
                         base_revision=self.event.revision, base_plan_id=self.plan.pk)
        response = self.client.get(self.url("detail"))
        markup = _Markup(response)
        self.assertEqual(len(markup.find("form", action=self.url())), 2)
        self.assertEqual(len([node for node in markup.find("li") if "data-task-row" in node.attrs]), 2)
        self.assertEqual(len(markup.find("div", id="task-progress-summary")), 1)
        self.assert_untouched()

    def test_rendering_queries_remain_bounded_with_more_progress_and_history(self):
        def populate(plan):
            records = TaskProgress.objects.bulk_create([
                TaskProgress(plan=plan, task_id=task["id"], status="in_progress", updated_by=self.owner)
                for task in plan.payload["tasks"]
            ])
            TaskProgressChange.objects.bulk_create([
                TaskProgressChange(progress=record, from_status="not_started", to_status="in_progress",
                                   version=1, actor=self.owner, request_key=uuid.uuid4())
                for record in records
            ])

        populate(self.plan)
        with CaptureQueriesContext(connection) as small:
            first = self.client.get(self.url("detail"))
        payload = valid_plan()
        payload["tasks"] += [{"id": f"t{number}", "title": f"Preparar material {number}", "depends_on": [],
                              "status": "pending", "purpose": "Revisar manualmente el material"} for number in range(3, 21)]
        _candidate, larger = self.approve(payload)
        # Approval conserves the two existing records. Add only the newly defined tasks.
        extra = deepcopy(larger.payload)
        extra["tasks"] = extra["tasks"][2:]
        records = TaskProgress.objects.bulk_create([
            TaskProgress(plan=larger, task_id=task["id"], status="in_progress", updated_by=self.owner)
            for task in extra["tasks"]
        ])
        TaskProgressChange.objects.bulk_create([
            TaskProgressChange(progress=record, from_status="not_started", to_status="in_progress",
                               version=1, actor=self.owner, request_key=uuid.uuid4()) for record in records
        ])
        with CaptureQueriesContext(connection) as large:
            second = self.client.get(self.url("detail"))
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(len(_Markup(second).find("form", action=self.url())), 20)
        self.assertLessEqual(len(large), len(small) + 1, "La lectura creció por tarea o por historial.")
        # Speaker, proposal history (10) and approved history (20) add three
        # bounded reads. The assertion above still rejects per-task/history N+1.
        self.assertLessEqual(len(large), 17)
