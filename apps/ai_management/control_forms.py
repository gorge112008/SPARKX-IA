"""Human-only inputs; passwords are never rendered back into a response."""
from decimal import Decimal
from django import forms
from django.db.models import Q

from .catalog import CATALOG, preset_for
from .agent_identity import AGENT_DISPLAY_NAME
from .models import AIProfile, AgentPoolEntry
from .runtime_credentials import PROVIDERS


class CredentialForm(forms.Form):
    provider = forms.ChoiceField(label="Proveedor", choices=list(PROVIDERS.items()))
    api_key = forms.CharField(label="Clave API privada", min_length=16, max_length=1024,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off", "spellcheck": "false"}))


class AgentAccessForm(forms.Form):
    enabled = forms.BooleanField(label=f"{AGENT_DISPLAY_NAME} habilitado", required=False)
    free_pool_enabled = forms.BooleanField(label="Usar primero los modelos gratuitos autorizados", required=False,
        help_text="Las consultas mecánicas siguen siendo locales. No autoriza una llamada de pago cuando se agoten los gratuitos.")
    free_pool_for_plans = forms.BooleanField(label="Permitir al grupo gratuito preparar propuestas", required=False,
        help_text="Sólo modelos con rol Propuestas. La aprobación del plan sigue siendo manual.")
    pool_options_present = forms.BooleanField(required=False, initial=True, widget=forms.HiddenInput)
    primary_profile = forms.ModelChoiceField(label="Perfil principal", queryset=AIProfile.objects.none())
    budget_usd = forms.DecimalField(label="Tope total del agente · USD", min_value=0, max_value=1,
        max_digits=7, decimal_places=6, initial=Decimal("1"),
        help_text="Incluye consumo y reservas de esta cuenta. El piloto global continúa limitado a USD 1.")
    fallback_preset = forms.ChoiceField(label="Alternativa única por presupuesto · sin grupo", required=False)
    accept_fallback_policy = forms.BooleanField(required=False,
        label="Autorizo la alternativa elegida sólo con datos ficticios y acepto sus condiciones indicadas.")
    expected_fallback_policy_fingerprint = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, account, grant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["primary_profile"].queryset = AIProfile.objects.filter(owner_id=account.owner_id, enabled=True).filter(
            Q(provider="openai") | Q(mode__in=["free", "local"]))
        self.fields["fallback_preset"].choices = [("", "Sin alternativa automática")] + [
            (code, item["name"]) for code, item in CATALOG.items() if item["provider"] == "opencode"]
        if not self.is_bound:
            from tools.opencode.catalog import policy_fingerprint
            fallback = grant.fallback_profile if grant and grant.fallback_profile else None
            budget = grant.budget_usd if grant else Decimal("1")
            self.initial.update({"enabled": grant.enabled if grant else True,
                "free_pool_enabled": grant.free_pool_enabled if grant else False,
                "free_pool_for_plans": grant.free_pool_for_plans if grant else False,
                "primary_profile": grant.primary_profile_id if grant else account.active_profile_id,
                "budget_usd": format(budget.normalize(), "f"),
                "fallback_preset": preset_for(grant.fallback_profile) if grant and grant.fallback_profile else "",
                "expected_fallback_policy_fingerprint": policy_fingerprint(fallback.model) if fallback and fallback.provider == "opencode" and preset_for(fallback) else "",
                "expected_version": grant.version if grant else 0})

    def clean(self):
        data = super().clean()
        preset = data.get("fallback_preset")
        if data.get("accept_fallback_policy") and preset in CATALOG:
            from tools.opencode.catalog import policy_fingerprint
            current = policy_fingerprint(CATALOG[preset]["model"])
            if data.get("expected_fallback_policy_fingerprint") != current:
                raise forms.ValidationError("Las condiciones de la alternativa cambiaron. Revísalas y vuelve a aceptarlas.",
                                            code="agent_fallback_policy_changed")
        return data


class PoolEntryForm(forms.Form):
    preset = forms.ChoiceField(label="Modelo gratuito revisado")
    enabled = forms.BooleanField(label=f"Habilitar este modelo para {AGENT_DISPLAY_NAME}", required=False)
    roles = forms.ChoiceField(label="Tareas permitidas", choices=AgentPoolEntry.Roles.choices)
    priority = forms.IntegerField(label="Prioridad", min_value=1, max_value=100, initial=10,
        help_text="Menor número: se elige antes entre los modelos elegibles.")
    daily_request_limit = forms.IntegerField(label="Máximo interno de trabajos al día", min_value=1, max_value=100, initial=5)
    daily_token_limit = forms.IntegerField(label="Máximo interno de tokens al día", min_value=2049, max_value=1000000, initial=60000,
        help_text="Día UTC. Incluye reservas y consumos desconocidos; no es la cuota del proveedor.")
    accept_policy = forms.BooleanField(required=False,
        label="Acepto las condiciones exactas de este modelo, sólo para datos ficticios.")
    expected_policy_fingerprint = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    expected_grant_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, grant=None, preset=None, entry=None, **kwargs):
        kwargs.setdefault("auto_id", "pool_%s")
        super().__init__(*args, **kwargs)
        choices = [(code, item["name"]) for code, item in CATALOG.items()
                   if item["provider"] == "opencode" and item["mode"] == "free"]
        self.fields["preset"].choices = choices
        if not self.is_bound:
            allowed = {code for code, _ in choices}
            selected = preset_for(entry.profile) if entry else preset
            selected = selected if selected in allowed else choices[0][0]
            from tools.opencode.catalog import policy_fingerprint
            self.initial.update({"preset": selected if selected in allowed else choices[0][0],
                "enabled": entry.enabled if entry else False,
                "roles": entry.roles if entry else AgentPoolEntry.Roles.CHAT,
                "priority": entry.priority if entry else 10,
                "daily_request_limit": entry.daily_request_limit if entry else 5,
                "daily_token_limit": entry.daily_token_limit if entry else 60000,
                "accept_policy": False,
                "expected_policy_fingerprint": policy_fingerprint(CATALOG[selected]["model"]),
                "expected_grant_version": grant.version if grant else 1})

    def clean(self):
        data = super().clean()
        preset = data.get("preset")
        if data.get("accept_policy") and preset in CATALOG:
            from tools.opencode.catalog import policy_fingerprint
            current = policy_fingerprint(CATALOG[preset]["model"])
            if data.get("expected_policy_fingerprint") != current:
                raise forms.ValidationError("Las condiciones cambiaron. Revisa la política del modelo y vuelve a aceptarla.",
                                            code="free_pool_policy_changed")
        return data
