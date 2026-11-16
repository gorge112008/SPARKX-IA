"""Only two enumerated presentation preferences are editable."""

from django import forms

from .models import GicaProfile


class GicaProfileForm(forms.Form):
    personality = forms.ChoiceField(label="Cómo te acompaña", choices=GicaProfile.Personality.choices,
                                    widget=forms.RadioSelect)
    appearance = forms.ChoiceField(label="Su apariencia", choices=GicaProfile.Appearance.choices,
                                   widget=forms.RadioSelect)

