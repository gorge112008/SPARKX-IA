"""Private API controls. No credential response, inference or agent authority."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from apps.assistant.execution import require_human_superadmin
from .agent_access import agent_grant_summary, update_agent_grant
from .agent_identity import AGENT_DISPLAY_NAME
from .catalog import CATALOG, catalog_entry, preset_for
from .control_forms import AgentAccessForm, CredentialForm, PoolEntryForm
from .credential_security import force_redact_request, require_private_transport
from .models import AIAccount, AIProfile, AgentGrant
from .pilot import openai_pilot_summary
from .runtime_credentials import PROVIDERS, credential_status, disconnect_credential, set_credential
from .services import get_account


def _authorize(request):
    force_redact_request(request)
    actor = require_human_superadmin(request.user)
    require_private_transport(request)
    return actor


def _context(actor, *, form=None, pool_form=None, pool_preset=None):
    from .free_pool import pool_summary
    from tools.opencode.catalog import policy_fingerprint

    account = get_account(actor)
    grant = AgentGrant.objects.filter(account=account).select_related("primary_profile", "fallback_profile").first()
    summary = pool_summary(grant)
    assigned = {row["profile"].model: row for row in summary["entries"]}
    policies = [(code, catalog_entry(code)) for code, item in CATALOG.items() if item["provider"] == "opencode"]
    for _, spec in policies:
        spec["model_policy_version"] = policy_fingerprint(spec["model"])
    rows = [{**assigned.get(spec["model"], {}), "code": code, "policy": spec}
            for code, spec in policies]
    selected_code = pool_form["preset"].value() if pool_form is not None else pool_preset
    selected = next((row for row in rows if row["code"] == selected_code), rows[0])
    if pool_form is not None and pool_form.is_bound:
        # Returning an error never carries an old policy acceptance forward.
        # Keep the non-sensitive draft, and present the currently displayed hash.
        pool_form.data = pool_form.data.copy()
        pool_form.data.pop("accept_policy", None)
        pool_form.data["expected_policy_fingerprint"] = selected["policy"]["model_policy_version"]
    if form is not None and form.is_bound:
        fallback_code = form["fallback_preset"].value()
        fallback = next((spec for code, spec in policies if code == fallback_code), None)
        form.data = form.data.copy()
        form.data.pop("accept_fallback_policy", None)
        form.data["expected_fallback_policy_fingerprint"] = fallback["model_policy_version"] if fallback else ""
    return {"section": "control", "account": account, "grant": grant,
        "agent_form": form or AgentAccessForm(account=account, grant=grant),
        "pool_form": pool_form or PoolEntryForm(grant=grant, preset=selected["code"], entry=selected.get("entry")),
        "pool_rows": rows, "pool_summary": summary,
        "pool_selected_code": selected_code if selected_code in {code for code, _ in policies} else selected["code"],
        "credential_form": CredentialForm(),
        "connections": [credential_status(actor.pk, name) for name in PROVIDERS],
        "agent_summary": agent_grant_summary(grant) if grant else None,
        "pilot_summary": openai_pilot_summary(),
        "fallback_policies": policies}


@login_required
@never_cache
@require_GET
def control(request):
    actor = _authorize(request)
    return render(request, "ai_management/control.html", _context(actor, pool_preset=request.GET.get("pool_model")))


@login_required
@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def credential_save(request):
    actor = _authorize(request)
    form = CredentialForm(request.POST)
    if not form.is_valid():
        # Never rerender bound fields, POST values or errors containing input.
        messages.error(request, "Revisa el proveedor y la clave privada: entre 16 y 1024 caracteres, sin espacios.")
    else:
        try:
            set_credential(actor=actor, provider=form.cleaned_data["provider"], secret=form.cleaned_data["api_key"])
        except Exception:
            messages.error(request, "No se guardó la conexión. Revisa los campos e inténtalo de nuevo.")
        else:
            messages.success(request, "Conexión disponible en memoria por hasta dos horas o hasta cerrar SparkX. No se realizó ninguna llamada de IA.")
    return redirect("ai_management:control")


@login_required
@never_cache
@require_POST
def credential_remove(request):
    actor = _authorize(request)
    try:
        disconnect_credential(actor=actor, provider=request.POST.get("provider", ""))
    except ValidationError:
        messages.error(request, "No se pudo desconectar ese proveedor.")
    else:
        messages.success(request, "Proveedor desconectado para próximas solicitudes. Una llamada ya iniciada conserva su contabilidad.")
    return redirect("ai_management:control")


@login_required
@never_cache
@require_POST
def agent_save(request):
    actor = _authorize(request)
    account = get_account(actor)
    grant = AgentGrant.objects.filter(account=account).select_related("fallback_profile").first()
    form = AgentAccessForm(request.POST, account=account, grant=grant)
    if form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
                require_human_superadmin(actor)
                account = AIAccount.objects.select_for_update().get(pk=account.pk)
                fallback = None
                if data["fallback_preset"]:
                    spec = catalog_entry(data["fallback_preset"])
                    if not data["accept_fallback_policy"] and (not grant or not grant.fallback_profile
                            or grant.fallback_profile.model != spec["model"]):
                        raise ValidationError("Acepta las condiciones del modelo gratuito elegido antes de autorizarlo.")
                    fallback, _ = AIProfile.objects.get_or_create(owner=actor,
                        name=AGENT_DISPLAY_NAME + " · alternativa · " + data["fallback_preset"],
                        defaults={**{key: spec[key] for key in ("provider", "model", "mode", "input_rate",
                            "cached_rate", "output_rate", "source_url", "verified_on")},
                            "enabled": True, "free_tier_confirmed": True, "max_input_tokens": 24000, "max_output_tokens": 2048})
                update_agent_grant(actor=actor, account=account, expected_version=data["expected_version"],
                    name=AGENT_DISPLAY_NAME, enabled=data["enabled"], budget_usd=data["budget_usd"],
                    primary_profile=data["primary_profile"], fallback_profile=fallback,
                    accept_fallback_policy=data["accept_fallback_policy"],
                    expected_fallback_policy_fingerprint=data["expected_fallback_policy_fingerprint"],
                    free_pool_enabled=data["free_pool_enabled"] if data["pool_options_present"] or "free_pool_enabled" in request.POST else None,
                    free_pool_for_plans=data["free_pool_for_plans"] if data["pool_options_present"] or "free_pool_for_plans" in request.POST else None)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Acceso de {AGENT_DISPLAY_NAME} actualizado. El servidor aplicará los límites antes de cada solicitud.")
            return redirect("ai_management:control")
    return render(request, "ai_management/control.html", _context(actor, form=form), status=400)


@login_required
@never_cache
@require_POST
def pool_entry_save(request):
    from .free_pool import configure_entry

    actor = _authorize(request)
    account = get_account(actor)
    grant = AgentGrant.objects.filter(account=account).first()
    form = PoolEntryForm(request.POST, grant=grant)
    if form.is_valid():
        try:
            configure_entry(actor=actor, account=account, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Modelo gratuito configurado. No se realizó ninguna llamada; la cuota remota sigue sin comprobar.")
            return redirect("ai_management:control")
    return render(request, "ai_management/control.html", _context(actor, pool_form=form), status=400)
