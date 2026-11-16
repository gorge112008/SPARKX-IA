"""Organizer forms for current-plan responsibility and declared evidence."""
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.directory.models import Person
from apps.events.models import Event
from apps.events.services import require_event_owner
from .models import TaskPreparation
from .preparation import PreparationConflict, preparation_rows, update_task_preparation
from .task_progress import TaskPlanConflict


class PreparationForm(forms.Form):
    plan_id = forms.UUIDField(widget=forms.HiddenInput)
    task_id = forms.CharField(max_length=64, widget=forms.HiddenInput)
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    responsible_person = forms.ChoiceField(label="Responsable del directorio", required=False)
    due_at = forms.CharField(label="Fecha límite (opcional)", required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    stage = forms.ChoiceField(label="Preparación declarada", choices=TaskPreparation.Stage.choices)
    evidence_note = forms.CharField(label="Evidencia o motivo de devolución a pendiente", max_length=1000,
        required=False, widget=forms.Textarea(attrs={"rows": 3}))
    evidence_url = forms.URLField(label="Enlace HTTPS a evidencia (opcional)", max_length=1000,
        required=False, assume_scheme="https")

    def __init__(self, *args, event, people, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields["responsible_person"].choices = [("", "Sin responsable")] + [
            (f"{person.pk}:{person.version}", person.full_name) for person in people]

    def clean_responsible_person(self):
        value = self.cleaned_data["responsible_person"]
        if not value:
            return None, None
        identifier, version = value.rsplit(":", 1)
        return uuid.UUID(identifier), int(version)

    def clean_due_at(self):
        value = self.cleaned_data["due_at"]
        if not value:
            return None
        try:
            local = datetime.fromisoformat(value)
            if local.tzinfo is not None or "T" not in value:
                raise ValueError
            zone = ZoneInfo(self.event.timezone)
            first, second = local.replace(tzinfo=zone, fold=0), local.replace(tzinfo=zone, fold=1)
            if first.utcoffset() != second.utcoffset():
                raise ValueError
            return first
        except (ValueError, TypeError) as exc:
            raise forms.ValidationError("Selecciona una hora local válida y sin ambigüedad.") from exc


def _forms(event, people, *, bound=None):
    rows = preparation_rows(event)
    for row in rows:
        record = row["record"]
        prefix = "prep-" + uuid.uuid5(uuid.NAMESPACE_URL, row["task_id"]).hex
        initial = {
            "plan_id": event.active_plan_id, "task_id": row["task_id"], "request_key": uuid.uuid4(),
            "expected_version": record.version if record else 0,
            "stage": record.stage if record else TaskPreparation.Stage.PENDING,
            "responsible_person": f"{record.responsible_person_id}:{record.responsible_person_version}" if record and record.responsible_person_id else "",
            "due_at": record.due_at.astimezone(ZoneInfo(event.timezone)).strftime("%Y-%m-%dT%H:%M") if record and record.due_at else "",
            "evidence_note": record.evidence_note if record else "",
            "evidence_url": record.evidence_url if record else "",
        }
        row["form"] = bound if bound and bound.data.get("task_id") == row["task_id"] else PreparationForm(
            event=event, people=people, initial=initial, auto_id=prefix + "_%s")
    return rows


@login_required
@require_http_methods(["GET", "POST"])
def preparation(request, event_id):
    # Read permission is refreshed, too. Reviewers never receive evidence URLs,
    # private contact choices or forms through this owner-only endpoint.
    actor = get_user_model().objects.filter(pk=request.user.pk).first()
    event = get_object_or_404(Event.objects.select_related("active_plan"), pk=event_id, owner_id=request.user.pk)
    require_event_owner(event, actor)
    people = list(Person.objects.filter(owner_id=actor.pk, is_active=True).order_by("name_key", "pk"))
    form, status = None, 200
    if request.method == "POST":
        form = PreparationForm(request.POST, event=event, people=people)
        if form.is_valid():
            values = form.cleaned_data
            person_id, person_version = values["responsible_person"]
            try:
                update_task_preparation(event=event, actor=request.user,
                    plan_id=values["plan_id"], task_id=values["task_id"], stage=values["stage"],
                    expected_version=values["expected_version"], request_key=values["request_key"],
                    responsible_person_id=person_id, responsible_person_version=person_version,
                    due_at=values["due_at"], evidence_note=values["evidence_note"], evidence_url=values["evidence_url"])
                messages.success(request, "Preparación guardada por el organizador. La ejecución de tareas conserva su estado.")
                return redirect(request.path)
            except ValidationError as exc:
                form.add_error(None, exc)
                status = 409 if isinstance(exc, (PreparationConflict, TaskPlanConflict)) else 400
                event.refresh_from_db()
        else:
            status = 400
    return render(request, "planning/preparation.html", {
        "event": event, "rows": _forms(event, people, bound=form), "submitted_form": form,
    }, status=status)
