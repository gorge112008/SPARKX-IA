"""Guided rehearsal using explicit manual examples and normal approval services."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import can_organize
from apps.planning.domain import plan_impact, validate_plan
from apps.planning.models import PlanCandidate
from apps.planning.progress_ui import task_tracking_context
from apps.planning.services import StalePlanError

from .journey_demo import JOURNEY_EVENT_ID, ensure_journey_proposal, get_journey_demo_context
from .models import Event


class JourneyScenarioForm(forms.Form):
    scenario = forms.ChoiceField(choices=[(key, key) for key in ("baseline", "change", "conflict")])
    expected_revision = forms.IntegerField(min_value=1)
    expected_plan_id = forms.UUIDField(required=False)


def _context(event, *, errors=()):
    journey = get_journey_demo_context(event)
    candidate = event.candidates.filter(
        status=PlanCandidate.Status.PENDING,
        base_revision=event.revision, base_plan_id=event.active_plan_id,
    ).order_by("-created_at", "-pk").first()
    progress = task_tracking_context(event)
    changed = journey["original_spec"] and journey["is_change_active"]
    finished = bool(changed and progress and progress["total"] and progress["completed"] == progress["total"])
    if not journey["original_spec"]:
        stage, title, description = (
            "custom", "Conservamos tus cambios en la ficha",
            "Los ejemplos corresponden a la ficha original. Tu edición permanece guardada; puedes continuar desde el evento normal sin que esta guía reemplace tus requisitos.",
        )
    elif not event.active_plan_id:
        stage, title, description = (
            "review", "Revisa tu primera propuesta",
            "La ficha y una propuesta manual están preparadas. Revisa horarios y tareas antes de aprobar; todavía no hay un plan vigente.",
        )
    elif finished:
        stage, title, description = (
            "complete", "Recorrido de preparación completado",
            "Aprobaste el cambio y marcaste las tareas del ensayo como completadas. Esto acredita un recorrido de software con datos ficticios, no la celebración de un evento.",
        )
    elif changed:
        stage, title, description = (
            "tracking", "Comprueba el avance de preparación",
            "El cambio ya forma parte del plan vigente. Se revisan el ensayo y su cierre dependiente; consulta el avance heredado y actualiza las tareas desde Preparación.",
        )
    elif journey["is_baseline_active"]:
        stage, title, description = (
            "adapt", "Ensaya un cambio antes de aplicarlo",
            "El plan base está aprobado. Puedes registrar un avance de ejemplo y comparar la ampliación de la práctica; la alternativa no se aplica hasta que la apruebes.",
        )
    else:
        stage, title, description = (
            "custom", "Conservamos tu plan personalizado",
            "Tu plan ya no coincide con los ejemplos originales. El recorrido no lo sobrescribe ni reinicia; puedes consultar su agenda y continuar el seguimiento.",
        )
    journey.update({
        "stage": stage, "stage_title": title, "stage_description": description,
        "baseline_available": journey["can_prepare_baseline"],
        "change_available": journey["can_prepare_change"],
        "conflict_available": journey["can_check_conflict"],
    })
    guide_steps = [
        {"name": "Contexto", "description": "Ficha de ejemplo guardada con datos ficticios.", "done": True, "current": False},
        {"name": "Propuesta", "description": "Contenido manual que puedes revisar y descartar.", "done": bool(event.active_plan_id), "current": not event.active_plan_id},
        {"name": "Aprobación", "description": "Tú decides cuándo activar el plan mostrado.", "done": bool(event.active_plan_id), "current": False},
        {"name": "Adaptación", "description": "Comparar y aprobar quince minutos adicionales.", "done": changed, "current": bool(event.active_plan_id and not changed)},
        {"name": "Seguimiento", "description": "Estados y porcentaje calculados desde tus registros.", "done": finished, "current": changed and not finished},
    ]
    return {
        "event": event, "journey": journey, "guide_steps": guide_steps,
        "candidate": candidate, "plan": event.active_plan.payload if event.active_plan_id else None,
        "progress": progress, "validation_errors": list(errors),
        "impact": plan_impact(event.active_plan.payload if event.active_plan_id else None, candidate.payload)
        if candidate and not candidate.validation and not validate_plan(candidate.payload) else None,
    }


@login_required
@require_http_methods(["GET", "POST"])
def journey_demo(request, event_id):
    # A normal event must never become writable through a demo-only shortcut.
    if event_id != JOURNEY_EVENT_ID:
        raise Http404
    event = get_object_or_404(Event.objects.select_related("active_plan"), pk=event_id, owner=request.user)
    if not can_organize(request.user):
        raise PermissionDenied
    errors, status = [], 200
    if request.method == "POST":
        form = JourneyScenarioForm(request.POST)
        if request.POST.get("action", "scenario") != "scenario":
            errors, status = ["La acción solicitada no es válida."], 400
        elif not form.is_valid():
            errors = [str(error) for values in form.errors.values() for error in values]
            status = 400
        else:
            try:
                ensure_journey_proposal(actor=request.user, event_id=event.pk, **form.cleaned_data)
            except StalePlanError as error:
                errors, status = error.messages, 409
            except ValidationError as error:
                errors, status = error.messages, 400
            else:
                messages.success(request, "Propuesta de ejemplo preparada. Revisa los cambios antes de aprobar; no se utilizó IA.")
                return redirect("events:journey_demo", event_id=event.pk)
        event.refresh_from_db()
    return render(request, "events/journey_demo.html", _context(event, errors=errors), status=status)
