"""Human-approved free routing, local capacity and conservative gateway backoff.

Limits here count logical jobs, not the provider's HTTP quota. Unknown usage
keeps its token hold across midnight. No network probe, hidden paid escalation,
or repeated inference is performed by this module.
"""
from datetime import datetime, time, timedelta, timezone as utc_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.assistant.execution import require_human_superadmin
from tools.opencode.catalog import CatalogVerificationError, policy_fingerprint
from .catalog import CATALOG, catalog_entry
from .agent_identity import AGENT_DISPLAY_NAME
from .models import AIAccount, AIProfile, AIUsage, AgentGrant, AgentPoolEntry, FreeGatewayState

BACKOFF = timedelta(minutes=10)
ROLES = frozenset({"chat", "plan", "both"})


def _invalid(message, code="free_pool_unavailable"):
    raise ValidationError(message, code=code)


def _policy_valid(entry):
    try:
        fingerprint = policy_fingerprint(entry.profile.model)
    except CatalogVerificationError:
        return False
    return bool(entry.approved_at and entry.policy_fingerprint == fingerprint
        and get_user_model().objects.filter(pk=entry.approved_by_id, is_active=True, is_superuser=True).exists())


def _snapshot(entry, account):
    from .agent_access import _fallback_snapshot
    if entry.profile.owner_id != account.owner_id:
        raise PermissionDenied("El modelo del grupo pertenece a otra cuenta.")
    if not entry.enabled or not _policy_valid(entry):
        _invalid("El modelo gratuito necesita autorización vigente.", "free_pool_policy")
    return _fallback_snapshot(entry.profile)


def _capacity(entry, account, *, exclude_usage_id=None, now=None):
    now = now or timezone.now()
    start = datetime.combine(now.astimezone(utc_timezone.utc).date(), time.min, tzinfo=utc_timezone.utc)
    requests = tokens = 0
    # Group by actual model, not mutable profile/grant identity. Re-adding a
    # profile must not erase previously consumed capacity or uncertain holds.
    rows = AIUsage.objects.filter(account_id=account.pk, snapshot__provider="opencode",
        snapshot__model=entry.profile.model).exclude(pk=exclude_usage_id)
    for item in rows.only("status", "dispatch_token", "dispatched_at", "created_at", "total_tokens",
                          "reserved_input_tokens", "reserved_output_tokens"):
        if item.status == AIUsage.Status.RELEASED and item.dispatch_token is None:
            continue
        today = (item.dispatched_at or item.created_at) >= start
        requests += int(today)
        if item.status == AIUsage.Status.SETTLED and item.total_tokens is not None:
            tokens += item.total_tokens if today else 0
        else:
            tokens += item.reserved_input_tokens + item.reserved_output_tokens
    return requests, tokens


def gateway_state(account):
    state = FreeGatewayState.objects.filter(account_id=account.pk).first()
    until = state.cooldown_until if state else None
    return until, bool(until and until > timezone.now())


def ensure_gateway_available(account, snapshot):
    if snapshot.get("provider") == "opencode" and gateway_state(account)[1]:
        _invalid("La pasarela gratuita está en pausa tras un 429. La pausa local no garantiza el restablecimiento de su cuota.", "free_gateway_cooldown")


def pool_summary(grant):
    if grant is None:
        return {"entries": [], "cooldown_until": None, "gateway_paused": False, "enabled": False}
    until, paused = gateway_state(grant.account)
    rows = []
    for entry in AgentPoolEntry.objects.filter(grant=grant).select_related("profile", "approved_by").order_by("priority", "id"):
        requests, tokens = _capacity(entry, grant.account)
        valid = False
        state = "Deshabilitado"
        if entry.enabled:
            try:
                snapshot = _snapshot(entry, grant.account)
                valid = True
                reserve = snapshot["max_input_tokens"] + snapshot["max_output_tokens"]
                if paused:
                    state = "Pasarela en pausa"
                elif requests >= entry.daily_request_limit or tokens + reserve > entry.daily_token_limit:
                    state = "Sin capacidad interna"
                else:
                    from apps.assistant import provider
                    state = "Disponible localmente · cuota remota sin comprobar" if provider.profile_ready(snapshot) else "Adaptador no disponible"
            except (ValidationError, PermissionDenied, KeyError):
                state = "Revisar perfil o política"
        eligible = valid and not paused and state.startswith("Disponible")
        rows.append({"entry": entry, "profile": entry.profile, "requests_used": requests,
            "tokens_committed": tokens, "available_requests": max(0, entry.daily_request_limit - requests),
            "available_tokens": max(0, entry.daily_token_limit - tokens), "eligible": eligible,
            "state": state, "policy_valid": valid})
    return {"entries": rows, "cooldown_until": until, "gateway_paused": paused, "enabled": grant.free_pool_enabled}


@transaction.atomic
def configure_entry(*, actor, account, expected_grant_version, preset, enabled, roles, priority,
                    daily_request_limit, daily_token_limit, accept_policy, expected_policy_fingerprint=None):
    actor = require_human_superadmin(actor)
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    require_human_superadmin(actor)
    account = AIAccount.objects.select_for_update().get(pk=account.pk)
    # A human superadmin may administer this scoped account; no model execution
    # can reach this service even when its actor happens to be a superuser.
    grant = AgentGrant.objects.select_for_update().filter(account=account).first()
    if grant is None or type(expected_grant_version) is not int or expected_grant_version != grant.version:
        _invalid("La asignación cambió. Recarga antes de guardar.", "agent_grant_stale")
    if (preset not in CATALOG or CATALOG[preset]["provider"] != "opencode"
            or type(enabled) is not bool or type(accept_policy) is not bool or roles not in ROLES
            or type(priority) is not int or not 1 <= priority <= 100
            or type(daily_request_limit) is not int or not 1 <= daily_request_limit <= 100
            or type(daily_token_limit) is not int or not 2049 <= daily_token_limit <= 1000000):
        _invalid("Revisa el modelo, función y límites internos.", "free_pool_invalid")
    spec = catalog_entry(preset)
    if accept_policy and (type(expected_policy_fingerprint) is not str
            or expected_policy_fingerprint != policy_fingerprint(spec["model"])):
        _invalid("Las condiciones del modelo cambiaron. Recarga y revísalas antes de aceptar.", "free_pool_policy")
    profile = AIProfile.objects.filter(owner_id=account.owner_id, provider="opencode", model=spec["model"], mode="free").order_by("pk").first()
    if profile is None:
        profile = AIProfile.objects.create(owner_id=account.owner_id, name=AGENT_DISPLAY_NAME + " · grupo · " + preset,
            **{key: spec[key] for key in ("provider", "model", "mode", "input_rate", "cached_rate", "output_rate", "source_url", "verified_on")},
            enabled=True, free_tier_confirmed=True, max_input_tokens=24000, max_output_tokens=2048)
    entry = AgentPoolEntry.objects.select_for_update().filter(grant=grant, profile=profile).first()
    if entry is None:
        entry = AgentPoolEntry(grant=grant, profile=profile)
    else:
        entry.version += 1
    if accept_policy:
        entry.policy_fingerprint = policy_fingerprint(profile.model)
        entry.approved_by, entry.approved_at = actor, timezone.now()
    entry.enabled, entry.roles, entry.priority = enabled, roles, priority
    entry.daily_request_limit, entry.daily_token_limit = daily_request_limit, daily_token_limit
    if enabled:
        _snapshot(entry, account)
    entry.full_clean()
    entry.save()
    grant.version += 1
    grant.save(update_fields=["version", "updated_at"])
    return entry


def choose_pool_snapshot(*, account, grant, kind, preview=False):
    """Choose before dispatch, highest priority first, then least used model.

    Enqueue holds Account: its eventual reservation commits atomically with the
    choice. All candidates are approved; unavailable/disabled/quota-full entries
    are skipped without making a request. No calls are retried here.
    """
    if kind not in {"chat", "plan"}:
        _invalid("La función solicitada no está admitida.", "free_pool_invalid")
    _, paused = gateway_state(account)
    if paused:
        _invalid("La pasarela gratuita está en pausa tras un 429. No conocemos su hora de restablecimiento; vuelve a revisar después de la pausa local.", "free_gateway_cooldown")
    candidates = []
    from apps.assistant import provider
    for entry in AgentPoolEntry.objects.filter(grant=grant, enabled=True, roles__in=(kind, "both")).select_related("profile"):
        try:
            snapshot = _snapshot(entry, account)
            requests, tokens = _capacity(entry, account)
            if requests >= entry.daily_request_limit or tokens + snapshot["max_input_tokens"] + snapshot["max_output_tokens"] > entry.daily_token_limit:
                continue
            if not provider.profile_ready(snapshot):
                continue
        except (ValidationError, PermissionDenied):
            continue
        candidates.append((entry.priority, requests, entry.pk, entry, snapshot))
    if not candidates:
        _invalid("No hay un modelo gratuito autorizado con capacidad para esta función. Revisa el grupo; no se gastarán créditos de OpenAI automáticamente.")
    _, _, _, entry, snapshot = min(candidates, key=lambda row: row[:3])
    return {**snapshot, "agent_pool_entry_id": entry.pk, "agent_pool_entry_version": entry.version,
            "agent_task_role": kind}


def validate_pool_snapshot(*, account, grant, snapshot):
    if not grant.free_pool_enabled or type(snapshot.get("agent_pool_entry_id")) is not int:
        _invalid("El grupo gratuito fue deshabilitado.", "free_pool_invalid")
    entry = AgentPoolEntry.objects.filter(pk=snapshot["agent_pool_entry_id"], grant=grant).select_related("profile").first()
    if entry is None or entry.version != snapshot.get("agent_pool_entry_version"):
        _invalid("La autorización del modelo cambió.", "free_pool_invalid")
    kind = snapshot.get("agent_task_role")
    if kind not in {"chat", "plan"} or entry.roles not in {kind, "both"}:
        _invalid("El modelo no tiene autorización para esta función.", "free_pool_invalid")
    current = _snapshot(entry, account)
    if any(current.get(key) != snapshot.get(key) for key in ("profile_id", "profile_version", "provider", "model", "mode",
            "max_input_tokens", "max_output_tokens", "input_rate", "cached_rate", "output_rate")):
        _invalid("El perfil del modelo cambió.", "free_pool_invalid")
    return entry


def ensure_pool_capacity(*, account, grant, snapshot, usage=None):
    entry = validate_pool_snapshot(account=account, grant=grant, snapshot=snapshot)
    if gateway_state(account)[1]:
        _invalid("La pasarela gratuita está en pausa; no se envió esta solicitud.", "free_gateway_cooldown")
    requests, tokens = _capacity(entry, account, exclude_usage_id=usage.pk if usage else None)
    if requests + 1 > entry.daily_request_limit or tokens + snapshot["max_input_tokens"] + snapshot["max_output_tokens"] > entry.daily_token_limit:
        _invalid("El límite interno del modelo no cubre esta solicitud.")


@transaction.atomic
def record_quota_failure(*, account_id, snapshot):
    """HTTP 429 has unknown scope: pause this account's shared OpenCode gateway.

    Ten minutes is our backoff, NOT a provider reset promise. Existing usage is
    untouched and no next model is called. Already dispatched jobs still settle.
    """
    if snapshot.get("provider") != "opencode":
        return
    account = AIAccount.objects.select_for_update().get(pk=account_id)
    state, _ = FreeGatewayState.objects.select_for_update().get_or_create(account=account)
    until = timezone.now() + BACKOFF
    state.cooldown_until = max(state.cooldown_until, until) if state.cooldown_until else until
    state.last_error_code = "quota_scope_unknown"
    state.save(update_fields=["cooldown_until", "last_error_code"])
