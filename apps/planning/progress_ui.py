"""Owner-view projections. Loading a plan never creates progress records."""

import uuid
from urllib.parse import urlencode

from django.db.models import Prefetch
from django.urls import reverse

from apps.events.forms import TaskStatusForm
from .models import TaskProgress, TaskProgressChange
from .templatetags.planning_ui import preparation_rows


def completion_percentage(completed, total):
    """Equal-weight tasks, rounded down so only actual completion reaches 100%."""
    return completed * 100 // total if total else 0


def task_tracking_context(event, *, plan=None, task_id=None, form=None,
                          feedback="", result="", note_hint="", open_task_id=None):
    plan = plan or event.active_plan
    if plan is None:
        return None
    records = TaskProgress.objects.filter(plan=plan).select_related(
        "updated_by", "carried_from__plan",
    ).prefetch_related(Prefetch(
        "changes",
        queryset=TaskProgressChange.objects.select_related("actor").order_by("-version")[:5],
        to_attr="recent_changes",
    ))
    stored = {record.task_id: record for record in records}
    rows = []
    counts = {value: 0 for value, _label in TaskProgress.Status.choices}
    editable = event.active_plan_id == plan.pk
    for position, task in enumerate(preparation_rows(plan.payload), start=1):
        identifier = task["id"].strip()
        progress = stored.get(identifier)
        status = progress.status if progress else TaskProgress.Status.NOT_STARTED
        version = progress.version if progress else 0
        dom_id = "task-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{plan.pk}:{identifier}").hex
        current_form = TaskStatusForm(initial={
            "expected_plan": plan.pk, "task_id": identifier,
            "expected_version": version, "request_key": uuid.uuid4(), "status": status,
            "note": note_hint if identifier == task_id else "",
        }, auto_id=dom_id + "_%s")
        if identifier == task_id and form is not None:
            current_form = form
            current_form.auto_id = dom_id + "_%s"
        if status == TaskProgress.Status.COMPLETED:
            # A completed task offers an explicit reopening command. Merely
            # opening this form does not alter its persisted completion.
            current_form.fields["status"].choices = [
                ("in_progress", "En proceso"), ("not_started", "No iniciado"),
            ]
            if not current_form.is_bound:
                current_form.initial["status"] = TaskProgress.Status.IN_PROGRESS
        current_feedback = feedback if identifier == task_id else ""
        tracking = {
            "status": status, "label": TaskProgress.Status(status).label,
            "version": version, "dom_id": dom_id, "form": current_form,
            "editable": editable, "feedback": current_feedback,
            "result": result if identifier == task_id else "",
            "editor_open": bool(current_feedback and result != "saved")
            or bool(editable and identifier == open_task_id),
            "is_completed": status == TaskProgress.Status.COMPLETED,
            "next_task": None,
            "updated_by": progress.updated_by if progress else None,
            "updated_at": progress.updated_at if progress else None,
            "carried_from_note": (
                progress.carried_from.note if progress and progress.carried_from_id else ""
            ),
            "history": progress.recent_changes if progress else [],
            "carried_from_version": (
                progress.carried_from.plan.version
                if progress and progress.carried_from_id else None
            ),
        }
        rows.append({**task, "position": position, "tracking": tracking})
        counts[status] += 1
    if result == "saved" and editable:
        current_index = next((index for index, row in enumerate(rows) if row["id"].strip() == task_id), None)
        if current_index is not None and rows[current_index]["tracking"]["is_completed"]:
            # Only guide attention. Dependencies and task states are not
            # modified by choosing a next unfinished task in display order.
            ordered = rows[current_index + 1:] + rows[:current_index]
            following = next((row for row in ordered if not row["tracking"]["is_completed"]), None)
            if following:
                identifier = following["id"].strip()
                dom_id = following["tracking"]["dom_id"]
                rows[current_index]["tracking"]["next_task"] = {
                    "id": identifier, "title": following["title"], "dom_id": dom_id,
                    "url": reverse("events:detail", kwargs={"event_id": event.pk})
                    + "?" + urlencode({"task": identifier}) + "#" + dom_id,
                }
    return {
        "rows": rows, "total": len(rows), "not_started": counts["not_started"],
        "in_progress": counts["in_progress"], "completed": counts["completed"],
        "percentage": completion_percentage(counts["completed"], len(rows)),
        "plan": plan,
        "all_completed": bool(rows) and counts["completed"] == len(rows),
        "completion_link_url": reverse("events:detail", kwargs={"event_id": event.pk}) + "#plan",
    }
