"""Versioned human-admin grants and routing before dispatch.

One grant per account: its lifetime summary includes the account's older ledger
too. Recreating or renaming the assignment cannot reset already committed money.
The OpenAI pilot's separate cross-account USD 1 cap is never increased here.
No secrets, provider requests, retry loops or model-generated permissions.
"""
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.assistant.execution import require_human_superadmin
from tools.opencode.catalog import policy_fingerprint
from .catalog import CATALOG, OPENCODE_DEMO_MODELS
from .models import AIAccount, AIProfile, AgentGrant


ROUTES = frozenset({"primary", "fallback_budget", "free_pool", "free_pool_budget"})
BUDGET_REASONS = frozenset({"agent_budget", "monthly_budget", "openai_pilot_budget"})


def _invalid(message="La asignación del agente cambió o no está autorizada.", *, code="agent_grant_invalid"):
    raise ValidationError(message, code=code)


def _profile(account, value):
    identity = getattr(value, "pk", value)
    profile = AIProfile.objects.filter(pk=identity, owner_id=account.owner_id).first()
    if profile is None:
        _invalid("El perfil debe pertenecer a la misma cuenta del agente.")
    return profile


def _fresh_superadmin(identity):
    return bool(identity and get_user_model().objects.filter(
        pk=identity, is_active=True, is_superuser=True).exists())


def _fallback_snapshot(profile):
    from .services import profile_snapshot
    snapshot = profile_snapshot(profile)
    if (snapshot["provider"] != "opencode" or snapshot["mode"] != "free"
            or not snapshot["free_tier_confirmed"] or snapshot["model"] not in OPENCODE_DEMO_MODELS
            or any(Decimal(snapshot[key]) != 0 for key in ("input_rate", "cached_rate", "output_rate"))):
        _invalid("La alternativa sólo admite un modelo OpenCode revisado y gratuito confirmado.", code="agent_fallback_invalid")
    return snapshot


def _primary_snapshot(profile):
    from .services import profile_snapshot
    snapshot = profile_snapshot(profile)
    if snapshot["mode"] == "paid":
        # Jorge authorized only the existing OpenAI pilot credits. Other paid
        # APIs need a separate spending authorization and reviewed tariff guard.
        if snapshot["provider"] != "openai":
            _invalid("Este piloto sólo autoriza OpenAI como API de pago principal.", code="agent_primary_invalid")
    elif not any((entry["provider"], entry["model"], entry["mode"]) ==
                 (snapshot["provider"], snapshot["model"], snapshot["mode"])
                 for entry in CATALOG.values()):
        _invalid("El modelo gratuito o local principal debe figurar en el catálogo revisado.", code="agent_primary_invalid")
    return snapshot


def _require_enabled(grant):
    if not grant.enabled:
        _invalid("El agente está deshabilitado.", code="agent_disabled")
    if not _fresh_superadmin(grant.configured_by_id):
        _invalid("Un superadministrador vigente debe revisar la asignación del agente.")


def _fallback_approval(grant, snapshot):
    if (not grant.fallback_policy_approved_at or not _fresh_superadmin(grant.fallback_policy_approved_by_id)
            or grant.fallback_policy_fingerprint != policy_fingerprint(snapshot["model"])):
        _invalid("Revisa y acepta nuevamente la privacidad de la alternativa gratuita.", code="agent_fallback_policy")


@transaction.atomic
def update_agent_grant(*, actor, account, expected_version, name, enabled, budget_usd,
                       primary_profile, fallback_profile=None, accept_fallback_policy=False,
                       free_pool_enabled=None, free_pool_for_plans=None,
                       expected_fallback_policy_fingerprint=None):
    """Only a fresh human superadmin may create/change this single assignment."""
    current_actor = require_human_superadmin(actor)
    current_actor = get_user_model().objects.select_for_update().get(pk=current_actor.pk)
    if not current_actor.is_active or not current_actor.is_superuser:
        raise PermissionDenied("El superadministrador ya no tiene permiso para cambiar la asignación.")
    account = AIAccount.objects.select_for_update().get(pk=account.pk)
    grant = AgentGrant.objects.select_for_update().filter(account=account).first()
    if type(expected_version) is not int or expected_version != (grant.version if grant else 0):
        _invalid("La asignación cambió. Recarga antes de guardar.", code="agent_grant_stale")
    if type(enabled) is not bool or type(accept_fallback_policy) is not bool:
        _invalid("Las confirmaciones del agente no son válidas.")
    if any(value is not None and type(value) is not bool for value in (free_pool_enabled, free_pool_for_plans)):
        _invalid("Las opciones del grupo gratuito no son válidas.")
    if type(name) is not str or not 1 <= len(name.strip()) <= 80:
        _invalid("Indica un nombre del agente de hasta 80 caracteres.")
    try:
        budget = Decimal(str(budget_usd))
    except (InvalidOperation, ValueError, TypeError):
        budget = Decimal("NaN")
    if not budget.is_finite() or not 0 <= budget <= 1 or budget.as_tuple().exponent < -6:
        _invalid("El presupuesto total del agente debe estar entre USD 0 y USD 1, con hasta seis decimales.", code="agent_budget_invalid")
    primary = _profile(account, primary_profile)
    fallback = _profile(account, fallback_profile) if fallback_profile is not None else None
    if enabled:
        _primary_snapshot(primary)
    approval_hash = ""
    approval_by = approval_at = None
    if fallback is not None:
        if fallback.pk == primary.pk:
            _invalid("La alternativa debe ser un perfil distinto del principal.", code="agent_fallback_invalid")
        if not enabled and grant and grant.fallback_profile_id == fallback.pk:
            # Revocation must remain possible even after removal, profile
            # disablement or a policy change. Re-enabling validates it afresh.
            approval_hash = grant.fallback_policy_fingerprint
            approval_by, approval_at = grant.fallback_policy_approved_by, grant.fallback_policy_approved_at
        else:
            reviewed = _fallback_snapshot(fallback)
            fingerprint = policy_fingerprint(reviewed["model"])
            if accept_fallback_policy:
                if (type(expected_fallback_policy_fingerprint) is not str
                        or expected_fallback_policy_fingerprint != fingerprint):
                    _invalid("Las condiciones de la alternativa cambiaron. Recarga y revísalas antes de aceptar.", code="agent_fallback_policy")
                approval_hash, approval_by, approval_at = fingerprint, current_actor, timezone.now()
            elif (grant and grant.fallback_profile_id == fallback.pk
                    and grant.fallback_policy_fingerprint == fingerprint
                    and _fresh_superadmin(grant.fallback_policy_approved_by_id)):
                approval_hash = grant.fallback_policy_fingerprint
                approval_by, approval_at = grant.fallback_policy_approved_by, grant.fallback_policy_approved_at
            else:
                _invalid("Acepta expresamente la política del modelo gratuito seleccionado.", code="agent_fallback_policy")
    if grant is None:
        grant = AgentGrant(account=account, code="romeo-1")
    else:
        grant.version += 1
    grant.name, grant.enabled, grant.budget_usd = name.strip(), enabled, budget
    grant.primary_profile, grant.fallback_profile = primary, fallback
    grant.fallback_policy_fingerprint = approval_hash
    grant.fallback_policy_approved_by, grant.fallback_policy_approved_at = approval_by, approval_at
    grant.configured_by = current_actor
    if free_pool_enabled is not None:
        grant.free_pool_enabled = free_pool_enabled
    if free_pool_for_plans is not None:
        grant.free_pool_for_plans = free_pool_for_plans
    grant.full_clean()
    grant.save()
    return grant


def agent_grant_summary(grant):
    """Conservative lifetime account ledger; unknown usage retains its hold."""
    from .models import AIUsage
    spent = reserved = Decimal("0")
    count = uncertain = breaches = 0
    rows = AIUsage.objects.filter(account_id=grant.account_id).only(
        "status", "dispatch_token", "reserved_usd", "estimated_cost_usd",
        "input_tokens", "output_tokens", "reserved_input_tokens", "reserved_output_tokens")
    for item in rows:
        count += 1
        cost = item.estimated_cost_usd
        if (item.status == AIUsage.Status.SETTLED and cost is not None
                and cost.is_finite() and cost >= 0):
            spent += cost
            breaches += int(cost > item.reserved_usd
                or (item.input_tokens or 0) > item.reserved_input_tokens
                or (item.output_tokens or 0) > item.reserved_output_tokens)
        elif item.status == AIUsage.Status.RELEASED and item.dispatch_token is None:
            continue
        else:
            reserved += item.reserved_usd
            uncertain += int(item.status != AIUsage.Status.RESERVED)
            breaches += int((item.input_tokens or 0) > item.reserved_input_tokens
                            or (item.output_tokens or 0) > item.reserved_output_tokens)
    committed = spent + reserved
    return {"limit_usd": grant.budget_usd, "spent_usd": spent, "reserved_usd": reserved,
        "committed_usd": committed, "available_usd": max(Decimal("0"), grant.budget_usd - committed),
        "usage_count": count, "uncertain_count": uncertain, "limit_breach_count": breaches,
        "over_limit": committed > grant.budget_usd}


def _bound_snapshot(grant, snapshot, route, reason=""):
    return {**snapshot, "agent_grant_id": grant.pk, "agent_grant_version": grant.version,
        "agent_code": grant.code, "agent_name": grant.name, "agent_route": route,
        "agent_budget_reason": reason}


def validate_agent_snapshot(account, snapshot):
    """Revalidate even a queued legacy job once this account receives a grant."""
    grant = AgentGrant.objects.filter(account_id=account.pk).first()
    if grant is None:
        if snapshot.get("agent_grant_id") is not None:
            _invalid()
        return None
    _require_enabled(grant)
    if (type(snapshot.get("agent_grant_id")) is not int or snapshot["agent_grant_id"] != grant.pk
            or type(snapshot.get("agent_grant_version")) is not int or snapshot["agent_grant_version"] != grant.version
            or snapshot.get("agent_code") != grant.code
            or snapshot.get("credential_owner_id") != account.owner_id or snapshot.get("agent_route") not in ROUTES):
        _invalid()
    if snapshot["agent_route"] == "primary":
        if snapshot.get("profile_id") != grant.primary_profile_id or snapshot.get("agent_budget_reason") != "":
            _invalid()
        current = _primary_snapshot(_profile(account, grant.primary_profile_id))
        if ((current["provider"], current["model"], current["profile_version"]) !=
                (snapshot.get("provider"), snapshot.get("model"), snapshot.get("profile_version"))):
            _invalid()
    elif snapshot["agent_route"].startswith("free_pool"):
        from .free_pool import validate_pool_snapshot
        if snapshot.get("agent_budget_reason") not in (BUDGET_REASONS if snapshot["agent_route"] == "free_pool_budget" else {""}):
            _invalid()
        validate_pool_snapshot(account=account, grant=grant, snapshot=snapshot)
    else:
        if (snapshot.get("profile_id") != grant.fallback_profile_id
                or snapshot.get("agent_budget_reason") not in BUDGET_REASONS):
            _invalid()
        current = _fallback_snapshot(_profile(account, grant.fallback_profile_id))
        if current["model"] != snapshot.get("model") or current["profile_version"] != snapshot.get("profile_version"):
            _invalid()
        _fallback_approval(grant, current)
    return grant


def is_budget_fallback(account, snapshot):
    grant = validate_agent_snapshot(account, snapshot)
    return grant is not None and snapshot["agent_route"] in {"fallback_budget", "free_pool", "free_pool_budget"}


def _maximum_cost(snapshot):
    from .services import estimate_cost
    rates = {**snapshot, "input_rate": str(max(Decimal(snapshot["input_rate"]), Decimal(snapshot["cached_rate"])))}
    return estimate_cost(rates, input_tokens=snapshot["max_input_tokens"], output_tokens=snapshot["max_output_tokens"])


def _primary_budget_reason(account, grant, snapshot, *, lock_pilot=True):
    from .services import account_summary
    from .pilot import _lock_pilot, openai_pilot_summary
    summary = agent_grant_summary(grant)
    monthly = account_summary(account)
    if summary["limit_breach_count"] or monthly["limit_breach_count"]:
        _invalid("Un consumo excedió su reserva; revisa el registro antes de continuar.", code="usage_limit_breach")
    if monthly["over_token_limit"] or snapshot["max_input_tokens"] + snapshot["max_output_tokens"] > monthly["available_tokens"]:
        _invalid("No quedan tokens suficientes para reservar esta solicitud.", code="monthly_tokens")
    reserve = _maximum_cost(snapshot)
    global_summary = None
    if snapshot["provider"] == "openai":
        # Enqueue holds Account before this shared lock. Keep the lock until its
        # transaction commits, including when selecting the free alternative.
        if lock_pilot:
            _lock_pilot()
        global_summary = openai_pilot_summary()
        if global_summary["limit_breach_count"]:
            _invalid("Un consumo OpenAI excedió su reserva; revisa el piloto.", code="openai_pilot_usage_breach")
    if reserve:
        if summary["committed_usd"] + reserve > grant.budget_usd:
            return "agent_budget"
        if monthly["spent_usd"] + monthly["reserved_usd"] + reserve > account.monthly_budget_usd:
            return "monthly_budget"
        if global_summary and global_summary["committed_usd"] + reserve > global_summary["limit_usd"]:
            return "openai_pilot_budget"
    return ""


def agent_preview_snapshot(account, kind="plan"):
    """Read-only eligibility hint; no locks, reservation or provider check.

    Budget can change after this preview. Enqueue chooses again under locks;
    displaying this hint neither grants consent nor guarantees a dispatch.
    """
    from .services import configured_snapshot
    grant = AgentGrant.objects.filter(account_id=account.pk).first()
    if grant is None:
        return configured_snapshot(account)
    _require_enabled(grant)
    if grant.free_pool_enabled and (kind == "chat" or grant.free_pool_for_plans):
        from .free_pool import choose_pool_snapshot
        return _bound_snapshot(grant, choose_pool_snapshot(account=account, grant=grant, kind=kind, preview=True), "free_pool")
    snapshot = _bound_snapshot(grant, _primary_snapshot(_profile(account, grant.primary_profile_id)), "primary")
    from .free_pool import ensure_gateway_available
    ensure_gateway_available(account, snapshot)
    if snapshot["mode"] == "paid" and not account.paid_enabled:
        _invalid("El uso de APIs de pago requiere autorización explícita.", code="paid_disabled")
    reason = _primary_budget_reason(account, grant, snapshot, lock_pilot=False)
    if reason:
        if grant.free_pool_enabled:
            from .free_pool import choose_pool_snapshot
            return _bound_snapshot(grant, choose_pool_snapshot(account=account, grant=grant, kind=kind, preview=True), "free_pool_budget", reason)
        if grant.fallback_profile_id is None:
            _invalid("El presupuesto no cubre la solicitud y no hay alternativa gratuita autorizada.", code=reason)
        snapshot = _fallback_snapshot(_profile(account, grant.fallback_profile_id))
        _fallback_approval(grant, snapshot)
        ensure_gateway_available(account, snapshot)
        return _bound_snapshot(grant, snapshot, "fallback_budget", reason)
    return snapshot


def chosen_snapshot(*, account, event, actor, kind, key, token=None):
    """Choose exactly one model before any provider call and bind its consent.

    Caller holds Event -> User -> Account in an atomic enqueue transaction.
    The approved pool handles chat (and optionally plans) from the beginning.
    An exhausted pool never escalates to paid. Remote errors do not retry here.
    """
    from .services import authorize_snapshot, configured_snapshot
    from .model_policy import bind_request_consent, request_policy_context
    from apps.assistant import provider
    grant = AgentGrant.objects.select_for_update().filter(account_id=account.pk).first()
    if grant is None:
        snapshot = configured_snapshot(account)
    else:
        _require_enabled(grant)
        if not event.is_synthetic:
            _invalid("Este agente y sus alternativas sólo permiten eventos ficticios controlados.", code="synthetic_required")
        if actor.pk != account.owner_id or event.owner_id != account.owner_id:
            raise PermissionDenied("La asignación no pertenece al organizador del evento.")
        use_pool = grant.free_pool_enabled and (kind == "chat" or grant.free_pool_for_plans)
        reason = ""
        if use_pool:
            from .free_pool import choose_pool_snapshot
            snapshot = _bound_snapshot(grant, choose_pool_snapshot(account=account, grant=grant, kind=kind), "free_pool")
        else:
            primary = _profile(account, grant.primary_profile_id)
            snapshot = _bound_snapshot(grant, _primary_snapshot(primary), "primary")
            if snapshot["mode"] == "paid" and not account.paid_enabled:
                _invalid("El uso de APIs de pago requiere autorización explícita.", code="paid_disabled")
            reason = _primary_budget_reason(account, grant, snapshot)
        if reason and grant.free_pool_enabled:
            from .free_pool import choose_pool_snapshot
            snapshot = _bound_snapshot(grant, choose_pool_snapshot(account=account, grant=grant, kind=kind), "free_pool_budget", reason)
        elif reason:
            if grant.fallback_profile_id is None:
                _invalid("El presupuesto no cubre la solicitud y no hay alternativa gratuita autorizada.", code=reason)
            snapshot = _fallback_snapshot(_profile(account, grant.fallback_profile_id))
            _fallback_approval(grant, snapshot)
            snapshot = _bound_snapshot(grant, snapshot, "fallback_budget", reason)
        if snapshot["agent_route"] in {"fallback_budget", "free_pool", "free_pool_budget"}:
            # The admin approved this exact model/policy. Bind a normal receipt
            # to the actual chosen model, not a stale preview of another model.
            context = request_policy_context(snapshot, event=event, actor=actor, kind=kind, request_key=key)
            token = context["token"] if context else None
        authorize_snapshot(account, snapshot)
        if not provider.profile_ready(snapshot):
            _invalid("El proveedor asignado no está configurado; no se seleccionó otro modelo.", code="ai_not_configured")
    if snapshot["provider"] == "opencode" and not event.is_synthetic:
        _invalid("La demostración gratuita sólo admite eventos ficticios.", code="synthetic_required")
    return bind_request_consent(snapshot, token=token, event=event, actor=actor, kind=kind, request_key=key)


def ensure_agent_reservation_locked(*, account, snapshot, reserve_usd, usage=None, job=None):
    """Check grant again at reserve/dispatch; no mid-flight fallback or retry."""
    from .free_pool import ensure_gateway_available
    ensure_gateway_available(account, snapshot)
    grant = validate_agent_snapshot(account, snapshot)
    if grant is None:
        return
    summary = agent_grant_summary(grant)
    if summary["limit_breach_count"]:
        _invalid("Un consumo excedió la reserva máxima del agente.", code="usage_limit_breach")
    additional = Decimal("0") if usage is not None else reserve_usd
    if reserve_usd and summary["committed_usd"] + additional > grant.budget_usd:
        _invalid("El presupuesto total del agente no cubre esta solicitud.", code="agent_budget")
    if snapshot["agent_route"] in {"fallback_budget", "free_pool", "free_pool_budget"} and reserve_usd:
        _invalid("Una alternativa de presupuesto no puede reservar dinero.", code="agent_fallback_invalid")
    if snapshot["agent_route"].startswith("free_pool"):
        from .free_pool import ensure_pool_capacity
        ensure_pool_capacity(account=account, grant=grant, snapshot=snapshot, usage=usage)
    from apps.events.models import Event
    current_job = usage.job if usage is not None else job
    if snapshot["agent_route"].startswith("free_pool") and (current_job is None or current_job.kind != snapshot.get("agent_task_role")):
        _invalid("El modelo no tiene autorización para la función de este trabajo.", code="free_pool_invalid")
    if current_job is None or not Event.objects.filter(pk=current_job.event_id, is_synthetic=True,
                                                     owner_id=account.owner_id).exists():
        _invalid("El agente sólo admite eventos ficticios controlados de su cuenta.", code="synthetic_required")


# Public short alias requested by the admin panel contract.
summary = agent_grant_summary
