"""Private local review artifacts. No public download, approval or network."""
import json
import os
from pathlib import Path
import tempfile
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.ai_management.models import AIUsage
from apps.events.models import Event
from apps.events.services import require_event_owner
from apps.jobs.models import Job
from apps.planning.event_rules import validate_event_plan
from apps.planning.models import PlanCandidate
from .compact_contract import validate_response
from .compact_planning import ALLOWED_MODELS, OPENAI_MODELS, compact_wire, expand_proposal, authorized_compact_job
from .demo_pilot import PILOT_EVENT_ID
from .local_commands import human_organizer
from .models import CompactPlanRequest

MAX_ARCHIVE_BYTES = 64000


def _archive_error():
    raise ValidationError("No se pudo guardar la agenda en Temporal. La propuesta se conserva; vuelve a guardar sin generar otra solicitud.", code="compact_archive_failed")


def _safe_target(actor_id, job_id):
    if type(actor_id) is not int or actor_id <= 0:
        _archive_error()
    base = Path(settings.BASE_DIR).absolute()
    target = base / "Temporal" / "gica-agenda-review" / str(actor_id) / (str(uuid.UUID(str(job_id))) + ".json")
    # Reject redirecting directories and files, including Windows junctions.
    for path in [target, *target.parents]:
        if path == base:
            break
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            _archive_error()
    if not target.resolve().is_relative_to((base / "Temporal").resolve()):
        _archive_error()
    return target


def _store(actor_id, job_id, payload):
    temporary = None
    try:
        target = _safe_target(actor_id, job_id)
        content = (json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if len(content) > MAX_ARCHIVE_BYTES:
            _archive_error()
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _safe_target(actor_id, job_id)
        if target.exists():
            if not target.is_file() or target.stat().st_size > MAX_ARCHIVE_BYTES or target.read_bytes() != content:
                _archive_error()
            return
        with tempfile.NamedTemporaryFile(mode="wb", prefix="." + str(job_id) + "-", suffix=".tmp", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _safe_target(actor_id, job_id)
        os.replace(temporary, target)
        temporary = None
    except (OSError, ValueError, TypeError, OverflowError):
        _archive_error()
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


@transaction.atomic
def archive_compact(*, actor, event_id, run_id, job_id):
    actor = human_organizer(actor)
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    human_organizer(actor)
    record = CompactPlanRequest.objects.select_related("job").filter(job_id=job_id, run_id=run_id,
        job__event=event, job__actor=actor, version=1, job__status=Job.Status.SUCCEEDED).first()
    if record is None:
        raise ValidationError("La agenda todavía no está disponible para guardar.")
    job = Job.objects.select_for_update().get(pk=record.job_id)
    if job.base_revision != event.revision or job.base_plan_id != event.active_plan_id:
        raise ValidationError("La ficha o el plan cambiaron. No se archivó una agenda obsoleta.", code="compact_stale")
    usage = AIUsage.objects.filter(job=job).first()
    if usage is None or not authorized_compact_job(job, usage.snapshot):
        raise ValidationError("La agenda no procede de una solicitud compacta autorizada.")
    response = validate_response(record.response, round_number=record.round_number)
    if response["state"] != "proposal":
        raise ValidationError("Responde las preguntas antes de guardar la agenda.")
    expanded = expand_proposal(event, record, response)
    if validate_event_plan(event, expanded):
        raise ValidationError("La agenda necesita corregir sus restricciones antes de guardarse.")
    if record.review_only:
        if job.result.get("compact_state") != "private_ready" or job.result.get("candidate_id"):
            raise ValidationError("La respuesta privada no tiene el estado esperado.")
    else:
        candidate = PlanCandidate.objects.select_for_update().filter(pk=job.result.get("candidate_id"), event=event,
            created_by=actor, status=PlanCandidate.Status.PENDING, base_revision=event.revision, base_plan_id=event.active_plan_id).first()
        if candidate is None or candidate.validation or candidate.payload != expanded:
            raise ValidationError("La propuesta ya no está pendiente o cambió.")
    wire = compact_wire(record.context, usage.snapshot)
    model = usage.snapshot.get("model")
    if model not in ALLOWED_MODELS | OPENAI_MODELS:
        raise ValidationError("El modelo no pertenece al grupo autorizado de este piloto.")
    preview = {"version": 1, "instructions": wire["system_prompt"], "context": record.context,
        "max_input_tokens": usage.snapshot["max_input_tokens"], "max_output_tokens": usage.snapshot["max_output_tokens"],
        **{key: value for key, value in wire.items() if key != "payload"}}
    counters = {key: value for key, value in (job.result.get("usage") or {}).items()
        if key in {"input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"}
        and type(value) is int and 0 <= value <= 2_000_000_000}
    payload = {"v": 1, "purpose": "private_review", "review_only": record.review_only,
        "event_id": str(event.pk), "job_id": str(job.pk), "run_id": str(record.run_id),
        "base_revision": job.base_revision, "created_at": record.created_at.isoformat(),
        "provider": usage.snapshot["provider"], "model": model, "usage": counters or None,
        "public_prompt": {key: preview[key] for key in ("version", "instructions", "system_prompt", "user_prompt", "prompt_text", "context", "max_input_tokens", "max_output_tokens")},
        "response": response, "agenda": expanded}
    if "response_schema" in preview:
        payload["public_prompt"]["response_schema"] = preview["response_schema"]
    _store(actor.pk, job.pk, payload)
    return {"run_id": str(record.run_id), "event_id": str(event.pk), "job_id": str(job.pk), "status": "archived", "saved": True}
