"""Management inputs. Tariffs, credential names and endpoints are server owned."""
from decimal import Decimal

from django import forms

from .catalog import CATALOG, catalog_choices, preset_for
from .models import AIProfile


class ProfileForm(forms.Form):
    name = forms.CharField(label="Nombre del perfil", max_length=80)
    preset = forms.ChoiceField(label="Proveedor y modalidad", choices=catalog_choices())
    enabled = forms.BooleanField(label="Perfil habilitado", required=False, initial=True)
    max_input_tokens = forms.IntegerField(label="Reserva máxima de entrada por solicitud", min_value=2048, max_value=128000, initial=24000)
    max_output_tokens = forms.IntegerField(label="Máximo de tokens de salida por solicitud", min_value=100, max_value=16000, initial=2500)
    free_tier_confirmed = forms.BooleanField(
        label="Confirmo el uso de esta oferta gratuita y he revisado sus condiciones y límites.",
        required=False,
        help_text="Groq y Gemini requieren una cuenta en su nivel gratuito, sin facturación activada. OpenCode de demostración no requiere clave y su oferta es temporal. SparkX no comprueba tu facturación.",
    )
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput, initial=0)

    def __init__(self, *args, profile=None, preset=None, **kwargs):
        initial = kwargs.setdefault("initial", {})
        if profile:
            initial.update({name: getattr(profile, name) for name in
                            ("name", "enabled", "max_input_tokens", "max_output_tokens", "free_tier_confirmed")})
            initial.update(preset=preset_for(profile), expected_version=profile.version)
        elif preset in CATALOG:
            initial.update(preset=preset, name=CATALOG[preset]["name"])
            if CATALOG[preset]["provider"] == "opencode":
                initial["max_output_tokens"] = 2048
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        preset = CATALOG.get(data.get("preset"))
        if preset and preset["mode"] == "free" and data.get("enabled") and not data.get("free_tier_confirmed"):
            self.add_error("free_tier_confirmed", "Confirma la modalidad gratuita o guarda el perfil deshabilitado.")
        if preset and preset["provider"] == "opencode" and data.get("max_output_tokens", 0) > 2048:
            self.add_error("max_output_tokens", "Esta demostración gratuita admite hasta 2048 tokens de salida.")
        return data


class AccountForm(forms.Form):
    active_profile = forms.ModelChoiceField(label="Perfil para nuevas solicitudes", queryset=AIProfile.objects.none(), required=False, empty_label="IA desactivada")
    monthly_budget_usd = forms.DecimalField(label="Presupuesto mensual bruto · USD", min_value=0, max_value=100000, max_digits=14, decimal_places=6)
    monthly_token_limit = forms.IntegerField(label="Límite mensual de tokens", min_value=0, max_value=100000000)
    paid_enabled = forms.BooleanField(label="Permitir solicitudes a APIs de pago dentro de este presupuesto", required=False)
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, account, **kwargs):
        kwargs.setdefault("initial", {}).update({
            "active_profile": account.active_profile_id, "monthly_budget_usd": account.monthly_budget_usd,
            "monthly_token_limit": account.monthly_token_limit, "paid_enabled": account.paid_enabled,
            "expected_version": account.version,
        })
        super().__init__(*args, **kwargs)
        self.fields["active_profile"].queryset = AIProfile.objects.filter(owner_id=account.owner_id)

    def clean(self):
        data = super().clean()
        if data.get("active_profile") and not data["active_profile"].enabled:
            self.add_error("active_profile", "Elige un perfil habilitado o desactiva la IA.")
        if data.get("paid_enabled") and data.get("monthly_budget_usd", Decimal("0")) <= 0:
            self.add_error("monthly_budget_usd", "Define un presupuesto mayor de cero para permitir APIs de pago.")
        return data


class CalculatorForm(forms.Form):
    preset = forms.ChoiceField(label="Proveedor y modalidad", choices=catalog_choices(), initial="openai_luna")
    input_tokens = forms.IntegerField(label="Tokens de entrada por solicitud", min_value=0, max_value=128000, initial=1000)
    cached_tokens = forms.IntegerField(label="De la entrada, tokens en caché", min_value=0, max_value=128000, initial=0,
                                    help_text="Ya están incluidos en la entrada; no se suman otra vez.")
    output_tokens = forms.IntegerField(label="Tokens de salida por solicitud", min_value=0, max_value=16000, initial=1000,
                                    help_text="Incluye razonamiento cuando el proveedor lo factura como salida.")
    requests = forms.IntegerField(label="Número de solicitudes", min_value=1, max_value=100000, initial=100)
    credits = forms.DecimalField(label="Créditos que declaras para este escenario · USD", min_value=0, max_value=100000, max_digits=12, decimal_places=6, initial=0,
                                help_text="Sólo del proveedor elegido y del periodo estimado. No se consulta ni se modifica tu saldo.")

    def clean(self):
        data = super().clean()
        if data.get("cached_tokens", 0) > data.get("input_tokens", 0):
            self.add_error("cached_tokens", "La caché no puede superar los tokens de entrada.")
        if data.get("input_tokens", 0) + data.get("output_tokens", 0) > 131072:
            self.add_error(None, "El escenario supera los 131 072 tokens admitidos por el prototipo.")
        return data


class ReconciliationForm(forms.Form):
    input_tokens = forms.IntegerField(label="Tokens de entrada comprobados", min_value=0, max_value=2000000000)
    cached_tokens = forms.IntegerField(label="De la entrada, tokens en caché", min_value=0, max_value=2000000000, initial=0)
    output_tokens = forms.IntegerField(label="Tokens de salida comprobados", min_value=0, max_value=2000000000)
    reasoning_tokens = forms.IntegerField(label="De la salida, tokens de razonamiento", min_value=0, max_value=2000000000, initial=0)
    note = forms.CharField(label="Fuente y motivo de la conciliación", max_length=1000, widget=forms.Textarea(attrs={"rows": 4}),
                           help_text="Registra la comprobación en el panel o recibo del proveedor. No pegues claves, documentos ni datos personales.")

    def clean(self):
        data = super().clean()
        if data.get("cached_tokens", 0) > data.get("input_tokens", 0):
            self.add_error("cached_tokens", "La caché está incluida en la entrada.")
        if data.get("reasoning_tokens", 0) > data.get("output_tokens", 0):
            self.add_error("reasoning_tokens", "El razonamiento está incluido en la salida.")
        if data.get("input_tokens", 0) + data.get("output_tokens", 0) > 2_147_483_647:
            self.add_error(None, "El total de tokens excede la capacidad del registro. Revisa los contadores.")
        return data

class UsageFilterForm(forms.Form):
    event = forms.UUIDField(label="Evento", required=False, widget=forms.Select)
    kind = forms.ChoiceField(label="Acción", required=False,
                             choices=[("", "Todas las acciones"), ("plan", "Propuesta de plan"), ("chat", "Consulta al agente")])
    month = forms.CharField(label="Mes contable", required=False, max_length=7,
                            widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
                            help_text="Mes de la reserva en America/Lima. Vacío incluye todo el historial.")

    def __init__(self, *args, owner, **kwargs):
        from apps.events.models import Event
        super().__init__(*args, **kwargs)
        self.fields["event"].widget.choices = [
            ("", "Todos mis eventos"),
            *[(str(pk), title) for pk, title in Event.objects.filter(owner=owner).order_by("title", "id").values_list("pk", "title")],
        ]

    def clean_month(self):
        import re
        from datetime import date
        value = self.cleaned_data["month"]
        if not value:
            return None
        if not re.fullmatch(r"\d{4}-\d{2}", value):
            raise forms.ValidationError("Usa un mes con formato AAAA-MM.")
        year, month = map(int, value.split("-"))
        if not 1900 <= year <= 2100 or not 1 <= month <= 12:
            raise forms.ValidationError("El mes debe estar entre 1900-01 y 2100-12.")
        return date(year, month, 1)


class ComparisonForm(UsageFilterForm):
    source = forms.ChoiceField(label="Origen del escenario", choices=[
        ("manual", "Introducir un escenario"),
        ("history", "Usar el historial de mis eventos"),
    ], initial="manual")
    input_tokens = forms.IntegerField(label="Entrada por solicitud", required=False,
                                      min_value=0, max_value=128000, initial=1000)
    cached_tokens = forms.IntegerField(label="De la entrada, tokens en caché", required=False,
                                       min_value=0, max_value=128000, initial=0,
                                       help_text="Incluidos en la entrada. El comparador aplica sólo las opciones de caché de cada integración.")
    output_tokens = forms.IntegerField(label="Salida por solicitud", required=False,
                                       min_value=0, max_value=16000, initial=1000,
                                       help_text="Incluye el razonamiento facturable.")
    requests = forms.IntegerField(label="Número de solicitudes", required=False,
                                  min_value=1, max_value=100000, initial=100)
    pen_rate = forms.DecimalField(label="Soles por 1 USD", required=False,
                                  min_value=Decimal("0.000001"), max_value=10000,
                                  max_digits=14, decimal_places=6,
                                  help_text="Conversión informativa declarada por ti; no modifica los límites en USD.")
    pen_date = forms.DateField(label="Fecha del tipo de cambio", required=False,
                               widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    pen_source = forms.CharField(label="Fuente del tipo de cambio", required=False, max_length=120,
                                 help_text="Nombre o referencia de tu consulta. SparkX no visita esta dirección ni verifica la tasa.")

    def clean(self):
        from django.utils import timezone
        data = super().clean()
        if data.get("source") == "manual":
            for name in ("input_tokens", "output_tokens", "requests"):
                if name not in self.errors and data.get(name) is None:
                    self.add_error(name, "Completa este dato para comparar el escenario.")
            cached = data.get("cached_tokens") or 0
            data["cached_tokens"] = cached
            if data.get("input_tokens") is not None and cached > data["input_tokens"]:
                self.add_error("cached_tokens", "La caché no puede superar la entrada.")
            if data.get("input_tokens") is not None and data.get("output_tokens") is not None:
                if data["input_tokens"] + data["output_tokens"] > 131072:
                    self.add_error(None, "El escenario admite hasta 131 072 tokens de entrada y salida combinados.")
        conversion = ("pen_rate", "pen_date", "pen_source")
        if any(data.get(name) is not None and data.get(name) != "" for name in conversion):
            for name in conversion:
                if name not in self.errors and not data.get(name):
                    self.add_error(name, "Completa tasa, fecha y fuente para mostrar soles.")
        if data.get("pen_date") and data["pen_date"] > timezone.localdate():
            self.add_error("pen_date", "La fecha del tipo de cambio no puede ser futura.")
        return data
