"""Lifetime, server-owned USD 1 OpenAI pilot guard; no external account access.

All owners, models and months share this cap. Existing monthly account consent,
token quotas and event ownership remain separate requirements. Amounts are gross
local estimates from saved tariffs, never a reading of promotional credit or a
provider-enforced invoice ceiling. The migration-created mutex serializes new
reservations on PostgreSQL. SQLite is only single-worker local support.
"""
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

from django.core.exceptions import ValidationError

from .models import AIUsage, OpenAIPilotLock


OPENAI_PILOT_LIMIT_USD = Decimal("1.000000")
_ZERO = Decimal("0")
# Reviewed text models only, USD per million tokens at Standard rates. Profile
# fields are editable estimates, not authority to discount the pilot's reserve.
# Review these floors alongside adapter/catalog changes, never via UI or env.
OPENAI_PILOT_MINIMUM_RATES = MappingProxyType({
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("0.075"), Decimal("4.50")),
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.01"), Decimal("0.50")),
})


def validate_openai_pilot_tariffs(snapshot):
    """Reject unreviewed models and locally discounted or malformed tariffs.

    Checked again on the immutable queued snapshot before dispatch, even when
    the original profile was validated. Promotional eligibility does not change
    these gross floors; a more conservative, higher profile tariff is allowed.
    """
    if snapshot.get("provider") != "openai":
        return
    model = snapshot.get("model")
    minimum = OPENAI_PILOT_MINIMUM_RATES.get(model) if type(model) is str else None
    try:
        rates = tuple(Decimal(str(snapshot[key]))
                      for key in ("input_rate", "cached_rate", "output_rate"))
    except (KeyError, TypeError, InvalidOperation, ValueError):
        rates = ()
    if (snapshot.get("mode") != "paid" or minimum is None or not rates
            or any(not value.is_finite() or value < floor
                   for value, floor in zip(rates, minimum or ()))):
        raise ValidationError(
            "El piloto OpenAI admite los modelos de texto revisados con tarifas Standard iguales o superiores a las mínimas verificadas; no aplica descuentos ni ofertas a la reserva.",
            code="openai_pilot_tariffs")


def openai_pilot_summary():
    """Read only: count every OpenAI ledger row, regardless of owner/month/model.

    A dispatched or uncertain row retains its entire maximum reservation. A
    released row is excluded only when it was never dispatched. Inconsistent
    settled rows remain held rather than being invented as a zero-cost result.
    """
    spent, reserved = _ZERO, _ZERO
    count = uncertain = breaches = 0
    rows = AIUsage.objects.filter(snapshot__provider="openai").only(
        "status", "dispatch_token", "reserved_usd", "estimated_cost_usd",
        "reserved_input_tokens", "reserved_output_tokens", "input_tokens", "output_tokens",
    )
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
    return {
        "limit_usd": OPENAI_PILOT_LIMIT_USD, "spent_usd": spent, "reserved_usd": reserved,
        "committed_usd": committed, "available_usd": max(_ZERO, OPENAI_PILOT_LIMIT_USD - committed),
        "usage_count": count, "uncertain_count": uncertain, "limit_breach_count": breaches,
        "over_limit": committed > OPENAI_PILOT_LIMIT_USD,
    }


def _lock_pilot():
    # Do not recreate a missing mutex silently: migrations establish the single
    # shared scope. The caller already holds Event -> User -> Account locks.
    try:
        OpenAIPilotLock.objects.select_for_update().get(pk=1)
    except OpenAIPilotLock.DoesNotExist:
        raise ValidationError("Falta preparar el control global del piloto. Aplica sus migraciones antes de continuar.",
                              code="openai_pilot_not_ready") from None


def _require_synthetic(job, snapshot=None):
    from apps.events.models import Event
    if snapshot is not None:
        from apps.assistant.compact_planning import authorized_compact_job
        if authorized_compact_job(job, snapshot):
            return
    if not Event.objects.filter(pk=job.event_id, is_synthetic=True).exists():
        raise ValidationError("El piloto OpenAI sólo permite eventos de demostración con datos ficticios.",
                              code="openai_pilot_synthetic_required")


def _check_summary(summary, additional):
    if summary["limit_breach_count"]:
        raise ValidationError("Un consumo OpenAI excedió su reserva; revisa el piloto antes de continuar.",
                              code="openai_pilot_usage_breach")
    if summary["committed_usd"] + additional > OPENAI_PILOT_LIMIT_USD:
        raise ValidationError("El piloto global OpenAI de USD 1 no cubre esta solicitud. Incluye consumo y reservas pendientes de todos los meses y modelos.",
                              code="openai_pilot_budget")


def reserve_openai_pilot_locked(*, job, snapshot, reserve_usd):
    """Gate a new reservation inside its existing atomic enqueue transaction."""
    if snapshot.get("provider") != "openai":
        return
    validate_openai_pilot_tariffs(snapshot)
    _require_synthetic(job, snapshot)
    _lock_pilot()
    _check_summary(openai_pilot_summary(), reserve_usd)


def ensure_openai_pilot_dispatch_locked(usage):
    """Recheck a reserved call, counting its existing hold exactly once."""
    if usage.snapshot.get("provider") != "openai":
        return
    validate_openai_pilot_tariffs(usage.snapshot)
    # Old/imported rows must not dispatch against a zero or discounted hold.
    # A token ceiling change also requires its own adequate reservation.
    from .services import estimate_cost
    snapshot = usage.snapshot
    maximum_rates = {**snapshot, "input_rate": str(max(
        Decimal(snapshot["input_rate"]), Decimal(snapshot["cached_rate"])))}
    expected = estimate_cost(maximum_rates, input_tokens=snapshot["max_input_tokens"],
                             output_tokens=snapshot["max_output_tokens"])
    if (usage.reserved_usd < expected
            or usage.reserved_input_tokens != snapshot["max_input_tokens"]
            or usage.reserved_output_tokens != snapshot["max_output_tokens"]):
        raise ValidationError("La reserva guardada no cubre los límites y tarifas del piloto OpenAI.",
                              code="openai_pilot_under_reserved")
    _require_synthetic(usage.job, snapshot)
    _lock_pilot()
    _check_summary(openai_pilot_summary(), _ZERO)
