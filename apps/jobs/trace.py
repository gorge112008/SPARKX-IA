"""Bounded operational observations. Never model thoughts, prompts or secrets."""

from django.db import transaction
from django.utils import timezone

from .models import Job


STAGES = {
    "queued": ("Solicitud guardada", "El evento y la reserva de presupuesto están vinculados a esta solicitud."),
    "budget_fallback": ("Alternativa gratuita seleccionada", "El presupuesto no cubre la vía principal. Se eligió el único modelo gratuito autorizado, antes de llamar."),
    "free_pool_selected": ("Modelo del grupo gratuito seleccionado", "El servidor eligió un modelo autorizado para esta función y reservó sus límites internos, antes de llamar."),
    "context_ready": ("Contexto preparado", "Ficha y restricciones preparadas para el modelo seleccionado."),
    "request_started": ("Solicitud iniciada", "Se ha iniciado la conexión con el proveedor de IA."),
    "response_received": ("Respuesta recibida", "Llegó una respuesta del proveedor; comienza la comprobación local."),
    "validating": ("Validando resultado", "El servidor comprueba formato, referencias y reglas del evento."),
    "review_ready": ("Propuesta lista para revisar", "Tú decides si apruebas los cambios del plan."),
    "needs_changes": ("Propuesta con observaciones", "Revisa las restricciones indicadas antes de aprobar."),
    "completed": ("Respuesta disponible", "Puedes revisar la respuesta en la conversación."),
    "failed": ("Ejecución detenida", "Revisa el estado del trabajo. No se aplicó un nuevo plan."),
    "cancelled": ("Solicitud cancelada", "Una llamada ya iniciada puede conservar consumo pendiente."),
    "stale": ("Contexto desactualizado", "La ficha cambió; el resultado no se aplicó al plan."),
}


def append_stage(job, stage):
    if stage not in STAGES:
        raise ValueError("Unknown operational stage")
    entries = job.execution_trace if isinstance(job.execution_trace, list) else []
    if any(isinstance(entry, dict) and entry.get("stage") == stage for entry in entries):
        return
    job.execution_trace = entries[:11] + [{"stage": stage, "at": timezone.now().isoformat()}]
    job.save(update_fields=["execution_trace"])


@transaction.atomic
def observe_stage(job_id, token, stage):
    job = Job.objects.select_for_update().get(pk=job_id)
    if (job.status != Job.Status.RUNNING or job.claim_token != token
            or not job.lease_until or job.lease_until <= timezone.now()):
        raise ValueError("Execution no longer owns this observation")
    append_stage(job, stage)


def trace_rows(job):
    """Only allowlisted server observations are rendered, including old jobs."""
    if job is None:
        return []
    entries = job.execution_trace if isinstance(job.execution_trace, list) else []
    rows = []
    from datetime import datetime
    for entry in entries[:12]:
        if not isinstance(entry, dict) or entry.get("stage") not in STAGES:
            continue
        try:
            when = datetime.fromisoformat(entry["at"])
            if when.tzinfo is None:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        label, detail = STAGES[entry["stage"]]
        rows.append({"stage": entry["stage"], "label": label, "detail": detail, "at": when})
    if rows:
        rows[-1]["current"] = job.status in {Job.Status.QUEUED, Job.Status.RUNNING}
    return rows
