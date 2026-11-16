from django import forms

from .models import ChecklistProgress


class ProgressForm(forms.Form):
    status = forms.ChoiceField(label="Estado", choices=ChecklistProgress.Status.choices)
    expected_version = forms.IntegerField(min_value=0, max_value=2147483647, widget=forms.HiddenInput)
    confirmations = forms.MultipleChoiceField(
        label="Confirmaciones personales", required=False, widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, item, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item
        self.fields["confirmations"].choices = [(check.key, check.label) for check in item.confirmations]
        if not item.optional:
            self.fields["status"].choices = [choice for choice in ChecklistProgress.Status.choices if choice[0] != ChecklistProgress.Status.NOT_APPLICABLE]
        self.fields["status"].widget.attrs.update({"aria-label": "Estado de " + item.title})

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            allowed = {"status", "expected_version", "confirmations", "csrfmiddlewaretoken"}
            if set(self.data) - allowed:
                raise forms.ValidationError("Sólo se admiten estado, versión y casillas de confirmación. No envíes claves, notas ni otros datos.")
            if any(len(self.data.getlist(key)) != 1 for key in ("status", "expected_version") if hasattr(self.data, "getlist") and key in self.data):
                raise forms.ValidationError("Cada campo debe enviarse una sola vez.")
        checks = cleaned.get("confirmations", [])
        if len(checks) != len(set(checks)):
            self.add_error("confirmations", "Cada confirmación debe enviarse una sola vez.")
        required = {check.key for check in self.item.confirmations}
        if cleaned.get("status") == ChecklistProgress.Status.COMPLETED and set(checks) != required:
            self.add_error("confirmations", "Revisa y marca todas las confirmaciones antes de completar este punto.")
        return cleaned
