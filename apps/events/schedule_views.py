"""Manual agenda changes create a reviewable proposal and preserve the active plan."""
from copy import deepcopy
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.assistant.local_commands import human_organizer
from apps.planning.services import create_candidate
from .models import Event


class SessionTimeForm(forms.Form):
    session_id = forms.CharField(max_length=64, widget=forms.HiddenInput)
    start = forms.CharField(max_length=30, label="Inicio", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    duration_minutes = forms.IntegerField(min_value=1, max_value=1440, label="Minutos")

    def clean_start(self):
        value = self.cleaned_data["start"]
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
                raise ValueError
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is not None:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise forms.ValidationError("Selecciona una fecha y hora locales válidas.") from error
        return parsed


SessionTimeSet = formset_factory(SessionTimeForm, extra=0, min_num=1, max_num=200, validate_min=True, validate_max=True, absolute_max=200)


@login_required
@require_http_methods(["GET", "POST"])
def schedule_editor(request, event_id):
    actor = human_organizer(request.user)
    event = get_object_or_404(Event.objects.select_related("active_plan"), pk=event_id, owner=actor, archived_at__isnull=True)
    if not event.active_plan_id:
        return redirect("events:detail", event_id=event.pk)
    sessions = event.active_plan.payload["sessions"]
    zone = ZoneInfo(event.timezone)
    initial = [{"session_id": row["id"], "start": datetime.fromisoformat(row["start"]).astimezone(zone).strftime("%Y-%m-%dT%H:%M"), "duration_minutes": row["duration_minutes"]} for row in sessions]
    formset = SessionTimeSet(request.POST if request.method == "POST" else None, initial=initial, prefix="sessions")
    error = ""
    response_status = 200
    if request.method == "POST" and formset.is_valid():
        try:
            with transaction.atomic():
                event = get_object_or_404(Event.objects.select_for_update().select_related("active_plan"),
                    pk=event.pk, owner=actor, archived_at__isnull=True)
                if str(event.revision) != request.POST.get("expected_revision") or str(event.active_plan_id) != request.POST.get("expected_plan"):
                    response_status = 409
                    raise ValidationError("La ficha o la agenda cambió. Recarga antes de proponer otro horario.")
                payload = deepcopy(event.active_plan.payload)
                by_id = {row["id"]: row for row in payload["sessions"]}
                ids = [form.cleaned_data["session_id"] for form in formset]
                if len(ids) != len(set(ids)) or set(ids) != set(by_id):
                    raise ValidationError("La propuesta debe conservar todas las sesiones de la agenda vigente.")
                for form in formset:
                    values = form.cleaned_data
                    local = values["start"].replace(tzinfo=zone)
                    candidates = {values["start"].replace(tzinfo=zone, fold=fold).astimezone(ZoneInfo("UTC")) for fold in (0, 1)
                                  if values["start"].replace(tzinfo=zone, fold=fold).astimezone(ZoneInfo("UTC")).astimezone(zone).replace(tzinfo=None) == values["start"]}
                    if len(candidates) != 1:
                        raise ValidationError("Ese horario no existe o es ambiguo en la zona del evento.")
                    by_id[values["session_id"]].update(start=local.isoformat(), duration_minutes=values["duration_minutes"])
                payload["summary"] = "Ajuste manual de horarios sobre la versión aprobada. Revisa los cambios antes de aprobar."
                candidate = create_candidate(event=event, actor=actor, payload=payload, base_revision=event.revision, base_plan_id=event.active_plan_id)
            return redirect(reverse("events:detail", args=[event.pk]) + "#candidate")
        except ValidationError as issue:
            error = " ".join(issue.messages)
    return render(request, "events/schedule_editor.html", {"event": event, "formset": formset, "schedule_rows": list(zip(sessions, formset)), "schedule_error": error}, status=response_status)
