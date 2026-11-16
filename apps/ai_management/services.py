"""Application spending controls, independent from AI-result publication.

Money is a USD estimate using the immutable tariff snapshot, not a provider
invoice. Unknown usage retains its reservation; it is never fabricated as zero.
Callers that mutate jobs lock Event, User, AIAccount, Job, then AIUsage.
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .catalog import OPENCODE_DEMO_MODELS, cache_policy_for
from .models import AIAccount, AIProfile, AIUsage

USD_UNIT = Decimal("0.000001")
MILLION = Decimal("1000000")
MAX_PG_TOKEN_COUNT = 2_147_483_647
OUTSTANDING = (AIUsage.Status.RESERVED, AIUsage.Status.DISPATCHED, AIUsage.Status.UNCERTAIN)


def current_month(at=None):
    local = timezone.localtime(at or timezone.now(), ZoneInfo("America/Lima"))
    return date(local.year, local.month, 1)


def get_account(owner):
    """Create only an inert, zero-dollar configuration; never enable a provider."""
    return AIAccount.objects.get_or_create(owner=owner)[0]


def profile_snapshot(profile):
    if not profile.enabled:
        raise ValidationError("El perfil de IA está desactivado.", code="ai_not_configured")
    if profile.provider not in AIProfile.Provider.values or profile.mode not in AIProfile.Mode.values:
        raise ValidationError("El proveedor o la modalidad no es válido.", code="ai_not_configured")
    if profile.max_input_tokens < 1 or profile.max_output_tokens < 1:
        raise ValidationError("El perfil requiere límites de tokens positivos.", code="ai_not_configured")
    rates = (profile.input_rate, profile.cached_rate, profile.output_rate)
    if any(not rate.is_finite() or rate < 0 for rate in rates):
        raise ValidationError("Las tarifas del perfil no son válidas.", code="ai_not_configured")
    if profile.mode != AIProfile.Mode.PAID and any(rates):
        raise ValidationError("Un perfil gratuito o local debe tener tarifas de API iguales a cero.", code="ai_not_configured")
    if profile.mode == AIProfile.Mode.FREE and (
        not profile.free_tier_confirmed or profile.provider not in (AIProfile.Provider.GROQ, AIProfile.Provider.GEMINI, AIProfile.Provider.OPENCODE)
    ):
        raise ValidationError("Confirma que esta clave utiliza la cuota gratuita del proveedor.", code="ai_not_configured")
    if (profile.mode == AIProfile.Mode.LOCAL) != (profile.provider == AIProfile.Provider.OLLAMA):
        raise ValidationError("La modalidad local sólo admite Ollama.", code="ai_not_configured")
    if profile.provider == AIProfile.Provider.OPENCODE and (
        profile.mode != AIProfile.Mode.FREE or profile.model not in OPENCODE_DEMO_MODELS or profile.max_output_tokens > 2048
    ):
        raise ValidationError("La demostración admite únicamente los modelos gratuitos revisados con hasta 2048 tokens de salida.", code="ai_not_configured")
    if not profile.model.strip():
        raise ValidationError("El perfil requiere un modelo.", code="ai_not_configured")
    from .runtime_credentials import credential_status
    credential = credential_status(profile.owner_id, profile.provider)
    snapshot = {
        "profile_id": profile.pk, "profile_version": profile.version, "credential_owner_id": profile.owner_id,
        "credential_version": credential["version"], "credential_ref": credential.get("reference"),
        "name": profile.name, "provider": profile.provider, "model": profile.model,
        "mode": profile.mode, "free_tier_confirmed": profile.free_tier_confirmed,
        "max_input_tokens": profile.max_input_tokens, "max_output_tokens": profile.max_output_tokens,
        "input_rate": str(profile.input_rate), "cached_rate": str(profile.cached_rate),
        "output_rate": str(profile.output_rate), "source_url": profile.source_url,
        "verified_on": profile.verified_on.isoformat() if profile.verified_on else None,
        "cache_policy": cache_policy_for(profile.provider, profile.model),
    }
    from .pilot import validate_openai_pilot_tariffs
    validate_openai_pilot_tariffs(snapshot)
    return snapshot


def configured_snapshot(account):
    profile = account.active_profile
    if profile is None or profile.owner_id != account.owner_id:
        raise ValidationError("Selecciona un perfil de IA de tu cuenta.", code="ai_not_configured")
    snapshot = profile_snapshot(profile)
    authorize_snapshot(account, snapshot)
    from apps.assistant import provider
    if not provider.profile_ready(snapshot):
        raise ValidationError("La IA aún no está configurada. Configura el proveedor en el entorno del servidor.", code="ai_not_configured")
    return snapshot


def authorize_snapshot(account, snapshot):
    """Current consent can revoke queued work; configuration cannot rewrite tariffs."""
    from .free_pool import ensure_gateway_available
    ensure_gateway_available(account, snapshot)
    from .agent_access import validate_agent_snapshot
    validate_agent_snapshot(account, snapshot)
    profile_id = snapshot.get("profile_id")
    if not AIProfile.objects.filter(pk=profile_id, owner_id=account.owner_id, enabled=True,
                                    version=snapshot.get("profile_version")).exists():
        raise ValidationError("El perfil de este trabajo ya no está disponible.", code="ai_not_configured")
    if snapshot.get("mode") == AIProfile.Mode.PAID and (
        not account.paid_enabled or account.monthly_budget_usd <= 0
    ):
        raise ValidationError("El uso de APIs de pago requiere autorización y presupuesto explícitos.", code="paid_disabled")


def _money(value):
    return value.quantize(USD_UNIT, rounding=ROUND_CEILING)


def estimate_cost(snapshot, *, input_tokens, output_tokens, cached_tokens=0):
    """USD estimate with cached input included in, not added to, input tokens."""
    if any(type(number) is not int or not 0 <= number <= 2_000_000_000
           for number in (input_tokens, output_tokens, cached_tokens)) or cached_tokens > input_tokens:
        raise ValidationError("Los tokens deben ser enteros no negativos y la caché no puede superar la entrada.")
    try:
        rates = [Decimal(str(snapshot[name])) for name in ("input_rate", "cached_rate", "output_rate")]
    except (KeyError, TypeError, InvalidOperation, ValueError):
        raise ValidationError("Las tarifas no son válidas.") from None
    if any(not rate.is_finite() or rate < 0 for rate in rates):
        raise ValidationError("Las tarifas no son válidas.")
    return _money((Decimal(input_tokens - cached_tokens) * rates[0]
                   + Decimal(cached_tokens) * rates[1]
                   + Decimal(output_tokens) * rates[2]) / MILLION)


def account_summary(account, month=None):
    month = month or current_month()
    spent, reserved = Decimal("0"), Decimal("0")
    used_tokens = reserved_tokens = count = uncertain = breaches = 0
    for item in account.usage.filter(month=month).only(
        "status", "estimated_cost_usd", "reserved_usd", "total_tokens",
        "reserved_input_tokens", "reserved_output_tokens",
        "input_tokens", "output_tokens",
    ):
        count += 1
        if item.status == AIUsage.Status.SETTLED:
            spent += item.estimated_cost_usd or Decimal("0")
            used_tokens += item.total_tokens or 0
            breaches += int((item.input_tokens or 0) > item.reserved_input_tokens
                            or (item.output_tokens or 0) > item.reserved_output_tokens
                            or (item.estimated_cost_usd or 0) > item.reserved_usd)
        elif item.status in OUTSTANDING:
            reserved += item.reserved_usd
            reserved_tokens += item.reserved_input_tokens + item.reserved_output_tokens
            uncertain += int(item.status == AIUsage.Status.UNCERTAIN)
    return {
        "month": month, "budget_usd": account.monthly_budget_usd,
        "token_limit": account.monthly_token_limit, "spent_usd": spent,
        "reserved_usd": reserved, "available_usd": max(Decimal("0"), account.monthly_budget_usd - spent - reserved),
        "used_tokens": used_tokens, "reserved_tokens": reserved_tokens,
        "available_tokens": max(0, account.monthly_token_limit - used_tokens - reserved_tokens),
        "usage_count": count, "uncertain_count": uncertain,
        "limit_breach_count": breaches,
        "over_budget": spent + reserved > account.monthly_budget_usd,
        "over_token_limit": used_tokens + reserved_tokens > account.monthly_token_limit,
    }


def ensure_account_within_limits(account, month=None, *, snapshot=None):
    summary = account_summary(account, month)
    if summary["limit_breach_count"]:
        raise ValidationError("Un consumo superó su reserva máxima; revisa la configuración antes de continuar.", code="usage_limit_breach")
    from .agent_access import is_budget_fallback
    budget_fallback = snapshot is not None and is_budget_fallback(account, snapshot)
    if summary["over_budget"] and not budget_fallback:
        raise ValidationError("El presupuesto actual es inferior al consumo y las reservas existentes.", code="monthly_budget")
    if summary["over_token_limit"]:
        raise ValidationError("El límite actual de tokens es inferior al consumo y las reservas existentes.", code="monthly_tokens")
    return summary


def reserve_job_locked(*, job, account, snapshot):
    """The caller holds the account lock inside the enqueue transaction."""
    prior = AIUsage.objects.filter(job=job).first()
    if prior is not None:
        return prior
    month = current_month()
    summary = ensure_account_within_limits(account, month, snapshot=snapshot)
    input_max, output_max = snapshot["max_input_tokens"], snapshot["max_output_tokens"]
    if input_max + output_max > summary["available_tokens"]:
        raise ValidationError("No quedan tokens suficientes para reservar esta solicitud.", code="monthly_tokens")
    # Use the largest possible input rate, including the cached bucket.
    maximum_rates = {**snapshot, "input_rate": str(max(Decimal(snapshot["input_rate"]), Decimal(snapshot["cached_rate"])))}
    reserve = estimate_cost(maximum_rates, input_tokens=input_max, output_tokens=output_max)
    if reserve > summary["available_usd"] or (reserve and summary["over_budget"]):
        raise ValidationError("El presupuesto mensual no cubre la reserva máxima de esta solicitud.", code="monthly_budget")
    from .agent_access import ensure_agent_reservation_locked
    ensure_agent_reservation_locked(account=account, snapshot=snapshot, reserve_usd=reserve, job=job)
    from .pilot import reserve_openai_pilot_locked
    reserve_openai_pilot_locked(job=job, snapshot=snapshot, reserve_usd=reserve)
    return AIUsage.objects.create(
        job=job, account=account, month=month, snapshot=snapshot,
        reserved_input_tokens=input_max, reserved_output_tokens=output_max, reserved_usd=reserve,
    )


def release_undispatched(usage, reason="No se envió una solicitud al proveedor."):
    if usage.status == AIUsage.Status.RESERVED and usage.dispatch_token is None:
        usage.status = AIUsage.Status.RELEASED
        usage.reason = reason[:200]
        usage.settled_at = timezone.now()
        usage.save(update_fields=["status", "reason", "settled_at", "updated_at"])
    return usage


def mark_dispatched(usage, token):
    if usage.status != AIUsage.Status.RESERVED or usage.dispatch_token is not None:
        return False
    from .agent_access import ensure_agent_reservation_locked
    ensure_agent_reservation_locked(account=AIAccount.objects.get(pk=usage.account_id),
        snapshot=usage.snapshot, reserve_usd=usage.reserved_usd, usage=usage)
    from .pilot import ensure_openai_pilot_dispatch_locked
    ensure_openai_pilot_dispatch_locked(usage)
    usage.dispatch_token = token
    usage.dispatched_at = timezone.now()
    usage.status = AIUsage.Status.DISPATCHED
    usage.save(update_fields=["dispatch_token", "dispatched_at", "status", "updated_at"])
    return True


def mark_uncertain(usage, reason="El proveedor no informó un consumo completo; conserva la reserva."):
    if usage.status in (AIUsage.Status.DISPATCHED, AIUsage.Status.UNCERTAIN):
        usage.status = AIUsage.Status.UNCERTAIN
        usage.reason = reason[:200]
        usage.save(update_fields=["status", "reason", "updated_at"])
    return usage


def settle_usage_locked(usage, dispatch_token, observed=None, *, source=AIUsage.AccountingSource.PROVIDER):
    """Accept actual usage independently from a cancelled/stale job's publication.

    Financial fencing survives Job.claim_token revocation. A duplicate completion
    never releases an uncertainty hold or changes already settled amounts.
    """
    if dispatch_token is None or usage.dispatch_token != dispatch_token:
        return usage
    replacing_manual = (usage.status == AIUsage.Status.SETTLED
                        and usage.accounting_source == AIUsage.AccountingSource.MANUAL
                        and source == AIUsage.AccountingSource.PROVIDER)
    if usage.status == AIUsage.Status.SETTLED and not replacing_manual:
        return usage
    if usage.status not in (AIUsage.Status.DISPATCHED, AIUsage.Status.UNCERTAIN) and not replacing_manual:
        return usage
    allowed = {"input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"}
    invalid_reported_total = (isinstance(observed, dict) and "total_tokens" in observed
                              and (type(observed["total_tokens"]) is not int
                                   or not 0 <= observed["total_tokens"] <= MAX_PG_TOKEN_COUNT))
    clean = {key: value for key, value in (observed if isinstance(observed, dict) else {}).items()
             if key in allowed and type(value) is int
             and 0 <= value <= (MAX_PG_TOKEN_COUNT if key == "total_tokens" else 2_000_000_000)}
    for key in ("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens"):
        if key in clean:
            setattr(usage, key, clean[key])
    if "cached_input_tokens" in clean:
        usage.cached_tokens = clean["cached_input_tokens"]
    complete = "input_tokens" in clean and "output_tokens" in clean
    if complete:
        total = clean["input_tokens"] + clean["output_tokens"]
        complete = (not invalid_reported_total and total <= MAX_PG_TOKEN_COUNT
                    and clean.get("total_tokens", total) == total
                    and clean.get("cached_input_tokens", 0) <= clean["input_tokens"]
                    and clean.get("reasoning_tokens", 0) <= clean["output_tokens"])
    if not complete:
        if replacing_manual:
            # A partial late report cannot erase a documented reconciliation.
            usage.refresh_from_db()
            return usage
        usage.status = AIUsage.Status.UNCERTAIN
        usage.reason = "Consumo incompleto o inconsistente; la reserva permanece por conciliar."
        usage.save(update_fields=["input_tokens", "output_tokens", "total_tokens", "cached_tokens",
                                  "reasoning_tokens", "status", "reason", "updated_at"])
        return usage
    # A missing cached breakdown is conservatively priced as uncached input.
    cached = clean.get("cached_input_tokens", 0)
    rates = usage.snapshot
    if "cached_input_tokens" not in clean:
        rates = {**rates, "input_rate": str(max(Decimal(rates["input_rate"]), Decimal(rates["cached_rate"])))}
    usage.cached_tokens = clean.get("cached_input_tokens")
    usage.reasoning_tokens = clean.get("reasoning_tokens")
    cost = estimate_cost(rates, input_tokens=clean["input_tokens"], output_tokens=clean["output_tokens"], cached_tokens=cached)
    usage.total_tokens = total
    usage.estimated_cost_usd = cost
    usage.accounting_source = source
    usage.status = AIUsage.Status.SETTLED
    usage.settled_at = timezone.now()
    usage.reason = ("El consumo excedió la reserva; revisa los límites antes de nuevas solicitudes."
                    if total > usage.reserved_input_tokens + usage.reserved_output_tokens or cost > usage.reserved_usd
                    else "Coste estimado a partir de tokens informados por el proveedor.")
    usage.save(update_fields=["input_tokens", "output_tokens", "total_tokens", "cached_tokens", "reasoning_tokens",
                              "estimated_cost_usd", "accounting_source", "status", "settled_at", "reason", "updated_at"])
    return usage


@transaction.atomic
def reconcile_usage(*, usage_id, actor, input_tokens, output_tokens, cached_tokens=0, reasoning_tokens=0, note):
    """A human superadmin records verified usage; real late reports take priority."""
    from apps.assistant.execution import require_human_superadmin
    actor = require_human_superadmin(actor)
    from apps.events.models import Event
    from apps.jobs.models import Job
    identity = AIUsage.objects.values("job_id", "job__event_id", "account_id", "account__owner_id").get(pk=usage_id)
    if identity["account__owner_id"] != actor.pk:
        raise PermissionDenied("Este consumo pertenece a otra cuenta.")
    Event.objects.select_for_update().get(pk=identity["job__event_id"])
    current_actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not current_actor.is_active or not current_actor.is_superuser:
        raise PermissionDenied("La cuenta ya no tiene permiso para conciliar consumo.")
    AIAccount.objects.select_for_update().get(pk=identity["account_id"])
    job = Job.objects.select_for_update().get(pk=identity["job_id"])
    usage = AIUsage.objects.select_for_update().get(pk=usage_id)
    numbers = (input_tokens, output_tokens, cached_tokens, reasoning_tokens)
    if any(type(number) is not int or not 0 <= number <= 2_000_000_000 for number in numbers):
        raise ValidationError("Los tokens deben ser enteros no negativos.")
    if input_tokens + output_tokens > MAX_PG_TOKEN_COUNT:
        raise ValidationError("El total de entrada y salida supera el límite admitido por solicitud.", code="usage_total_too_large")
    if cached_tokens > input_tokens or reasoning_tokens > output_tokens:
        raise ValidationError("Los desgloses no pueden superar los tokens de entrada o salida.")
    if not isinstance(note, str) or not note.strip() or len(note.strip()) > 1000:
        raise ValidationError("Documenta la comprobación externa en una nota de hasta 1000 caracteres.")
    command = {"input_tokens": input_tokens, "output_tokens": output_tokens,
               "cached_tokens": cached_tokens, "reasoning_tokens": reasoning_tokens, "note": note.strip()}
    if usage.reconciliation_snapshot:
        previous = {key: usage.reconciliation_snapshot.get(key) for key in command}
        if previous == command:
            return usage
        raise ValidationError("Este consumo ya tiene una conciliación; recarga para revisar su estado.", code="stale_reconciliation")
    if job.status in (Job.Status.QUEUED, Job.Status.RUNNING):
        raise ValidationError("Espera a que termine el trabajo antes de conciliarlo.")
    if usage.status != AIUsage.Status.UNCERTAIN or usage.accounting_source == AIUsage.AccountingSource.PROVIDER:
        raise ValidationError("Sólo puede conciliarse consumo desconocido; el consumo del proveedor no se sobrescribe.")
    settle_usage_locked(usage, usage.dispatch_token, {
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cached_input_tokens": cached_tokens, "reasoning_tokens": reasoning_tokens,
    }, source=AIUsage.AccountingSource.MANUAL)
    if usage.status != AIUsage.Status.SETTLED:
        raise ValidationError("No hay un despacho verificable para conciliar este consumo.")
    usage.reconciled_by = actor
    usage.reconciled_at = timezone.now()
    usage.reconciliation_note = note.strip()
    usage.reconciliation_snapshot = {**command, "estimated_cost_usd": str(usage.estimated_cost_usd)}
    usage.reason = "Conciliación manual de una comprobación externa; no es una lectura de API."
    usage.save(update_fields=["reconciled_by", "reconciled_at", "reconciliation_note", "reconciliation_snapshot", "reason", "updated_at"])
    return usage
