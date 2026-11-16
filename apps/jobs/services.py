"""Owner-scoped jobs with short transactions and fenced result publication.

Lock order is Event, User, AIAccount, Job, then AIUsage. Enqueue also
locks its actor to serialize actor-wide daily quotas and financial reservations.
Provider calls are outside transactions. Expired calls are never auto-retried:
a lease expiry cannot establish whether the remote provider billed a request.
"""

from datetime import datetime, time, timedelta
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import logging
import threading
from types import SimpleNamespace
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.events.models import Event
from apps.events.services import require_event_owner
from apps.ai_management.models import AIAccount, AIUsage
from apps.ai_management.services import (
    authorize_snapshot, current_month, ensure_account_within_limits, get_account, mark_dispatched,
    mark_uncertain, release_undispatched, reserve_job_locked, settle_usage_locked,
)
from .models import Job
from .trace import append_stage, observe_stage

logger = logging.getLogger(__name__)
PENDING = (Job.Status.QUEUED, Job.Status.RUNNING)
EXPIRED_MESSAGE = "El tiempo de ejecución venció. La llamada remota puede haberse consumido; revisa antes de solicitar otro trabajo."
FAILED_MESSAGE = "No se pudo completar el trabajo. El plan vigente se conserva; revisa la configuración y vuelve a solicitarlo si corresponde."
STALE_MESSAGE = "El evento o su plan vigente cambió. Solicita una propuesta con los datos actuales."


class IdempotencyConflict(ValidationError):
    def __init__(self):
        super().__init__("La clave de solicitud ya se utilizó con otro contenido.", code="idempotency_conflict")


def _active_owner(event, actor):
    require_event_owner(event, actor)
    if not getattr(actor, "is_active", False):
        raise PermissionDenied("La cuenta ya no tiene acceso para esta operación.")


def _normalize_request(kind, prompt, idempotency_key):
    if kind not in Job.Kind.values:
        raise ValidationError("El tipo de trabajo no es válido.")
    if not isinstance(prompt, str) or not 3 <= len(prompt.strip()) <= 6000:
        raise ValidationError("Escribe una solicitud de entre 3 y 6000 caracteres.")
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key.strip()) <= 128:
        raise ValidationError("La solicitud requiere una clave válida de hasta 128 caracteres.")
    prompt = prompt.strip()
    key = idempotency_key.strip()
    canonical = json.dumps({"kind": kind, "prompt": prompt}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return prompt, key, request_hash


@transaction.atomic
def enqueue(*, event, actor, kind, prompt, idempotency_key, model_policy_token=None):
    prompt, key, request_hash = _normalize_request(kind, prompt, idempotency_key)
    current = Event.objects.select_for_update().get(pk=event.pk)
    _active_owner(current, actor)
    # Serialize quotas across this actor's different events, not just one event.
    current_actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    _active_owner(current, current_actor)
    previous = Job.objects.filter(event=current, actor=current_actor, idempotency_key=key).first()
    if previous is not None:
        if previous.request_hash != request_hash:
            raise IdempotencyConflict()
        return previous
    account = get_account(current_actor)
    account = AIAccount.objects.select_for_update().get(pk=account.pk)
    from apps.ai_management.agent_access import chosen_snapshot
    snapshot = chosen_snapshot(account=account, event=current, actor=current_actor,
        kind=kind, key=key, token=model_policy_token)
    if snapshot["provider"] == "opencode" and not current.is_synthetic:
        raise ValidationError("La demostración gratuita solo admite eventos marcados como ficticios.", code="synthetic_required")
    today = timezone.localdate()
    zone = timezone.get_current_timezone()
    day_start = datetime.combine(today, time.min, tzinfo=zone)
    day_end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
    daily_count = Job.objects.filter(actor=current_actor, created_at__gte=day_start, created_at__lt=day_end).count()
    if daily_count >= max(0, int(getattr(settings, "AI_DAILY_JOB_LIMIT", 20))):
        raise ValidationError("Alcanzaste el límite diario de solicitudes de IA.", code="daily_budget")
    if Job.objects.filter(event=current, status__in=PENDING).count() >= max(0, int(getattr(settings, "AI_MAX_PENDING_PER_EVENT", 3))):
        raise ValidationError("Este evento ya tiene el máximo de trabajos pendientes. Espera o cancela uno.", code="pending_budget")
    job = Job.objects.create(
        event=current, actor=current_actor, kind=kind, prompt=prompt,
        base_revision=current.revision, base_plan_id=current.active_plan_id,
        request_hash=request_hash, idempotency_key=key,
    )
    reserve_job_locked(job=job, account=account, snapshot=snapshot)
    append_stage(job, "queued")
    if snapshot.get("agent_route") == "fallback_budget":
        append_stage(job, "budget_fallback")
    if snapshot.get("agent_route") in {"free_pool", "free_pool_budget"}:
        append_stage(job, "free_pool_selected")
    return job


def _clear_claim(job, *, status, error="", result=None):
    job.status = status
    job.claim_token = None
    job.lease_until = None
    job.error = error
    job.result = {} if result is None else result
    job.save(update_fields=["status", "claim_token", "lease_until", "error", "result", "updated_at"])
    final_stage = {Job.Status.FAILED: "failed", Job.Status.CANCELLED: "cancelled", Job.Status.STALE: "stale"}.get(status)
    if final_stage:
        append_stage(job, final_stage)


def _lock_event_job(job_id):
    event_id, actor_id = Job.objects.values_list("event_id", "actor_id").get(pk=job_id)
    event = Event.objects.select_for_update().get(pk=event_id)
    actor = get_user_model().objects.select_for_update().get(pk=actor_id)
    account = get_account(actor)
    AIAccount.objects.select_for_update().get(pk=account.pk)
    job = Job.objects.select_for_update().get(pk=job_id, event_id=event.pk)
    job.actor = actor
    return event, job


def _financial(job):
    return AIUsage.objects.select_for_update().filter(job=job).first()


def _close_financial(job, reason=""):
    usage = _financial(job)
    if usage is None:
        return
    if usage.dispatch_token is None:
        release_undispatched(usage, reason or "No se envió una solicitud al proveedor.")
    else:
        mark_uncertain(usage, reason or "La llamada pudo consumirse; conserva la reserva hasta conciliar.")


def _has_claim(job, token, usage=None):
    if job.status != Job.Status.RUNNING or job.claim_token != token or token is None:
        return False
    if job.lease_until is None or job.lease_until <= timezone.now():
        _close_financial(job, "El intento venció; el consumo remoto puede seguir pendiente.")
        _clear_claim(job, status=Job.Status.FAILED, error=EXPIRED_MESSAGE, result={"usage": usage} if usage else {})
        return False
    return True


def _snapshot_current(event, job):
    return event.revision == job.base_revision and event.active_plan_id == job.base_plan_id


@transaction.atomic
def cancel(*, job_id, actor):
    event, job = _lock_event_job(job_id)
    _active_owner(event, actor)
    _active_owner(event, job.actor)
    if job.status == Job.Status.CANCELLED:
        return job
    if job.status not in PENDING:
        raise ValidationError("Este trabajo ya terminó y no puede cancelarse.")
    # Revoking the token fences a response even if the remote call continues.
    _close_financial(job, "Trabajo cancelado; una solicitud ya enviada puede haberse consumido.")
    _clear_claim(job, status=Job.Status.CANCELLED)
    return job


@transaction.atomic
def _expire_job(job_id, max_attempts):
    _event, job = _lock_event_job(job_id)
    expired = job.status == Job.Status.RUNNING and job.lease_until is not None and job.lease_until <= timezone.now()
    exhausted = job.status == Job.Status.QUEUED and job.attempt >= max_attempts
    if not expired and not exhausted:
        return
    _close_financial(job, "El intento venció; el consumo remoto puede seguir pendiente." if expired else "No se envió una solicitud al proveedor.")
    _clear_claim(job, status=Job.Status.FAILED, error=EXPIRED_MESSAGE if expired else "Este trabajo alcanzó el máximo de intentos permitido.")


def claim_next(*, job_id=None):
    now = timezone.now()
    max_attempts = max(1, int(getattr(settings, "JOB_MAX_ATTEMPTS", 2)))
    # Close one job at a time in the same lock order as enqueue/cancel. Never
    # bulk-update leases: every reservation must remain accounted for.
    from django.db.models import Q
    expiring = Job.objects.filter(
        Q(status=Job.Status.RUNNING, lease_until__lte=now)
        | Q(status=Job.Status.QUEUED, attempt__gte=max_attempts)
    )
    if job_id is not None:
        expiring = expiring.filter(pk=job_id)
    expired_ids = list(expiring.values_list("pk", flat=True)[:1000])
    for job_id in expired_ids:
        _expire_job(job_id, max_attempts)
    with transaction.atomic():
        queued = Job.objects.filter(status=Job.Status.QUEUED, attempt__lt=max_attempts).order_by("created_at", "id")
        if job_id is not None:
            queued = queued.filter(pk=job_id)
        if connection.features.has_select_for_update_skip_locked:
            queued = queued.select_for_update(skip_locked=True)
        else:
            queued = queued.select_for_update()
        job = queued.first()
        if job is None:
            return None
        job.status = Job.Status.RUNNING
        job.attempt += 1
        job.claim_token = uuid.uuid4()
        job.lease_until = now + timedelta(seconds=max(1, int(getattr(settings, "JOB_LEASE_SECONDS", 120))))
        job.error = ""
        job.save(update_fields=["status", "attempt", "claim_token", "lease_until", "error", "updated_at"])
        return job


@transaction.atomic
def _prepare(job_id, token):
    event, job = _lock_event_job(job_id)
    if not _has_claim(job, token):
        return None
    try:
        _active_owner(event, job.actor)
    except PermissionDenied:
        _close_financial(job, "El solicitante ya no tiene permiso; no se llamó al proveedor.")
        _clear_claim(job, status=Job.Status.FAILED, error="El solicitante ya no tiene permiso para este evento.")
        return None
    if not _snapshot_current(event, job):
        _close_financial(job, "La ficha cambió antes de llamar al proveedor.")
        _clear_claim(job, status=Job.Status.STALE, error=STALE_MESSAGE)
        return None
    usage = _financial(job)
    if usage is None:
        _clear_claim(job, status=Job.Status.FAILED, error="Este trabajo no tiene una reserva de IA válida.")
        return None
    if usage.dispatch_token is not None:
        # A second worker/process_claim invocation must not issue a second call.
        return None
    if usage.month != current_month():
        release_undispatched(usage, "La reserva pertenece a otro mes; no se llamó al proveedor.")
        _clear_claim(job, status=Job.Status.FAILED,
                     error="Cambió el mes del presupuesto. Crea una nueva solicitud para reservar con los límites actuales.")
        return None
    try:
        account = AIAccount.objects.get(pk=usage.account_id)
        authorize_snapshot(account, usage.snapshot)
        from apps.ai_management.model_policy import validate_job_consent
        validate_job_consent(usage.snapshot, event=event, actor=job.actor,
            kind=job.kind, request_key=job.idempotency_key)
        from apps.assistant.compact_planning import authorized_compact_job, freeze_compact
        compact = authorized_compact_job(job, usage.snapshot)
        if usage.snapshot.get("provider") == "opencode" and not event.is_synthetic and not compact:
            raise ValidationError("La demostración gratuita requiere un evento ficticio.")
        ensure_account_within_limits(account, usage.month, snapshot=usage.snapshot)
        from apps.assistant import provider
        from apps.planning.event_rules import context_constraints
        event._planning_snapshot = context_constraints(event)
        if not provider.profile_ready(usage.snapshot):
            raise ValidationError("El proveedor no está configurado.")
        # Task writers share this Event lock. Freeze chat state and history once
        # so budget preflight and the remote request use the same observation.
        conversation = (provider.chat_context(event)
            if job.kind == Job.Kind.CHAT and usage.snapshot.get("provider") != "openai" else None)
        if usage.snapshot.get("provider") == "openai" and not compact:
            event._openai_context_snapshot = provider.freeze_openai_context(
                event=event, prompt=job.prompt, action=job.kind, snapshot=usage.snapshot,
            )
        if compact:
            event._compact_context_snapshot = freeze_compact(event, job, usage.snapshot)
        elif usage.snapshot.get("provider") == "opencode":
            event._free_context_snapshot = provider.freeze_free_context(
                event=event, prompt=job.prompt, action=job.kind, conversation=conversation,
                snapshot=usage.snapshot,
            )
        if not compact:
            provider.ensure_input_fits(
                event=event, kind=job.kind, prompt=job.prompt, snapshot=usage.snapshot,
                conversation=conversation,
            )
    except Exception:
        release_undispatched(usage, "La comprobación previa falló; no se llamó al proveedor.")
        _clear_claim(job, status=Job.Status.FAILED, error="No se pudo preparar la solicitud. Revisa el perfil y sus límites.")
        return None
    append_stage(job, "context_ready")
    try:
        if not mark_dispatched(usage, token):
            return None
    except ValidationError:
        release_undispatched(usage, "El control del piloto impidió el despacho; no se llamó al proveedor.")
        _clear_claim(job, status=Job.Status.FAILED, error="El piloto no permite esta solicitud. Revisa el presupuesto y el alcance autorizado del evento.")
        return None
    return event, job, usage.snapshot, conversation


@transaction.atomic
def _publish(job_id, token, output, usage):
    event, job = _lock_event_job(job_id)
    financial = _financial(job)
    if financial is not None:
        settle_usage_locked(financial, token, usage)
    if not _has_claim(job, token, usage):
        return job
    try:
        _active_owner(event, job.actor)
    except PermissionDenied:
        _clear_claim(job, status=Job.Status.FAILED, error="El solicitante ya no tiene permiso para este evento.", result={"usage": usage} if usage else {})
        return job
    if not _snapshot_current(event, job):
        _clear_claim(job, status=Job.Status.STALE, error=STALE_MESSAGE, result={"usage": usage} if usage else {})
        return job
    if job.kind == Job.Kind.PLAN:
        from apps.planning.services import create_candidate
        if not isinstance(output, dict):
            raise ValidationError("La respuesta de planificación no tiene el formato esperado.")
        from apps.assistant.models import CompactPlanRequest
        compact = CompactPlanRequest.objects.filter(job=job).first()
        if compact:
            from apps.assistant.compact_contract import validate_response
            from apps.assistant.compact_planning import expand_proposal
            validated = validate_response(output, round_number=compact.round_number)
            compact.response = validated
            compact.save(update_fields=["response"])
            output = expand_proposal(event, compact, validated)
            if output is None:
                append_stage(job, "completed")
                _clear_claim(job, status=Job.Status.SUCCEEDED, result={"compact_state": "questions", "usage": usage or {}})
                return job
            if compact.review_only:
                from apps.planning.event_rules import validate_event_plan
                if validate_event_plan(event, output):
                    raise ValidationError("La agenda privada requiere corregir sus restricciones.")
                append_stage(job, "completed")
                _clear_claim(job, status=Job.Status.SUCCEEDED, result={"compact_state": "private_ready", "usage": usage or {}})
                return job
        candidate = create_candidate(
            event=event, actor=job.actor, payload=output,
            base_revision=job.base_revision, base_plan_id=job.base_plan_id,
        )
        result = {"candidate_id": str(candidate.pk)}
        if compact:
            result["compact_state"] = "proposal"
            result["communications"] = compact.response["communications"]
        append_stage(job, "needs_changes" if candidate.validation else "review_ready")
    elif job.kind == Job.Kind.CHAT:
        from apps.assistant.models import Message
        if not isinstance(output, str) or not output.strip() or len(output) > 20000:
            raise ValidationError("La respuesta del agente no tiene el formato esperado.")
        message = Message.objects.create(event=event, role="assistant", content=output.strip(), job=job)
        result = {"message_id": str(message.pk)}
        append_stage(job, "completed")
    else:
        raise ValidationError("El tipo de trabajo no es válido.")
    if usage:
        result["usage"] = usage
    _clear_claim(job, status=Job.Status.SUCCEEDED, result=result)
    return job


@transaction.atomic
def _fail(job_id, token, usage=None, *, code=None):
    _event, job = _lock_event_job(job_id)
    financial = _financial(job)
    if financial is not None:
        settle_usage_locked(financial, token, usage)
        if code == "free_quota" and financial.snapshot.get("provider") == "opencode":
            # Serial completion owns the Account lock. Quota telemetry never
            # changes this Job's model or releases its unknown reservation.
            from apps.ai_management.free_pool import record_quota_failure
            record_quota_failure(account_id=financial.account_id, snapshot=financial.snapshot)
    if _has_claim(job, token, usage):
        message = ("El proveedor gratuito alcanzó un límite de cuota o solicitudes (429). "
                   "El plan se conserva. No hubo reintento ni cambio automático de proveedor. "
                   "Si no llegaron contadores, el consumo queda por conciliar.") if code == "free_quota" else FAILED_MESSAGE
        result = {"usage": usage} if usage else {}
        if code == "compact_invalid":
            message = "La respuesta no cumple el contrato compacto. La agenda no se guardó. No hubo reintento automático."
            result["diagnostic"] = {"phase": "contract", "code": "compact_invalid"}
        _clear_claim(job, status=Job.Status.FAILED, error=message, result=result)
    return job


def _pop_usage(provider):
    pop = getattr(provider, "pop_usage", None)
    if not callable(pop):
        return {}
    try:
        observed = pop()
    except Exception:
        return {}
    if not isinstance(observed, dict):
        return {}
    return {key: value for key, value in observed.items()
            if key in {"input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"}
            and type(value) is int and value >= 0}


def process_claim(claim):
    from apps.assistant.execution import agent_execution
    with agent_execution():
        return _process_claim(claim)


def _process_claim(claim):
    """Run one claimed attempt; a returned/cancelled claim cannot publish twice."""
    prepared = prepare_claim(claim)
    if prepared is None:
        return Job.objects.get(pk=claim.pk)
    result = perform_inference(prepared, observer=lambda stage: observe_stage(prepared.job_id, prepared.token, stage))
    return finish_inference(prepared, result)


@dataclass(frozen=True)
class PreparedInference:
    """One claimed call. Only detached, frozen adapters may use another thread."""
    job_id: object
    token: object
    event_id: object
    kind: str
    prompt: str
    snapshot: dict
    event: object
    conversation: object
    creator_thread: int
    parallel_safe: bool = False


@dataclass(frozen=True)
class InferenceResult:
    """Untrusted output and reported counters, without exception bodies/secrets."""
    job_id: object
    token: object
    output: object = None
    usage: dict = field(default_factory=dict)
    failed: bool = False
    code: str | None = None


def prepare_claim(claim, *, for_parallel=False):
    """DB phase, called only by the local coordinator in bounded parallel mode."""
    from apps.assistant.execution import agent_execution
    with agent_execution():
        prepared = _prepare(claim.pk, claim.claim_token)
    if prepared is None:
        return None
    event, job, snapshot, conversation = prepared
    parallel_safe = for_parallel and snapshot["provider"] in {"openai", "opencode"}
    if parallel_safe:
        # A detached namespace has no ORM relations, save(), deferred fields or
        # connection. Frozen payloads are the entire remote thread's context.
        attrs = {"pk": event.pk, "id": event.pk, "revision": event.revision,
                 "active_plan_id": event.active_plan_id, "is_synthetic": event.is_synthetic}
        for name in ("_openai_context_snapshot", "_free_context_snapshot", "_compact_context_snapshot"):
            if hasattr(event, name):
                attrs[name] = deepcopy(getattr(event, name))
        event = SimpleNamespace(**attrs)
        # The model-scoped frozen snapshot already owns its eligible history.
        # Do not carry the unused generic chat projection into another thread.
        conversation = None
    return PreparedInference(job_id=job.pk, token=job.claim_token, event_id=event.pk,
        kind=job.kind, prompt=job.prompt, snapshot=deepcopy(snapshot), event=event,
        conversation=deepcopy(conversation), creator_thread=threading.get_ident(), parallel_safe=parallel_safe)


def perform_inference(prepared, *, observer):
    """Remote phase, with no ORM for a detached OpenAI/OpenCode call.

    In parallel mode the observer is a synchronous relay: the coordinator checks
    the fenced claim and writes observations before acknowledging the thread.
    Other adapters retain their original serial behavior on the preparing thread.
    """
    provider = None
    usage = {}
    try:
        if not prepared.parallel_safe and threading.get_ident() != prepared.creator_thread:
            raise ValueError("An unfrozen adapter cannot run on another thread")
        from apps.assistant import provider
        from apps.assistant.execution import agent_execution
        with agent_execution(prepared.snapshot.get("agent_code", "romeo-1")), provider.use_profile(prepared.snapshot), provider.observe_requests(observer):
            # Recheck cancellation/lease through the coordinator before starting
            # an admitted call. Repeated context_ready is deliberately idempotent.
            observer("context_ready")
            if hasattr(prepared.event, "_compact_context_snapshot"):
                output = provider.generate_compact(event=prepared.event)
            elif prepared.kind == Job.Kind.PLAN:
                output = provider.generate_plan(event=prepared.event, prompt=prepared.prompt)
            elif prepared.kind == Job.Kind.CHAT:
                output = provider.answer_question(
                    event=prepared.event, prompt=prepared.prompt, conversation=prepared.conversation,
                )
            else:
                raise ValidationError("El tipo de trabajo no es válido.")
        usage = _pop_usage(provider)
        return InferenceResult(prepared.job_id, prepared.token, output=output, usage=usage)
    except Exception as error:
        # Never store remote bodies, input, credentials or raw exception strings.
        logger.warning("El trabajo de IA %s terminó con un error controlado.", prepared.job_id)
        if not usage:
            try:
                usage = _pop_usage(provider)
            except Exception:
                usage = {}
        code = ("free_quota" if isinstance(error, getattr(provider, "FreeQuotaUnavailable", ())) else
                "compact_invalid" if isinstance(error, getattr(provider, "CompactContractError", ())) else None)
        return InferenceResult(prepared.job_id, prepared.token, usage=usage, failed=True, code=code)


def finish_inference(prepared, result):
    """DB phase; account even a cancelled/expired call, without another send."""
    if result.job_id != prepared.job_id or result.token != prepared.token:
        raise ValidationError("El resultado no pertenece a este intento.")
    from apps.assistant.execution import agent_execution
    with agent_execution(prepared.snapshot.get("agent_code", "romeo-1")):
        if result.failed:
            return _fail(prepared.job_id, prepared.token, result.usage, code=result.code)
        try:
            observe_stage(prepared.job_id, prepared.token, "validating")
            return _publish(prepared.job_id, prepared.token, result.output, result.usage)
        except Exception:
            logger.warning("El resultado de IA %s no pudo publicarse.", prepared.job_id)
            return _fail(prepared.job_id, prepared.token, result.usage)


def run_one(*, job_id=None):
    claim = claim_next(job_id=job_id)
    return None if claim is None else process_claim(claim)
