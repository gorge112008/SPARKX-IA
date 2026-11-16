"""Offline comparisons, never a billing authority or a paid model connector."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .costs import default_tariffs, estimate_usage, summarize_usage


def reported_cost(values, expected_steps):
    subtotal = Decimal(0)
    known = 0
    if isinstance(values, list):
        for value in values:
            if type(value) not in (int, float, str):
                continue
            try:
                amount = Decimal(str(value))
            except InvalidOperation:
                continue
            if amount.is_finite() and 0 <= amount <= Decimal("1000000000") and abs(amount.as_tuple().exponent) <= 100:
                subtotal += amount
                known += 1
    complete = (type(expected_steps) is int and expected_steps > 0
                and isinstance(values, list) and len(values) == expected_steps == known)
    return {"total": format(subtotal, "f") if complete else None,
            "known_subtotal": format(subtotal, "f"), "complete": complete,
            "steps_with_reported_cost": known, "currency": "USD",
            "source": "OpenCode step_finish.cost", "billing_independently_verified": False}


def build_comparison(result: dict) -> dict:
    if not isinstance(result, dict):
        raise ValueError("El resultado no es un objeto válido.")
    semantics = result.get("token_semantics")
    # Existing receipt from the first approved trial predates this field.
    preflight = result.get("preflight")
    if semantics is None and isinstance(preflight, dict) and preflight.get("version") == "2.2.7":
        semantics = "opencode-v2.2.7"
    if semantics != "opencode-v2.2.7":
        raise ValueError("No se ha verificado la semántica de tokens de esta versión.")
    tokens = result.get("observed_tokens")
    usage = summarize_usage(tokens)
    declared_steps = result.get("observed_steps")
    counters_match = (type(declared_steps) is int and declared_steps > 0 and declared_steps == usage["steps"]
                      and not result.get("counters_incomplete") and result.get("status") == "review_required")
    scenarios = [estimate_usage(tokens, tariff) for tariff in default_tariffs()]
    # A missing whole step must not silently turn a partial receipt into a full
    # cost, even when all buckets in the available steps are well formed.
    if not counters_match:
        for scenario in scenarios:
            scenario["hypothetical_cost"]["total"] = None
            scenario["complete"] = False
            scenario["warnings"].append("Recibo incompleto: faltan pasos o la ejecución no terminó con respuesta completa.")
    for scenario in scenarios:
        total = scenario["hypothetical_cost"]["total"]
        scenario["identical_workload_projections"] = {
            str(count): format(Decimal(total) * count, "f") if total is not None else None
            for count in (1, 100, 1000)
        }
    model = result.get("model")
    if not isinstance(model, dict) or not isinstance(model.get("id"), str):
        raise ValueError("El resultado no identifica el modelo medido.")
    cost = reported_cost(result.get("reported_cost"), declared_steps)
    if not counters_match:
        cost.update(total=None, complete=False)
    return {
        "task": result.get("task"), "measured_model": model["id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Ayudante de desarrollo; no corresponde al agente de eventos de SparkX",
        "source_result_status": result.get("status"), "usage": usage,
        "step_counters_match": counters_match,
        "reported_cost": cost,
        "scenarios": scenarios,
        "paid_models_invoked": False,
        "warnings": [
            "Estimaciones con los mismos contadores observados y tarifas de referencia; no son facturas ni reservas de gasto.",
            "Otro modelo puede cambiar tokenización, razonamiento, caché, reintentos, calidad y duración.",
            "Las proyecciones repiten idénticamente esta muestra; no representan usuarios simultáneos o una previsión mensual.",
            "Tarifas con fecha y fuente; revisar su vigencia y las condiciones del proveedor antes de decidir un gasto.",
            "No se incluyen impuestos, compra de créditos, herramientas, voz, almacenamiento o infraestructura.",
            "Los contadores publicados por el harness no garantizan una contabilidad completa del proveedor.",
        ],
    }


def render_markdown(report: dict) -> str:
    def number(value):
        return "Desconocido" if value is None else str(value)

    usage = report["usage"]["tokens"]
    actual = report["reported_cost"]
    lines = ["# Consumo observado y comparación hipotética", "",
             f"Modelo de la muestra: `{report['measured_model']}`. Ayudante de desarrollo OpenCode.", "",
             f"**Coste reportado por OpenCode: USD {number(actual['total'])}.** No es una factura auditada.", "",
             "| Contador observado | Tokens |", "| --- | ---: |"]
    for label, key in (
        ("Entrada sin caché", "input_uncached"), ("Lectura de caché", "cache_read"),
        ("Escritura de caché", "cache_write"), ("Salida visible", "output"),
        ("Razonamiento", "reasoning"), ("Total de entrada", "input_total"),
        ("Total de salida con razonamiento", "output_billable"), ("Total observado", "total"),
    ):
        lines.append(f"| {label} | {number(usage[key])} |")
    lines += ["", "## Escenarios con tarifas pagadas", "",
              "Estos modelos **no se han ejecutado**. Se aplican sus tarifas a los mismos contadores.", "",
              "| Tarifa de referencia | 1 trabajo · USD | 100 trabajos idénticos · USD | 1.000 trabajos idénticos · USD |",
              "| --- | ---: | ---: | ---: |"]
    for scenario in report["scenarios"]:
        values = scenario["identical_workload_projections"]
        lines.append(f"| {scenario['tariff']['model']} | {number(values['1'])} | {number(values['100'])} | {number(values['1000'])} |")
    lines += ["", "## Fuentes, supuestos y límites", ""]
    for scenario in report["scenarios"]:
        tariff = scenario["tariff"]
        lines.append(f"- `{tariff['model']}`: proveedor {tariff['provider']}; comprobada {tariff['verified_at']}; [fuente]({tariff['source']}).")
        lines += ["  " + warning for warning in scenario["warnings"]]
    lines += ["", *["- " + warning for warning in report["warnings"]], "",
              "Si falta un contador o una tarifa necesaria, el total queda desconocido.", ""]
    return "\n".join(lines)
