"""Pure, offline token summaries and hypothetical costs for OpenCode V2.

The pinned V2.2.7 CLI reports five disjoint token buckets. In particular,
``input`` excludes cache reads/writes and ``output`` is *visible* output;
reasoning must be added once to obtain billable output. These are not the
raw usage semantics of every provider API. Never feed another API's counters
to this estimator without converting them explicitly.

No imports, functions, or default tariff snapshots make requests, read files,
start a model, change a budget, or authorize payment. Money is returned as
unrounded decimal strings so a JSON consumer need not use binary floats.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
import re


TOKEN_SEMANTICS = "opencode-v2.2.7"
SEMANTICS_SOURCE = "https://raw.githubusercontent.com/anomalyco/opencode/v2.2.7/packages/core/src/session/usage.ts"
TARIFF_SOURCE = "https://opencode.ai/docs/console/models/"
TARIFF_VERIFIED_AT = "2026-11-14"
MAX_STEPS = 1000
MILLION = Decimal(1_000_000)
TOKEN_FIELDS = ("input_uncached", "cache_read", "cache_write", "output", "reasoning")
RATE_FIELDS = ("input", "cache_read", "cache_write", "output")
COMPARISON_WARNING = (
    "Escenario hipotético con los mismos contadores: cambiar de modelo puede "
    "cambiar la tokenización, el razonamiento, la caché y el número de pasos."
)
BILLING_WARNING = "No representa un gasto realizado ni una factura; no autoriza llamadas ni pagos."
SCOPE_WARNING = (
    "Solo se comparan tarifas base de tokens de texto. No se incluyen cargos "
    "de herramientas, almacenamiento, impuestos ni recargos no aportados."
)


class CostDataError(ValueError):
    """Invalid counters or tariff metadata must not become a cost estimate."""


def _counter(value, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise CostDataError("El contador debe ser un entero no negativo o desconocido: " + field)
    return value


def _steps(observed_tokens) -> list[dict[str, int | None]]:
    if observed_tokens is None:
        return []
    if not isinstance(observed_tokens, (list, tuple)) or len(observed_tokens) > MAX_STEPS:
        raise CostDataError("Se requiere una lista acotada de contadores por paso.")
    steps = []
    for index, observed in enumerate(observed_tokens):
        if observed is None:
            observed = {}
        if not isinstance(observed, dict):
            raise CostDataError("Los contadores de cada paso deben ser un objeto o desconocidos.")
        cache = observed.get("cache")
        if cache is None:
            cache = {}
        if not isinstance(cache, dict):
            raise CostDataError("Los contadores de caché deben ser un objeto o desconocidos.")
        values = {
            "input_uncached": observed.get("input"),
            "cache_read": cache.get("read"),
            "cache_write": cache.get("write"),
            "output": observed.get("output"),
            "reasoning": observed.get("reasoning"),
        }
        steps.append({field: _counter(value, f"paso {index + 1}: {field}") for field, value in values.items()})
    return steps


def _complete_sum(values):
    return sum(values) if values and all(value is not None for value in values) else None


def summarize_usage(observed_tokens) -> dict:
    """Sum disjoint CLI counters, preserving every absent bucket as unknown.

    ``observed_tokens`` is the list from ``step_finish.part.tokens``. ``None``
    or an empty list means no observations, not a confirmed zero-token run.
    ``known_tokens`` contains partial subtotals and is never a complete total.
    """
    steps = _steps(observed_tokens)
    tokens, known = {}, {}
    for field in TOKEN_FIELDS:
        values = [step[field] for step in steps]
        tokens[field] = _complete_sum(values)
        present = [value for value in values if value is not None]
        known[field] = sum(present) if present else None
    tokens["input_total"] = _complete_sum([tokens[field] for field in ("input_uncached", "cache_read", "cache_write")])
    tokens["output_billable"] = _complete_sum([tokens["output"], tokens["reasoning"]])
    tokens["total"] = _complete_sum([tokens["input_total"], tokens["output_billable"]])
    unknown = [field for field in TOKEN_FIELDS if tokens[field] is None]
    warnings = []
    if unknown:
        warnings.append("Faltan contadores; los valores desconocidos no se convierten en cero.")
    return {
        "steps": None if observed_tokens is None else len(steps),
        "token_semantics": TOKEN_SEMANTICS,
        "semantics_source": SEMANTICS_SOURCE,
        "tokens": tokens,
        "known_tokens": known,
        "unknown_fields": unknown,
        "complete": bool(steps) and not unknown,
        "warnings": warnings,
    }


def _rate(value, field: str) -> Decimal | None:
    if value is None:
        return None
    if type(value) not in (str, int, Decimal):
        raise CostDataError("La tarifa debe ser un decimal exacto, no float ni bool: " + field)
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise CostDataError("Tarifa decimal no válida: " + field) from None
    if not result.is_finite() or result < 0 or abs(result.as_tuple().exponent) > 100:
        raise CostDataError("La tarifa debe ser finita y no negativa: " + field)
    return result


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _tariff(tariff) -> tuple[dict, dict[str, Decimal | None], bool]:
    if not isinstance(tariff, dict):
        raise CostDataError("Se requiere una tarifa con fuente, fecha, proveedor y modelo.")
    metadata = {}
    for field in ("provider", "model", "currency", "source", "verified_at"):
        value = tariff.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 1000:
            raise CostDataError("Falta la procedencia de la tarifa: " + field)
        metadata[field] = value
    if not re.fullmatch(r"[A-Z]{3}", metadata["currency"]):
        raise CostDataError("La moneda debe usar un código de tres letras mayúsculas.")
    try:
        value = metadata["verified_at"]
        date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CostDataError("La fecha de verificación debe usar formato ISO.") from None
    supplied_rates = tariff.get("rates_per_million", {})
    if not isinstance(supplied_rates, dict) or set(supplied_rates) - set(RATE_FIELDS):
        raise CostDataError("Las tarifas por millón contienen componentes no admitidos.")
    rates = {field: _rate(supplied_rates.get(field), field) for field in RATE_FIELDS}
    metadata["rates_per_million"] = {field: _decimal_text(rate) for field, rate in rates.items()}
    tiers = tariff.get("context_tiers", [])
    if not isinstance(tiers, list):
        raise CostDataError("Los niveles de contexto deben ser una lista explícita.")
    # No silently applying a base tariff to a model with supplied tier pricing.
    # A future tier implementation must evaluate context per request, not by
    # summing the entire session first.
    supported = not tiers
    metadata["context_tiers_supported"] = supported
    metadata["pricing_scope"] = "base_text_token_rates"
    for field in ("comparison_note", "model_difference_note"):
        if field in tariff:
            value = tariff[field]
            if not isinstance(value, str) or len(value) > 1000:
                raise CostDataError("La nota de comparación no es válida.")
            metadata[field] = value
    return metadata, rates, supported


def estimate_usage(observed_tokens, tariff) -> dict:
    """Apply a supplied flat tariff to the same observed counters, offline.

    Formula in currency units: ``(uncached_input * input_rate + cache_read *
    read_rate + cache_write * write_rate + (visible_output + reasoning) *
    output_rate) / 1_000_000``. Missing usage/rates keep a component unknown;
    zero known cache writes need no cache-write rate. Supplied context tiers
    are not implemented and block all hypothetical costs instead of guessing.
    """
    summary = summarize_usage(observed_tokens)
    metadata, rates, supported = _tariff(tariff)
    tokens = summary["tokens"]
    quantities = {
        "input_uncached": tokens["input_uncached"],
        "cache_read": tokens["cache_read"],
        "cache_write": tokens["cache_write"],
        "output": tokens["output_billable"],
    }
    mapped_rates = {"input_uncached": rates["input"], **{key: rates[key] for key in ("cache_read", "cache_write", "output")}}
    # Precision grows with caller-provided exact integers and decimal rates.
    # Avoid binary floats and cent rounding: small tasks cost fractions of a cent.
    count_digits = max((len(str(value)) for value in quantities.values() if value is not None), default=1)
    rate_digits = max((len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                       for value in rates.values() if value is not None), default=1)
    components = {}
    with localcontext() as context:
        context.prec = max(50, count_digits + rate_digits + 20)
        for field, quantity in quantities.items():
            rate = mapped_rates[field]
            if not supported or quantity is None:
                components[field] = None
            elif quantity == 0:
                components[field] = Decimal(0)
            elif rate is None:
                components[field] = None
            else:
                components[field] = Decimal(quantity) * rate / MILLION
        present = [value for value in components.values() if value is not None]
        components["total"] = sum(present, Decimal(0)) if len(present) == 4 else None
        components["known_subtotal"] = sum(present, Decimal(0)) if present else None
    warnings = [COMPARISON_WARNING, BILLING_WARNING, SCOPE_WARNING, *summary["warnings"]]
    if not supported:
        warnings.append("La tarifa incluye niveles de contexto no implementados; el coste queda desconocido.")
    if any(value is None for value in mapped_rates.values()):
        warnings.append("Las tarifas ausentes no se consideran gratuitas; un componente con uso positivo queda desconocido.")
    if metadata.get("model_difference_note"):
        warnings.append(metadata["model_difference_note"])
    return {
        "scenario": "hypothetical",
        "currency": metadata["currency"],
        "usage": summary,
        "tariff": metadata,
        "hypothetical_cost": {field: _decimal_text(value) for field, value in components.items()},
        "complete": components["total"] is not None,
        "warnings": warnings,
    }


def default_tariffs() -> list[dict]:
    """Return fresh copies of three dated public tariff snapshots, not quotes.

    The pricing table lists no cache-write price for these models; ``None``
    preserves that gap. MiniMax M3 is not MiniMax M3.1 Flash Free. No snapshot
    changes the model allowlist or supplies a runnable paid model configuration.
    """
    specifications = (
        ("glm-5.3-flash", "0.15", "0.50", "0.03"),
        ("deepseek-v4.1-flash", "0.30", "1.20", "0.006"),
        ("minimax-m3", "0.30", "1.20", "0.06"),
    )
    result = []
    for model, input_rate, output_rate, read_rate in specifications:
        tariff = {
            "provider": "opencode",
            "model": model,
            "currency": "USD",
            "source": TARIFF_SOURCE,
            "verified_at": TARIFF_VERIFIED_AT,
            "rates_per_million": {"input": input_rate, "output": output_rate, "cache_read": read_rate, "cache_write": None},
            "context_tiers": [],
            "comparison_note": COMPARISON_WARNING,
        }
        if model == "minimax-m3":
            tariff["model_difference_note"] = (
                "MiniMax M3 es un modelo diferente de MiniMax M3.1 Flash Free; "
                "esta comparación no presume equivalencia ni el mismo consumo."
            )
        result.append(tariff)
    return result
