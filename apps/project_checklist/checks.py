"""Read-only local hints, separate from the owner's manual declarations.

No check contacts a provider, creates an account or dispatches work. A configured
credential is not proof of validity, credit or quota; historical records are not
independent confirmation of real inference or the provider's final invoice.
"""
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.ai_management.services import (
    account_summary,
    configured_snapshot,
    estimate_cost,
    profile_snapshot,
)
from apps.assistant import provider
from apps.jobs.models import Job
from apps.planning.models import PlanCandidate, PlanRevision


def _result(status, message, checked_at):
    return {"status": status, "message": message, "checked_at": checked_at}


def _budget_result(account, snapshot, checked_at):
    """Compare local limits with one maximum reservation, without reserving it."""
    if snapshot["mode"] == AIProfile.Mode.PAID and (
        not account.paid_enabled or account.monthly_budget_usd <= 0
    ):
        return _result("pending", "La API de pago sigue desactivada o sin presupuesto local positivo. Este checklist no la activa.", checked_at)
    summary = account_summary(account)
    if summary["limit_breach_count"] or summary["over_budget"] or summary["over_token_limit"]:
        return _result("pending", "El consumo o las reservas registradas requieren revisar los límites locales en Gestión de IA.", checked_at)
    maximum_rates = {
        **snapshot,
        "input_rate": str(max(Decimal(snapshot["input_rate"]), Decimal(snapshot["cached_rate"]))),
    }
    maximum_cost = estimate_cost(
        maximum_rates,
        input_tokens=snapshot["max_input_tokens"],
        output_tokens=snapshot["max_output_tokens"],
    )
    if (
        maximum_cost > summary["available_usd"]
        or snapshot["max_input_tokens"] + snapshot["max_output_tokens"] > summary["available_tokens"]
    ):
        return _result("pending", "Los límites locales disponibles no cubren la reserva máxima de una solicitud del perfil activo.", checked_at)
    return _result("ready", "Los límites locales cubren una reserva máxima del perfil activo en este momento. No se reservó ni gastó nada; saldo, cuota y recargas externas requieren revisión manual.", checked_at)


def _has_recorded_journey(owner):
    """Require one coherent owner/event/job/candidate/approval/usage chain."""
    jobs = Job.objects.filter(
        event__owner=owner,
        actor=owner,
        kind=Job.Kind.PLAN,
        status=Job.Status.SUCCEEDED,
        ai_usage__account__owner=owner,
        ai_usage__status=AIUsage.Status.SETTLED,
        ai_usage__accounting_source=AIUsage.AccountingSource.PROVIDER,
        ai_usage__dispatch_token__isnull=False,
        ai_usage__dispatched_at__isnull=False,
        ai_usage__settled_at__isnull=False,
        ai_usage__input_tokens__isnull=False,
        ai_usage__output_tokens__isnull=False,
        ai_usage__total_tokens__gt=0,
    ).values_list("event_id", "result")
    for event_id, result in jobs.iterator():
        if not isinstance(result, dict):
            continue
        try:
            candidate_id = UUID(str(result.get("candidate_id", "")))
        except (ValueError, TypeError, AttributeError):
            continue
        if PlanRevision.objects.filter(
            event_id=event_id,
            event__owner=owner,
            approved_by=owner,
            candidate_id=candidate_id,
            candidate__event_id=event_id,
            candidate__created_by=owner,
            candidate__status=PlanCandidate.Status.APPROVED,
        ).exists():
            return True
    return False


def collect_local_checks(owner, at=None):
    """Return safe local hints by catalog key; never alter manual completion."""
    checked_at = at or timezone.now()
    checks = {
        "creditos_api": _result("info", "Revisión manual en la cuenta del proveedor: vinculación, saldo, vigencia, cuota y recargas. SparkX no consulta ni confirma esos datos desde este módulo.", checked_at),
        "credencial_privada": _result("pending", "Selecciona un perfil propio en Gestión de IA y configura su credencial de forma privada. No pegues claves en este módulo.", checked_at),
        "presupuesto_ia": _result("pending", "Revisa el perfil y los límites locales en Gestión de IA. Este checklist no cambia presupuestos ni autoriza consumo.", checked_at),
        "prueba_recorrido": _result("pending", "No se encontró un recorrido local enlazado de propuesta, aprobación y consumo informado por el proveedor para tus eventos. Una demo manual no lo acredita.", checked_at),
    }
    if not getattr(owner, "pk", None):
        return checks
    account = AIAccount.objects.select_related("active_profile").filter(owner=owner).first()
    if account is not None and account.active_profile_id:
        profile = account.active_profile
        if profile.owner_id == owner.pk:
            try:
                snapshot = profile_snapshot(profile)
                credential_present = provider.profile_ready(snapshot)
                if credential_present:
                    local_message = (
                        "El perfil local está habilitado en la configuración. No se comprobó que Ollama esté ejecutándose ni que el modelo esté disponible."
                        if profile.provider == AIProfile.Provider.OLLAMA
                        else "El perfil es válido y hay una credencial presente en la configuración privada. No se comprobó su validez, conexión, saldo ni cuota."
                    )
                    checks["credencial_privada"] = _result("ready", local_message, checked_at)
                checks["presupuesto_ia"] = _budget_result(account, snapshot, checked_at)
                # Reuse the runtime configuration gate as an additional local
                # check only. No exception detail can expose configuration data.
                if credential_present and checks["presupuesto_ia"]["status"] == "ready":
                    configured_snapshot(account)
            except ValidationError:
                checks["presupuesto_ia"] = _result("pending", "La configuración local del perfil o presupuesto necesita revisión en Gestión de IA. No se consultó al proveedor.", checked_at)
    if _has_recorded_journey(owner):
        checks["prueba_recorrido"] = _result("ready", "Hay registros locales enlazados de una propuesta, su aprobación y consumo informado por el proveedor. Revisa el resultado y contrástalo con el proveedor: estos registros no verifican por sí solos inferencia real, saldo ni facturación final.", checked_at)
    return checks
