"""Read-only owner reports and hypothetical, simultaneous tariff comparisons.

Historical money comes exclusively from the ledger. Comparison prices describe
a separate scenario: they cannot rewrite costs, reserve funds or make API calls.
"""

from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import BigIntegerField, Count, DecimalField, F, Q, Sum
from django.db.models.functions import Cast
from django.utils import timezone

from apps.jobs.models import Job
from .catalog import CATALOG, catalog_entry
from .models import AIUsage
from .services import MAX_PG_TOKEN_COUNT, OUTSTANDING, USD_UNIT, estimate_cost

MAX_SCENARIO_JOBS = 1000
MAX_MANUAL_REQUESTS = 100000
MAX_SCENARIO_INPUT = 128000
MAX_SCENARIO_OUTPUT = 16000
MAX_SCENARIO_TOTAL = 131072
_MAX_BUCKET = 2_000_000_000


def _report_month(value):
    """Ledger periods use Lima, independently from Django's active UI timezone."""
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            raise ValidationError("El mes requiere una fecha con zona horaria.", code="invalid_month")
        local = timezone.localtime(value, ZoneInfo("America/Lima"))
        return date(local.year, local.month, 1)
    if type(value) is date:
        if value.day != 1:
            raise ValidationError("Selecciona el primer día del mes.", code="invalid_month")
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
        try:
            return date(int(value[:4]), int(value[5:]), 1)
        except ValueError:
            pass
    raise ValidationError("Selecciona un mes válido con formato AAAA-MM.", code="invalid_month")


def owner_usage(owner, *, event_id=None, kind="", month=None):
    """No account creation, row locks, external requests or permissive fallbacks."""
    if kind not in ("", *Job.Kind.values):
        raise ValidationError("La operación no es válida.", code="invalid_kind")
    period = _report_month(month) if month is not None else None
    event_key = None
    if event_id not in (None, ""):
        try:
            event_key = UUID(str(event_id))
        except (ValueError, AttributeError, TypeError):
            raise ValidationError("El evento no es válido.", code="invalid_event") from None
    if not getattr(owner, "pk", None) or not getattr(owner, "is_authenticated", False):
        return AIUsage.objects.none()
    rows = AIUsage.objects.filter(account__owner_id=owner.pk, job__actor_id=owner.pk,
                                  job__event__owner_id=owner.pk)
    if event_key is not None:
        rows = rows.filter(job__event_id=event_key)
    if kind:
        rows = rows.filter(job__kind=kind)
    if period is not None:
        rows = rows.filter(month=period)
    return rows


def _total_expression():
    # Cast before addition: malformed legacy buckets can each fit int32 while
    # their sum does not. Even a read-only PostgreSQL report must remain safe.
    return Cast("input_tokens", BigIntegerField()) + Cast("output_tokens", BigIntegerField())


def _coherent_tokens():
    return (
        Q(input_tokens__isnull=False, output_tokens__isnull=False,
          input_tokens__gte=0, output_tokens__gte=0,
          input_tokens__lte=_MAX_BUCKET, output_tokens__lte=_MAX_BUCKET)
        & Q(input_tokens__lte=MAX_PG_TOKEN_COUNT - F("output_tokens"))
        & (Q(total_tokens__isnull=True) | Q(total_tokens=_total_expression()))
        & (Q(cached_tokens__isnull=True) | Q(cached_tokens__gte=0, cached_tokens__lte=F("input_tokens")))
        & (Q(reasoning_tokens__isnull=True) | Q(reasoning_tokens__gte=0, reasoning_tokens__lte=F("output_tokens")))
    )


def _aggregations():
    settled = Q(status=AIUsage.Status.SETTLED)
    active = ~Q(status=AIUsage.Status.RELEASED)
    known_usage = settled & _coherent_tokens()
    known_cost = settled & Q(estimated_cost_usd__isnull=False)
    money = DecimalField(max_digits=24, decimal_places=6)
    return {
        "total_count": Count("id"),
        "settled_count": Count("id", filter=settled),
        "reserved_count": Count("id", filter=Q(status=AIUsage.Status.RESERVED)),
        "dispatched_count": Count("id", filter=Q(status=AIUsage.Status.DISPATCHED)),
        "uncertain_count": Count("id", filter=Q(status=AIUsage.Status.UNCERTAIN)),
        "released_count": Count("id", filter=Q(status=AIUsage.Status.RELEASED)),
        "manual_count": Count("id", filter=settled & Q(accounting_source=AIUsage.AccountingSource.MANUAL)),
        "provider_count": Count("id", filter=settled & Q(accounting_source=AIUsage.AccountingSource.PROVIDER)),
        "unknown_source_count": Count("id", filter=settled & Q(accounting_source=AIUsage.AccountingSource.UNKNOWN)),
        "known_cost_count": Count("id", filter=known_cost),
        "unknown_cost_count": Count("id", filter=active & ~known_cost),
        "known_usage_count": Count("id", filter=known_usage),
        "unknown_usage_count": Count("id", filter=active & ~known_usage),
        "historical_cost_usd": Sum("estimated_cost_usd", filter=known_cost, default=Decimal("0"), output_field=money),
        "reserved_usd": Sum("reserved_usd", filter=Q(status__in=OUTSTANDING), default=Decimal("0"), output_field=money),
        "used_tokens": Sum(_total_expression(), filter=known_usage, default=0, output_field=BigIntegerField()),
    }


def _normalize_aggregate(summary):
    for key in ("historical_cost_usd", "reserved_usd"):
        summary[key] = summary[key].quantize(USD_UNIT)
    return summary


def aggregate_usage(queryset):
    """One SQL aggregate; zero money stays distinct from unknown-cost counts."""
    return _normalize_aggregate(queryset.aggregate(**_aggregations()))


def group_usage_by_event(queryset):
    rows = queryset.order_by().values("job__event_id", "job__event__title").annotate(**_aggregations())
    return [
        {"event_id": row.pop("job__event_id"), "event_title": row.pop("job__event__title"),
         **_normalize_aggregate(row)}
        for row in rows.order_by("job__event__title", "job__event_id")
    ]


def group_usage_by_operation(queryset):
    rows = queryset.order_by().values("job__kind").annotate(**_aggregations())
    labels = dict(Job.Kind.choices)
    result = []
    for row in rows.order_by("job__kind"):
        kind = row.pop("job__kind")
        result.append({"kind": kind, "label": labels.get(kind, kind), **_normalize_aggregate(row)})
    return result


def _coverage(count):
    return {"total_count": count, "included_count": 0, "excluded_count": 0,
            "not_settled_count": 0, "invalid_count": 0, "cache_unknown_count": 0,
            "manual_count": 0, "provider_count": 0, "unknown_source_count": 0,
            "released_count": 0, "derived_total_count": 0, "unknown_cost_count": 0,
            "declared_count": 0}


def _scenario(source, rows, coverage):
    requests = sum(row["requests"] for row in rows)
    sums = {name: sum(row[name] * row["requests"] for row in rows)
            for name in ("input_tokens", "output_tokens", "cached_tokens")}
    return {"source": source, "rows": rows, "requests": requests, **sums,
            "total_tokens": sums["input_tokens"] + sums["output_tokens"], "coverage": coverage}


def _valid_row(input_tokens, output_tokens, cached_tokens, requests):
    if any(type(number) is not int or not 0 <= number <= _MAX_BUCKET
           for number in (input_tokens, output_tokens, cached_tokens)) or cached_tokens > input_tokens:
        raise ValidationError("Los tokens deben ser enteros no negativos y la caché no puede superar la entrada.")
    if type(requests) is not int or not 1 <= requests <= MAX_MANUAL_REQUESTS:
        raise ValidationError("Selecciona entre 1 y 100000 solicitudes.")
    return {"input_tokens": input_tokens, "output_tokens": output_tokens,
            "cached_tokens": cached_tokens, "requests": requests}


def manual_scenario(*, input_tokens, output_tokens, cached_tokens=0, requests=1):
    row = _valid_row(input_tokens, output_tokens, cached_tokens, requests)
    if not _compatible(row):
        raise ValidationError("El escenario supera los límites por solicitud: 128000 de entrada, 16000 de salida y 131072 en total.", code="scenario_context_limit")
    coverage = _coverage(requests)
    coverage.update(included_count=requests, declared_count=requests)
    return _scenario("manual", [row], coverage)


def _compatible(row):
    return (row["input_tokens"] <= MAX_SCENARIO_INPUT
            and row["output_tokens"] <= MAX_SCENARIO_OUTPUT
            and row["input_tokens"] + row["output_tokens"] <= MAX_SCENARIO_TOTAL)


def _historical_tokens_valid(row):
    values = (row["input_tokens"], row["output_tokens"])
    if any(type(value) is not int or not 0 <= value <= _MAX_BUCKET for value in values):
        return False
    total = sum(values)
    if total > MAX_PG_TOKEN_COUNT or row["total_tokens"] not in (None, total):
        return False
    return all(value is None or (type(value) is int and 0 <= value <= limit)
               for value, limit in ((row["cached_tokens"], row["input_tokens"]),
                                    (row["reasoning_tokens"], row["output_tokens"])))


def historical_scenario(queryset):
    """Bounded one-query snapshot of known token buckets, never a new ledger.

    Unknown cache gets no discount; manual reconciliations remain explicitly
    counted as manual. NULL total can be derived from two complete buckets.
    """
    raw = list(queryset.values("status", "input_tokens", "output_tokens", "total_tokens",
                               "cached_tokens", "reasoning_tokens", "accounting_source",
                               "estimated_cost_usd")[:MAX_SCENARIO_JOBS + 1])
    if len(raw) > MAX_SCENARIO_JOBS:
        raise ValidationError("El histórico supera 1000 trabajos. Acota el mes, evento u operación para comparar.", code="scenario_too_large")
    coverage = _coverage(len(raw))
    rows = []
    for item in raw:
        if item["status"] != AIUsage.Status.SETTLED:
            coverage["not_settled_count"] += 1
            coverage["released_count"] += int(item["status"] == AIUsage.Status.RELEASED)
            continue
        if not _historical_tokens_valid(item):
            coverage["invalid_count"] += 1
            continue
        rows.append(_valid_row(item["input_tokens"], item["output_tokens"], item["cached_tokens"] or 0, 1))
        coverage["cache_unknown_count"] += int(item["cached_tokens"] is None)
        coverage["derived_total_count"] += int(item["total_tokens"] is None)
        coverage["unknown_cost_count"] += int(item["estimated_cost_usd"] is None)
        key = {AIUsage.AccountingSource.MANUAL: "manual_count",
               AIUsage.AccountingSource.PROVIDER: "provider_count"}.get(item["accounting_source"], "unknown_source_count")
        coverage[key] += 1
    coverage["included_count"] = len(rows)
    coverage["excluded_count"] = len(raw) - len(rows)
    return _scenario("history", rows, coverage)


def compare_scenario(scenario):
    """Keep catalogue order and tariff conditions; never pick a universal winner.

    Each distinct request is rounded first, then multiplied by its repetitions.
    Credits and FX are separate UI scenarios and never shared across providers.
    """
    rows = [_valid_row(**row) for row in scenario["rows"]]
    requests = sum(row["requests"] for row in rows)
    incompatible = sum(row["requests"] for row in rows if not _compatible(row))
    result = []
    for preset in CATALOG:
        entry = catalog_entry(preset)
        cache_disabled = entry["cache_policy"] == "disabled"
        available = bool(requests) and not incompatible
        applied_cache = 0 if cache_disabled or not available else sum(row["cached_tokens"] * row["requests"] for row in rows)
        gross = None if not available else sum((
            estimate_cost(entry, input_tokens=row["input_tokens"], output_tokens=row["output_tokens"],
                          cached_tokens=0 if cache_disabled else row["cached_tokens"]) * row["requests"]
            for row in rows), Decimal("0")).quantize(USD_UNIT)
        per_request = (gross / requests).quantize(USD_UNIT, rounding=ROUND_CEILING) if requests and gross is not None else None
        cache_note = ("Sin descuento de caché: este modelo usa modo explícito sin puntos de caché."
                      if cache_disabled else
                      "Caché automática del proveedor, sin aciertos garantizados. La caché está incluida en la entrada; las solicitudes sin desglose se simulan sin descuento."
                      if entry["provider"] == "openai" else
                      "La caché está incluida en la entrada; las solicitudes sin desglose se simulan sin descuento.")
        reason = ("El histórico supera los límites del prototipo por solicitud: 128000 de entrada, 16000 de salida y 131072 en total."
                  if incompatible else "No hay solicitudes con tokens completos para comparar." if not requests else "")
        result.append({**entry, "gross": gross, "per_request": per_request,
                       "available": available, "reason": reason,
                       "incompatible_count": incompatible, "available_count": requests - incompatible,
                       "cache_note": cache_note, "cached_tokens_applied": applied_cache,
                       "requests": requests, "coverage": dict(scenario["coverage"]), "condition": entry["description"]})
    return result
