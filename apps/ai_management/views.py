"""Owner-scoped AI management. Configuration and manual reconciliation require staff."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.assistant import provider
from .catalog import CATALOG, VERIFIED_ON, catalog_entry
from .forms import AccountForm, CalculatorForm, ProfileForm, ReconciliationForm
from .models import AIAccount, AIProfile, AIUsage
from .services import account_summary, estimate_cost, get_account, profile_snapshot, reconcile_usage


def _staff(user):
    from apps.assistant.execution import require_human_superadmin
    require_human_superadmin(user)


def _error(form, error):
    for text in error.messages:
        form.add_error(None, text)


def _base(request, section):
    account = get_account(request.user)
    try:
        from .agent_access import agent_preview_snapshot
        snapshot = agent_preview_snapshot(account)
        if not provider.profile_ready(snapshot):
            raise ValidationError("Conecta el proveedor y revisa el acceso del agente en APIs y agentes.")
        readiness = "Configuración disponible"
        ready = True
    except ValidationError as error:
        snapshot = None
        readiness = " ".join(error.messages)
        ready = False
    return {
        "account": account, "section": section, "summary": account_summary(account),
        "ready": ready, "readiness": readiness, "active_snapshot": snapshot,
        "catalog_verified_on": VERIFIED_ON,
    }


@login_required
@require_GET
def index(request):
    context = _base(request, "summary")
    context["recent_usage"] = AIUsage.objects.filter(account=context["account"]).select_related("job__event")[:8]
    return render(request, "ai_management/index.html", context)


@login_required
@require_GET
def providers(request):
    context = _base(request, "providers")
    profiles = list(AIProfile.objects.filter(owner=request.user))
    from .models import AgentGrant
    grant = AgentGrant.objects.filter(account__owner=request.user).first()
    rows = []
    for item in profiles:
        try:
            snapshot = profile_snapshot(item)
            if grant and item.pk in {grant.primary_profile_id, grant.fallback_profile_id}:
                snapshot["agent_grant_id"] = grant.pk
            ready = provider.profile_ready(snapshot)
            status = "Referencia de conexión disponible" if ready else "Credencial o servicio pendiente"
        except ValidationError as error:
            ready, status = False, " ".join(error.messages)
        rows.append({"profile": item, "ready": ready, "status": status})
    context["profiles"] = rows
    context["catalog"] = [catalog_entry(key) for key in CATALOG]
    return render(request, "ai_management/providers.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request, profile_id=None):
    _staff(request.user)
    profile = get_object_or_404(AIProfile, pk=profile_id, owner=request.user) if profile_id is not None else None
    form = ProfileForm(request.POST if request.method == "POST" else None, profile=profile, preset=request.GET.get("preset"))
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                # Keep User before Account, including FK checks during profile creation.
                _staff(get_user_model().objects.select_for_update().get(pk=request.user.pk))
                account = get_account(request.user)
                AIAccount.objects.select_for_update().get(pk=account.pk)
                current = AIProfile.objects.select_for_update().get(pk=profile.pk, owner=request.user) if profile else None
                if (current.version if current else 0) != form.cleaned_data["expected_version"]:
                    raise ValidationError("El perfil cambió en otra pestaña. Recarga antes de guardar.")
                entry = catalog_entry(form.cleaned_data["preset"])
                current = current or AIProfile(owner=request.user)
                for name in ("name", "enabled", "max_input_tokens", "max_output_tokens", "free_tier_confirmed"):
                    setattr(current, name, form.cleaned_data[name])
                for name in ("provider", "model", "mode", "input_rate", "cached_rate", "output_rate", "source_url", "verified_on"):
                    setattr(current, name, entry[name])
                if profile:
                    current.version += 1
                current.full_clean()
                current.save()
        except ValidationError as error:
            _error(form, error)
        else:
            messages.success(request, "Perfil guardado. Elígelo en Presupuesto para nuevas solicitudes.")
            return redirect("ai_management:providers")
    context = _base(request, "providers")
    context.update(form=form, profile=profile, form_title="Editar perfil de IA" if profile else "Configurar un perfil de IA",
                   form_description="Las claves se guardan en el entorno del servidor. Esta pantalla no realiza llamadas de IA.")
    return render(request, "ai_management/form.html", context, status=400 if request.method == "POST" and form.errors else 200)


@login_required
@require_http_methods(["GET", "POST"])
def budget(request):
    _staff(request.user)
    account = get_account(request.user)
    form = AccountForm(request.POST if request.method == "POST" else None, account=account)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                _staff(get_user_model().objects.select_for_update().get(pk=request.user.pk))
                current = AIAccount.objects.select_for_update().get(pk=account.pk, owner=request.user)
                if current.version != form.cleaned_data["expected_version"]:
                    raise ValidationError("El presupuesto cambió en otra pestaña. Recarga y revisa los límites actuales.")
                for name in ("active_profile", "monthly_budget_usd", "monthly_token_limit", "paid_enabled"):
                    setattr(current, name, form.cleaned_data[name])
                if current.active_profile and current.active_profile.owner_id != request.user.pk:
                    raise PermissionDenied
                current.version += 1
                current.full_clean()
                current.save()
        except ValidationError as error:
            _error(form, error)
        else:
            messages.success(request, "Presupuesto guardado. No se ha realizado ninguna solicitud de IA.")
            return redirect("ai_management:index")
    context = _base(request, "summary")
    context.update(form=form, form_title="Presupuesto y selección de IA",
                   form_description="Límite mensual bruto en USD y tokens. Los créditos no se descuentan automáticamente del presupuesto.",
                   is_budget=True)
    return render(request, "ai_management/form.html", context, status=400 if request.method == "POST" and form.errors else 200)


@login_required
@require_http_methods(["GET", "POST"])
def calculator(request):
    form = CalculatorForm(request.POST if request.method == "POST" else None)
    quote = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        entry = catalog_entry(data["preset"])
        applied_cache = 0 if entry["cache_policy"] == "disabled" else data["cached_tokens"]
        per_request = estimate_cost(entry, input_tokens=data["input_tokens"], output_tokens=data["output_tokens"],
                                    cached_tokens=applied_cache)
        gross = per_request * data["requests"]
        quote = {
            "profile": entry, "per_request": per_request, "gross": gross,
            "cache_disabled": entry["cache_policy"] == "disabled",
            "requests": data["requests"], "credits": data["credits"],
            "after_credits": max(Decimal("0"), gross - data["credits"]),
            "tokens": (data["input_tokens"] + data["output_tokens"]) * data["requests"],
        }
    context = _base(request, "calculator")
    context.update(form=form, quote=quote)
    return render(request, "ai_management/calculator.html", context, status=400 if request.method == "POST" and form.errors else 200)



@login_required
@require_GET
def usage(request):
    from .forms import UsageFilterForm
    from .reporting import aggregate_usage, group_usage_by_event, group_usage_by_operation
    form = UsageFilterForm(_filter_data(request.GET), owner=request.user)
    context = _base(request, "usage")
    context["filter_form"] = form
    if not form.is_valid():
        context["usage_page"] = None
        return render(request, "ai_management/usage.html", context, status=400)
    rows, selected_event = _filtered_usage(form, request.user)
    context.update(
        selected_event=selected_event,
        analysis_summary=aggregate_usage(rows),
        event_groups=group_usage_by_event(rows),
        operation_groups=group_usage_by_operation(rows),
    )
    context["usage_page"] = Paginator(rows.select_related("job__event", "reconciled_by"), 20).get_page(request.GET.get("page"))
    query = _filter_data(request.GET)
    query.pop("page", None)
    context["filter_query"] = query.urlencode()
    return render(request, "ai_management/usage.html", context)

@login_required
@require_http_methods(["GET", "POST"])
def reconcile(request, usage_id):
    _staff(request.user)
    item = get_object_or_404(AIUsage.objects.select_related("job__event"), pk=usage_id, account__owner=request.user)
    form = ReconciliationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            reconcile_usage(usage_id=item.pk, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _error(form, error)
        else:
            messages.success(request, "Conciliación manual registrada con su fuente y responsable.")
            return redirect("ai_management:usage")
    context = _base(request, "usage")
    context.update(form=form, item=item, form_title="Conciliar consumo desconocido",
                   form_description="Comprueba primero los tokens en el proveedor. Es una declaración manual; una respuesta real tardía tiene prioridad.",
                   is_reconciliation=True)
    return render(request, "ai_management/form.html", context, status=400 if request.method == "POST" and form.errors else 200)

def _filter_data(data):
    """Current ledger month by default; explicitly blank means all months."""
    from .services import current_month
    normalized = data.copy()
    if "month" not in normalized:
        normalized["month"] = current_month().strftime("%Y-%m")
    return normalized


def _filtered_usage(form, owner):
    from apps.events.models import Event
    from .reporting import owner_usage
    event_id = form.cleaned_data.get("event")
    selected_event = get_object_or_404(Event, pk=event_id, owner=owner) if event_id else None
    return owner_usage(
        owner, event_id=event_id, kind=form.cleaned_data.get("kind", ""),
        month=form.cleaned_data.get("month"),
    ), selected_event


@login_required
@require_http_methods(["GET", "POST"])
def compare(request):
    from decimal import ROUND_CEILING
    from .forms import ComparisonForm
    from .reporting import aggregate_usage, compare_scenario, historical_scenario, manual_scenario
    if request.method == "POST":
        form = ComparisonForm(_filter_data(request.POST), owner=request.user)
    else:
        from django.http import QueryDict
        # Validate deep links with the same rules as submitted scenarios.
        # Defaults come from the form; GET only prepares it, never calculates.
        data = QueryDict("", mutable=True)
        for name, field in ComparisonForm.base_fields.items():
            if field.initial is not None:
                data[name] = field.initial
        data["month"] = _filter_data(request.GET)["month"]
        data.update(request.GET)
        if "source" not in request.GET and request.GET.get("event"):
            data["source"] = "history"
        form = ComparisonForm(data, owner=request.user, initial=data.dict())
    result = None
    selected_event = None
    if request.method == "GET" and form.is_valid() and form.cleaned_data.get("event"):
        _, selected_event = _filtered_usage(form, request.user)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data
            historical = None
            if data["source"] == "history":
                rows, selected_event = _filtered_usage(form, request.user)
                scenario = historical_scenario(rows)
                historical = aggregate_usage(rows)
            else:
                # Even an unused event reference must belong to this user.
                if data.get("event"):
                    _filtered_usage(form, request.user)
                scenario = manual_scenario(
                    input_tokens=data["input_tokens"], output_tokens=data["output_tokens"],
                    cached_tokens=data["cached_tokens"], requests=data["requests"],
                )
            comparisons = compare_scenario(scenario)
            conversion = None
            if data.get("pen_rate") is not None:
                conversion = {"rate": data["pen_rate"], "date": data["pen_date"], "source": data["pen_source"]}
                for item in comparisons:
                    item["gross_pen"] = ((item["gross"] * conversion["rate"]).quantize(
                        Decimal("0.000001"), rounding=ROUND_CEILING) if item["gross"] is not None else None)
            result = {"scenario": scenario, "comparisons": comparisons, "historical": historical,
                      "conversion": conversion}
        except ValidationError as error:
            _error(form, error)
    context = _base(request, "calculator")
    context.update(form=form, comparison=result, selected_event=selected_event)
    return render(request, "ai_management/compare.html", context,
                  status=400 if form.errors else 200)
