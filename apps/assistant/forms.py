"""Explicit human review is required; recognized meanings cannot be overwritten."""

from django import forms

from apps.jobs.command_language import validate_pattern_phrase

from .interaction_memory import redact_secrets
from .models import CommandPattern, InteractionRecord


class CommandPatternForm(forms.ModelForm):
    phrase = forms.CharField(
        label="Frase revisada",
        max_length=300,
        strip=False,
        widget=forms.TextInput(attrs={"maxlength": 300, "autocomplete": "off"}),
    )
    intent = forms.ChoiceField(
        label="Intención",
        choices=CommandPattern.Intent.choices,
        error_messages={"invalid_choice": "Selecciona una de las seis intenciones permitidas."},
    )
    reviewed = forms.BooleanField(label="Revisé esta frase y confirmo su intención.", required=True)

    class Meta:
        model = CommandPattern
        fields = ("phrase", "intent", "reviewed")

    def clean_reviewed(self):
        if self.data.get("reviewed") not in {"on", "true", "1", True}:
            raise forms.ValidationError("Marca la confirmación explícita de revisión.")
        return self.cleaned_data["reviewed"]

    def clean(self):
        data = super().clean()
        if "phrase" in data and "intent" in data:
            try:
                data["normalized_phrase"] = validate_pattern_phrase(data["phrase"], data["intent"])
            except ValueError as error:
                field = "intent" if str(error) == "intent_conflict" else "phrase"
                self.add_error(
                    field,
                    "La intención no puede cambiar una orden ya reconocida."
                    if field == "intent"
                    else (
                        "Usa una frase segura y directa, sin controles de voz, negaciones, "
                        "citas ni varias acciones."
                    ),
                )
        return data


class InteractionReviewForm(forms.Form):
    review_status = forms.ChoiceField(
        label="Revisión humana",
        choices=[
            (InteractionRecord.Review.GOOD, "Correcta"),
            (InteractionRecord.Review.NEEDS_CHANGE, "Necesita mejora"),
            (InteractionRecord.Review.IGNORE, "Ignorar"),
        ],
    )
    review_note = forms.CharField(
        label="Nota para el mentor", max_length=1000, required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    suggested_intent = forms.ChoiceField(
        label="Intención sugerida, sin activarla",
        choices=[("", "Sin sugerencia"), *CommandPattern.Intent.choices], required=False,
    )

    def clean_review_note(self):
        return redact_secrets(self.cleaned_data["review_note"])[:1000]


class InteractionFilterForm(forms.Form):
    q = forms.CharField(label="Buscar texto", max_length=300, required=False)
    phase = forms.ChoiceField(
        label="Fase", choices=[("", "Todas"), *InteractionRecord.Phase.choices], required=False,
    )
    status = forms.ChoiceField(
        label="Estado declarado",
        choices=[("", "Todos"), *InteractionRecord.Status.choices], required=False,
    )
    review = forms.ChoiceField(
        label="Revisión", choices=[("", "Todas"), *InteractionRecord.Review.choices], required=False,
    )


class InteractionDeleteForm(forms.Form):
    confirm = forms.BooleanField(label="Confirmo la eliminación de mis registros.")

    def clean_confirm(self):
        if self.data.get("confirm") not in {"on", "true", "1", True}:
            raise forms.ValidationError("Marca la confirmación explícita de eliminación.")
        return self.cleaned_data["confirm"]
