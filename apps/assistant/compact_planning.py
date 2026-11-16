"""Human-started compact pilot inference with explicit, budgeted routing."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.ai_management.models import AIAccount, AgentGrant
from apps.ai_management.services import get_account, reserve_job_locked, authorize_snapshot
from apps.directory.models import Person
from apps.events.models import Event
from apps.events.services import require_event_owner
from apps.jobs.models import Job
from apps.jobs.trace import append_stage
from .compact_contract import BASE_CONTEXT, VERSION, validate_context, validate_response
from .demo_pilot import PILOT_EVENT_ID
from .local_commands import human_organizer
from .models import CompactPlanRequest, CompactRequestCancellation

ALLOWED_MODELS = frozenset({"glm-5.3-flash-free", "deepseek-v4.1-flash-free", "minimax-m3.1-flash-free"})
OPENAI_MODELS = frozenset({"gpt-5.4-mini"})
PROMPT = "compact-pilot-v1"
RETRY_MAX_AGE = timedelta(hours=2)


def _mapping(event):
    from .pilot_workflow import PILOT_TITLE, ANSWER_KEYS
    if event.pk != PILOT_EVENT_ID or event.title != PILOT_TITLE or not event.starts_at or event.timezone != "America/Lima":
        raise ValidationError("Este contrato compacto sólo admite el seminario de mantenimiento configurado.")
    answers = event.interview_answers
    if (set(answers) != set(ANSWER_KEYS) or any(type(row) is not dict or row.get("status") != "confirmed" or not row.get("value") for row in answers.values())
            or answers["duration_minutes"]["value"] != "90" or answers["modality"]["value"] != "Virtual"):
        raise ValidationError("Completa las siete respuestas y confirma modalidad virtual y duración de 90 minutos.")
    links = list(event.directory_people.select_related("person").filter(role="speaker", status__in=["planned", "confirmed"])[:2])
    if (len(links) != 1 or links[0].person.owner_id != event.owner_id or not links[0].person.is_active
            or links[0].person.category != Person.Category.SPEAKER):
        raise ValidationError("Selecciona un expositor activo de tu directorio.")
    return {"p1": {"id": str(links[0].person_id), "version": links[0].person.version}, "r1": "Sala virtual Zoom"}


def authorized_compact_job(job, snapshot):
    """Narrow exception to synthetic-only jobs; never inferred from a prompt."""
    free = (snapshot.get("provider") == "opencode" and snapshot.get("mode") == "free"
        and snapshot.get("model") in ALLOWED_MODELS and snapshot.get("agent_route") == "free_pool")
    paid = (snapshot.get("provider") == "openai" and snapshot.get("mode") == "paid"
        and snapshot.get("model") in OPENAI_MODELS and snapshot.get("agent_route") == "primary")
    if (job is None or job.kind != Job.Kind.PLAN or job.event_id != PILOT_EVENT_ID
            or snapshot.get("compact_contract") != VERSION or not (free or paid)):
        return False
    record = CompactPlanRequest.objects.filter(job_id=job.pk, version=VERSION).first()
    if record is None or job.event.owner_id != job.actor_id:
        return False
    try:
        validate_context(record.context)
    except ValidationError:
        return False
    return record.round_number in (1, 2) and set(record.local_mapping) == {"p1", "r1"}


def _openai_snapshot(account, *, lock=False):
    from apps.ai_management.agent_access import _bound_snapshot, _require_enabled, _primary_snapshot
    grants = AgentGrant.objects.select_for_update() if lock else AgentGrant.objects
    grant = grants.filter(account=account).select_related("primary_profile").first()
    if grant is None:
        raise ValidationError("Configura una asignación humana vigente para OpenAI.")
    _require_enabled(grant)
    if not account.paid_enabled or account.monthly_budget_usd <= 0:
        raise ValidationError("OpenAI requiere autorización y presupuesto en Gestión de IA.", code="paid_disabled")
    profile = grant.primary_profile
    if profile is None or profile.owner_id != account.owner_id:
        raise PermissionDenied("El perfil principal no pertenece a esta cuenta.")
    snapshot = _primary_snapshot(profile)
    if snapshot["provider"] != "openai" or snapshot["mode"] != "paid" or snapshot["model"] not in OPENAI_MODELS:
        raise ValidationError("Selecciona GPT-5.4 mini como perfil principal OpenAI de este piloto.")
    from .compact_contract import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS
    return {**_bound_snapshot(grant, snapshot, "primary"), "compact_contract": VERSION,
        "max_input_tokens": min(snapshot["max_input_tokens"], MAX_INPUT_TOKENS),
        "max_output_tokens": min(snapshot["max_output_tokens"], MAX_OUTPUT_TOKENS)}


def _snapshot(account, event, actor, key, *, provider_name="free"):
    if provider_name == "openai":
        return _openai_snapshot(account, lock=True)
    from apps.ai_management.agent_access import _bound_snapshot, _require_enabled
    from apps.ai_management.free_pool import choose_pool_snapshot
    from apps.ai_management.model_policy import bind_request_consent, request_policy_context
    grant = AgentGrant.objects.select_for_update().filter(account=account).first()
    if grant is None or not grant.free_pool_enabled or not grant.free_pool_for_plans:
        raise ValidationError("Activa un grupo gratuito autorizado en Gestión de IA. Este recorrido no utiliza APIs de pago.")
    _require_enabled(grant)
    snapshot = _bound_snapshot(grant, choose_pool_snapshot(account=account, grant=grant, kind="plan", allowed_models=ALLOWED_MODELS), "free_pool")
    receipt = request_policy_context(snapshot, event=event, actor=actor, kind="plan", request_key=key)
    snapshot = bind_request_consent(snapshot, token=receipt["token"] if receipt else None,
        event=event, actor=actor, kind="plan", request_key=key)
    from .compact_contract import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS
    return {**snapshot, "compact_contract": VERSION,
        "max_input_tokens": min(snapshot["max_input_tokens"], MAX_INPUT_TOKENS),
        "max_output_tokens": min(snapshot["max_output_tokens"], MAX_OUTPUT_TOKENS)}


def _provider_choice(provider_name, parent=None):
    if parent is not None:
        from apps.ai_management.models import AIUsage
        snapshot = AIUsage.objects.filter(job=parent.job).values_list("snapshot", flat=True).first() or {}
        inherited = "openai" if snapshot.get("provider") == "openai" else "free" if snapshot.get("provider") == "opencode" else None
        if provider_name is not None and provider_name != inherited:
            raise ValidationError("Las respuestas deben continuar con el proveedor de sus preguntas.")
        provider_name = inherited
    provider_name = "free" if provider_name is None else provider_name
    if type(provider_name) is not str or provider_name not in {"free", "openai"}:
        raise ValidationError("Selecciona OpenAI o la ruta gratuita autorizada.")
    return provider_name


def compact_wire(context, snapshot=None):
    """Exact provider payload used by preview, worker freeze and local archive."""
    from .compact_contract import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, OPENAI_SCHEMA, OPENAI_PROPOSAL_SCHEMA, instructions_for
    context = validate_context(context)
    if snapshot is not None and snapshot.get("provider") == "openai":
        from . import provider
        schema = OPENAI_PROPOSAL_SCHEMA if context["answers"] or context.get("change") else OPENAI_SCHEMA
        with provider.use_profile(snapshot):
            payload = provider._payload(instructions_for(context, openai=True), {"action": "plan", "data_mode": "closed_public_topic", "context": context}, schema=schema)
            body = provider._body(payload)
        system, user = payload["input"][0]["content"], payload["input"][1]["content"]
        return {"system_prompt": system, "user_prompt": user, "response_schema": deepcopy(schema), "payload": payload,
            "prompt_text": "SISTEMA\n" + system + "\n\nENTRADA\n" + user + "\n\nFORMATO DE SALIDA\n" + json.dumps(schema, ensure_ascii=False),
            "input_bound": len(body) + provider.INPUT_OVERHEAD_TOKENS}
    from .free_harness import _request
    user, system, bound = _request(context=context, instructions=instructions_for(context), action="plan",
        max_input_tokens=MAX_INPUT_TOKENS if snapshot is None else snapshot["max_input_tokens"],
        max_output_tokens=MAX_OUTPUT_TOKENS if snapshot is None else snapshot["max_output_tokens"], synthetic=False, schema=None, minimized=True)
    return {"system_prompt": system, "user_prompt": user,
        "prompt_text": "SISTEMA\n" + system + "\n\nENTRADA\n" + user, "input_bound": bound}


def retry_source(*, event, actor, failed_job_id=None):
    """Owner-only recent failed clarification; one child across every run."""
    if event.owner_id != actor.pk or event.pk != PILOT_EVENT_ID:
        return None
    query = CompactPlanRequest.objects.filter(job__actor=actor, job__event=event,
        round_number=2, job__status=Job.Status.FAILED, parent__round_number=1,
        parent__job__status=Job.Status.SUCCEEDED, job__base_revision=event.revision,
        job__base_plan_id=event.active_plan_id, parent__job__base_revision=event.revision,
        parent__job__base_plan_id=event.active_plan_id, parent__job__actor=actor,
        parent__job__event=event, created_at__gte=timezone.now() - RETRY_MAX_AGE,
        job__ai_usage__snapshot__provider="openai", job__ai_usage__snapshot__mode="paid",
        job__ai_usage__snapshot__model__in=OPENAI_MODELS,
        job__ai_usage__snapshot__agent_route="primary", job__ai_usage__snapshot__compact_contract=VERSION)
    if failed_job_id is not None:
        query = query.filter(job_id=failed_job_id)
    else:
        query = query.filter(continuation__isnull=True)
    source = query.select_related("job", "parent__job").order_by("-created_at").first()
    if source is None or source.parent.run_id != source.run_id or source.parent.response.get("state") != "questions":
        return None
    try:
        validate_response(source.parent.response, round_number=1)
        context = validate_context(source.context)
        if (source.local_mapping != _mapping(event)
                or set(context["answers"]) != {row["field"] for row in source.parent.response["questions"]}
                or any(context["answers"][row["field"]] not in row["options"] for row in source.parent.response["questions"])):
            return None
    except ValidationError:
        return None
    return source


def _confirmed_preferences(event, actor):
    """Reuse only human-selected catalog values, never another model's prose."""
    plan = event.active_plan
    seen = set()
    for _ in range(32):
        if plan is None or plan.pk in seen:
            return {}
        seen.add(plan.pk)
        record = CompactPlanRequest.objects.filter(job__actor=actor, job__event=event,
            job__status=Job.Status.SUCCEEDED, job__result__candidate_id=str(plan.candidate_id),
            response__state="proposal").first()
        if record is not None:
            context = validate_context(record.context)
            return deepcopy(context["answers"])
        plan = plan.candidate.base_plan
    return {}


def _compact_input(*, event, actor, run_id, expected_revision, parent_job_id=None, answers=None, failed_job_id=None, change_request=None):
    """One projection/answer validator for preview and actual enqueue."""
    mapping = _mapping(event)
    if type(expected_revision) is not int or expected_revision != event.revision:
        raise ValidationError("La ficha cambió. Revisa antes de preparar la agenda.", code="compact_stale")
    context, parent, round_number = deepcopy(BASE_CONTEXT), None, 1
    if change_request is not None:
        if parent_job_id is not None or answers is not None or failed_job_id is not None:
            raise ValidationError("El cambio acotado no admite respuestas ni reintentos de otra solicitud.")
        from .compact_changes import project_change, require_current_schedule
        context["change"] = project_change(event, change_request)
        person = Person.objects.get(pk=mapping["p1"]["id"], owner=actor, version=mapping["p1"]["version"], is_active=True)
        require_current_schedule(event, person.full_name, mapping["r1"])
        context["answers"] = _confirmed_preferences(event, actor)
        validate_context(context)
        return mapping, context, None, 1
    if failed_job_id is not None:
        if parent_job_id is not None or answers is not None:
            raise ValidationError("El reintento conserva las respuestas ya confirmadas.")
        failed = retry_source(event=event, actor=actor, failed_job_id=failed_job_id)
        if failed is None:
            raise ValidationError("Sólo puedes reintentar una aclaración fallida vigente, una vez.", code="compact_retry_unavailable")
        return mapping, validate_context(failed.context), failed, 2
    if parent_job_id is not None:
        parent = CompactPlanRequest.objects.filter(job_id=parent_job_id, job__actor=actor,
            job__event=event, run_id=run_id, round_number=1, job__status=Job.Status.SUCCEEDED).select_related("job").first()
        if (parent is None or parent.job.base_revision != event.revision or parent.job.base_plan_id != event.active_plan_id
                or parent.response.get("state") != "questions"):
            raise ValidationError("Estas preguntas ya no están disponibles.")
        rows = parent.response["questions"]
        if type(answers) is not dict or set(answers) != {row["id"] for row in rows}:
            raise ValidationError("Responde todas las preguntas antes de continuar.")
        for row in rows:
            answer = answers[row["id"]]
            if type(answer) is not str or answer not in row["options"]:
                raise ValidationError("Selecciona una de las opciones mostradas.")
            context["answers"][row["field"]] = answer
        round_number = 2
    validate_context(context)
    return mapping, context, parent, round_number


def compact_preview(*, actor, event_id, run_id, expected_revision, parent_job_id=None, answers=None, provider_name=None, failed_job_id=None, change_request=None):
    """Read-only exact prompt. No job, account creation, reservation or network."""
    actor = human_organizer(actor)
    event = Event.objects.get(pk=event_id)
    require_event_owner(event, actor)
    _mapping_local, context, parent, round_number = _compact_input(event=event, actor=actor, run_id=run_id,
        expected_revision=expected_revision, parent_job_id=parent_job_id, answers=answers, failed_job_id=failed_job_id, change_request=change_request)
    provider_name = _provider_choice(provider_name, parent)
    if failed_job_id is not None and provider_name != "openai":
        raise ValidationError("Este reintento explícito sólo admite la aclaración OpenAI autorizada.")
    snapshot = None
    if provider_name == "openai":
        account = AIAccount.objects.filter(owner=actor).first()
        if account is None:
            raise ValidationError("Configura OpenAI en Gestión de IA antes de continuar.")
        snapshot = _openai_snapshot(account)
        from . import provider
        if not provider.profile_ready(snapshot):
            raise ValidationError("Añade tu clave OpenAI en Gestión de IA. No se envió ni reservó una solicitud.", code="ai_not_configured")
    from .compact_contract import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS
    wire = compact_wire(context, snapshot)
    return {"run_id": str(run_id), "event_id": str(event.pk), "status": "preview", "version": VERSION,
        "round_number": round_number, "instructions": wire["system_prompt"], **{key: value for key, value in wire.items() if key != "payload"}, "context": context,
        "provider": "openai" if provider_name == "openai" else "opencode", "model": snapshot["model"] if snapshot else None,
        "max_input_tokens": MAX_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS}


@transaction.atomic
def enqueue_compact(*, actor, event_id, run_id, expected_revision, request_key, parent_job_id=None, answers=None, review_only=False, provider_name=None, failed_job_id=None, change_request=None):
    actor = human_organizer(actor)
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    human_organizer(actor)
    key = str(uuid.UUID(str(request_key)))
    run_id = uuid.UUID(str(run_id))
    if CompactRequestCancellation.objects.filter(event=event, actor=actor, run_id=run_id, request_key=key).exists():
        raise ValidationError("La solicitud fue detenida. No se envió al proveedor.", code="compact_cancelled")
    mapping, context, parent, round_number = _compact_input(event=event, actor=actor, run_id=run_id,
        expected_revision=expected_revision, parent_job_id=parent_job_id, answers=answers, failed_job_id=failed_job_id, change_request=change_request)
    if type(review_only) is not bool:
        raise ValidationError("La modalidad privada debe ser una confirmación válida.")
    if parent is not None:
        review_only = parent.review_only
    provider_name = _provider_choice(provider_name, parent)
    if failed_job_id is not None and provider_name != "openai":
        raise ValidationError("Este reintento explícito sólo admite la aclaración OpenAI autorizada.")
    canonical = json.dumps({"context": context, "parent": str(parent.pk) if parent else None, "revision": event.revision,
        "plan": str(event.active_plan_id), "review_only": review_only, "provider": provider_name}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    prior = Job.objects.filter(event=event, actor=actor, idempotency_key=key).first()
    if prior:
        if prior.request_hash != digest or not CompactPlanRequest.objects.filter(job=prior, run_id=run_id).exists():
            raise ValidationError("La solicitud ya se utilizó con otros datos.")
        return prior
    # One initial exchange and one batched answer per run/event revision. Reloads
    # and new request keys cannot multiply a pending/completed generation.
    previous = CompactPlanRequest.objects.filter(job__event=event, job__actor=actor, run_id=run_id,
        job__base_revision=event.revision, round_number=round_number,
        job__ai_usage__snapshot__provider="openai" if provider_name == "openai" else "opencode")
    if failed_job_id is not None:
        previous = previous.filter(parent=parent)
    previous = previous.first()
    if previous:
        if previous.parent_id == (parent.pk if parent else None) and previous.job.request_hash == digest:
            return previous.job
        raise ValidationError("Ya existe una solicitud para esta etapa. Revisa su resultado.")
    if parent and CompactPlanRequest.objects.filter(parent=parent).exists():
        raise ValidationError("Las respuestas ya fueron enviadas.")
    if Job.objects.filter(event=event, status__in=["queued", "running"]).exists():
        raise ValidationError("Espera a que termine la solicitud actual.")
    day_start = timezone.now() - timedelta(days=1)
    if Job.objects.filter(actor=actor, created_at__gte=day_start).count() >= max(0, int(getattr(settings, "AI_DAILY_JOB_LIMIT", 20))):
        raise ValidationError("Alcanzaste el límite diario de solicitudes.")
    account = get_account(actor)
    account = AIAccount.objects.select_for_update().get(pk=account.pk)
    snapshot = _snapshot(account, event, actor, key, provider_name=provider_name)
    authorize_snapshot(account, snapshot)
    if provider_name == "openai":
        from . import provider
        if not provider.profile_ready(snapshot):
            raise ValidationError("Añade tu clave OpenAI en Gestión de IA. No se envió ni reservó una solicitud.", code="ai_not_configured")
    job = Job.objects.create(event=event, actor=actor, kind=Job.Kind.PLAN, prompt=PROMPT,
        base_revision=event.revision, base_plan_id=event.active_plan_id, request_hash=digest, idempotency_key=key)
    CompactPlanRequest.objects.create(job=job, parent=parent, run_id=run_id, round_number=round_number,
        context=context, local_mapping=mapping, review_only=review_only)
    reserve_job_locked(job=job, account=account, snapshot=snapshot)
    append_stage(job, "queued")
    if provider_name == "free":
        append_stage(job, "free_pool_selected")
    return job


@transaction.atomic
def cancel_compact(*, actor, event_id, run_id, request_key=None, job_id=None):
    """Same Event->User lock order as enqueue; Stop can arrive first."""
    from apps.jobs.services import cancel
    actor = human_organizer(actor)
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    human_organizer(actor)
    query = {"job_id": job_id} if job_id is not None else {"job__idempotency_key": str(request_key)}
    record = CompactPlanRequest.objects.filter(**query, job__event=event, job__actor=actor, run_id=run_id).select_related("job__event").first()
    if request_key is not None:
        CompactRequestCancellation.objects.get_or_create(event=event, actor=actor, run_id=run_id, request_key=request_key)
    if record and record.job.status in ("queued", "running"):
        cancel(job_id=record.job_id, actor=actor)
        record.job.refresh_from_db()
    return record


def freeze_compact(event, job, snapshot):
    if not authorized_compact_job(job, snapshot):
        raise ValidationError("La solicitud compacta no está autorizada.")
    record = job.compact_request
    if record.local_mapping != _mapping(event):
        raise ValidationError("El expositor cambió. Revisa la ficha antes de continuar.")
    if record.context.get("change"):
        from .compact_changes import project_change
        if record.context["change"] != project_change(event, record.context["change"]["kind"]):
            raise ValidationError("La agenda base cambió antes de enviar la solicitud.", code="compact_stale")
    from .compact_contract import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS
    maximum_input = min(snapshot["max_input_tokens"], MAX_INPUT_TOKENS)
    maximum_output = min(snapshot["max_output_tokens"], MAX_OUTPUT_TOKENS)
    wire = compact_wire(record.context, snapshot)
    return {"context": deepcopy(record.context), "round_number": record.round_number, "model": snapshot["model"],
        "max_input_tokens": maximum_input, "max_output_tokens": maximum_output,
        "provider": snapshot["provider"], **({"payload": wire["payload"]} if "payload" in wire else {})}


def expand_proposal(event, record, output):
    output = validate_response(output, round_number=record.round_number)
    if record.context.get("change"):
        from .compact_changes import validate_change_response
        validate_change_response(event, record.context, output)
    if output["state"] != "proposal":
        return None
    if record.local_mapping != _mapping(event):
        raise ValidationError("La asignación del expositor cambió.")
    person = Person.objects.get(pk=record.local_mapping["p1"]["id"], owner_id=event.owner_id,
        version=record.local_mapping["p1"]["version"], is_active=True)
    current = event.starts_at.astimezone(ZoneInfo(event.timezone))
    sessions = []
    for index, row in enumerate(output["agenda"], 1):
        title = event.active_plan.payload["sessions"][index - 1]["title"] if record.context.get("change") else row["topic"].strip()
        session_id = event.active_plan.payload["sessions"][index - 1]["id"] if record.context.get("change") else f"s{index}"
        sessions.append({"id": session_id, "title": title, "start": current.isoformat(),
            "duration_minutes": row["min"], "speaker": person.full_name, "resource": record.local_mapping["r1"]})
        current += timedelta(minutes=row["min"])
    tasks = [{"id": f"t{index}", "title": row["task"].strip(), "depends_on": [f"t{dep}" for dep in row["after"]],
        "status": "pending", "purpose": "Preparación del evento."} for index, row in enumerate(output["preparation"], 1)]
    risks = []
    if record.context.get("change"):
        from .compact_changes import preserved_preparation
        tasks, risks = preserved_preparation(event)
    return {"title": event.title, "summary": "Agenda propuesta con IA. Horarios y asignaciones calculados y validados por ArquiGica. Comunicaciones en borrador; no se enviaron mensajes.",
        "sessions": sessions, "tasks": tasks, "risks": risks}
