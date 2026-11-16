"""Explicit organizer-reviewed planning constraints and mechanical repair."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.directory.queries import people_for
from apps.directory.models import Person
from apps.planning.constraints import normalize_constraints, repair_plan
from apps.planning.event_rules import context_constraints
from apps.planning.models import PlanCandidate
from apps.planning.services import create_candidate
from .models import Event
from .services import require_event_owner


class ConstraintsForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    start = forms.CharField(label="Inicio de la ventana disponible", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    end = forms.CharField(label="Fin de la ventana disponible", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    speakers = forms.ModelMultipleChoiceField(label="Expositores habilitados", queryset=Person.objects.none(),
        help_text="Selecciona hasta tres. Declaras que están disponibles en toda la ventana, salvo sus otras agendas aprobadas.")

    def __init__(self, *args, event, actor, **kwargs):
        self.event = event
        self.sessions = event.active_plan.payload["sessions"] if event.active_plan_id else []
        initial = {"expected_revision": event.revision}
        window = event.planning_constraints.get("window", {})
        start = datetime.fromisoformat(window["start"]) if window else event.starts_at
        end = datetime.fromisoformat(window["end"]) if window else (start + timedelta(hours=3) if start else None)
        for key, value in (("start", start), ("end", end)):
            if value:
                initial[key] = value.astimezone(ZoneInfo(event.timezone)).strftime("%Y-%m-%dT%H:%M")
        initial["speakers"] = [item["id"] for item in event.planning_people]
        fixed = {item["session_id"]: item for item in event.planning_constraints.get("fixed", [])}
        for index, session in enumerate(self.sessions):
            for field in ("start", "speaker", "resource", "duration_minutes"):
                initial[f"fixed_{index}_{field}"] = field in fixed.get(session["id"], {})
        kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)
        choices = people_for(actor).filter(category=Person.Category.SPEAKER, is_active=True)
        if event.is_synthetic:
            choices = choices.filter(is_synthetic=True)
        self.fields["speakers"].queryset = choices.order_by("full_name", "pk")
        labels = {"start": "Conservar horario", "speaker": "Conservar expositor", "resource": "Conservar recurso", "duration_minutes": "Conservar duración"}
        self.session_fields = []
        for index, session in enumerate(self.sessions):
            fields = []
            for field, label in labels.items():
                key = f"fixed_{index}_{field}"
                self.fields[key] = forms.BooleanField(required=False, label=label)
                fields.append(self[key])
            self.session_fields.append({"session": session, "fields": fields})

    def clean(self):
        values = super().clean()
        zone = ZoneInfo(self.event.timezone)
        for key in ("start", "end"):
            if key not in values:
                continue
            try:
                local = datetime.fromisoformat(values[key])
                if local.tzinfo is not None or "T" not in values[key]:
                    raise ValueError
                first, second = local.replace(tzinfo=zone, fold=0), local.replace(tzinfo=zone, fold=1)
                if first.utcoffset() != second.utcoffset():
                    raise ValueError
                values[key] = first
            except (ValueError, TypeError):
                self.add_error(key, "Selecciona una hora local válida y sin ambigüedad.")
        if "speakers" in values and not 1 <= len(values["speakers"]) <= 3:
            self.add_error("speakers", "Selecciona entre uno y tres expositores.")
        return values

    def canonical(self):
        values = self.cleaned_data
        window = {key: values[key].isoformat() for key in ("start", "end")}
        people = list(values["speakers"])
        resources = sorted({session["resource"].strip() for session in self.sessions if session["resource"].strip()})
        fixed = []
        for index, session in enumerate(self.sessions):
            item = {"session_id": session["id"]}
            for field in ("start", "speaker", "resource", "duration_minutes"):
                if values.get(f"fixed_{index}_{field}"):
                    item[field] = session[field]
            if len(item) > 1:
                fixed.append(item)
        constraints = normalize_constraints({"version": 1, "window": window, "max_duration_minutes": 1440,
            "speakers": [{"name": person.full_name, "windows": [window], "busy": []} for person in people],
            "resources": [{"name": name, "windows": [window], "busy": []} for name in resources],
            "sessions": [{"session_id": session["id"], "allowed_speakers": [person.full_name for person in people],
                          "allowed_resources": resources} for session in self.sessions], "fixed": fixed})
        references = [{"id": str(person.pk), "version": person.version, "name": person.full_name} for person in people]
        return constraints, references


def _owned(actor, event_id):
    event = get_object_or_404(Event.objects.select_related("active_plan"), pk=event_id, owner_id=actor.pk)
    require_event_owner(event, actor)
    return event


@login_required
@require_http_methods(["GET", "POST"])
def configure(request, event_id):
    event = _owned(request.user, event_id)
    if not event.active_plan_id or not 1 <= len(event.active_plan.payload["sessions"]) <= 12:
        messages.error(request, "Esta preparación de restricciones necesita un plan aprobado con entre una y doce sesiones.")
        return redirect("events:detail", event_id=event.pk)
    form = ConstraintsForm(request.POST if request.method == "POST" else None, event=event, actor=request.user)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                current = Event.objects.select_for_update().get(pk=event.pk)
                actor = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                require_event_owner(current, actor)
                if current.revision != form.cleaned_data["expected_revision"] or current.active_plan_id != event.active_plan_id:
                    status = 409
                    raise ValidationError("El evento cambió. Recarga y revisa sus decisiones antes de guardar.")
                constraints, people = form.canonical()
                changed = constraints != current.planning_constraints or people != current.planning_people
                current.planning_constraints, current.planning_people = constraints, people
                context_constraints(current)
                current.full_clean()
                if changed:
                    current.revision += 1
                    current.save(update_fields=["planning_constraints", "planning_people", "revision", "updated_at"])
        except (ValueError, ValidationError) as error:
            form.add_error(None, " ".join(error.messages) if isinstance(error, ValidationError) else str(error))
            status = status if status == 409 else 400
        else:
            messages.success(request, "Restricciones guardadas. El plan aprobado se conserva; las propuestas anteriores requieren actualización.")
            return redirect("events:constraints", event_id=event.pk)
    elif request.method == "POST":
        status = 400
    return render(request, "events/constraints.html", {"event": event, "form": form}, status=status)


@login_required
@require_POST
def repair(request, event_id):
    event = _owned(request.user, event_id)
    try:
        with transaction.atomic():
            current = Event.objects.select_for_update().get(pk=event.pk)
            actor = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            require_event_owner(current, actor)
            if str(current.revision) != request.POST.get("expected_revision"):
                raise ValidationError("El evento cambió. Revisa las restricciones antes de calcular.")
            if not current.active_plan_id or not current.planning_constraints:
                raise ValidationError("Guarda primero las restricciones de un plan aprobado.")
            result = repair_plan(current.active_plan.payload, context_constraints(current))
            if result["status"] != "candidate":
                return render(request, "events/repair_result.html", {"event": current, "repair": result})
            previous = PlanCandidate.objects.filter(event=current, base_revision=current.revision, status="pending", payload=result["payload"]).first()
            candidate = previous or create_candidate(event=current, actor=actor, payload=result["payload"],
                base_revision=current.revision, base_plan_id=current.active_plan_id)
            if candidate.validation:
                raise ValidationError(candidate.validation)
    except (ValueError, ValidationError) as error:
        messages.error(request, " ".join(error.messages) if isinstance(error, ValidationError) else str(error))
        return redirect("events:constraints", event_id=event.pk)
    messages.success(request, "Alternativa calculada localmente, sin IA. Revisa la propuesta antes de aprobar; no se cambió el plan.")
    return redirect("events:detail", event_id=event.pk)
