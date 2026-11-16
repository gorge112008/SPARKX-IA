from django import forms
from django.core.exceptions import ValidationError

from .models import RegistrationPage
from .normalization import registration_values


class PublicationForm(forms.Form):
    action = forms.ChoiceField(choices=RegistrationPage.State.choices, widget=forms.HiddenInput)
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    expected_plan = forms.UUIDField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(label="Confirmo esta acción sobre las inscripciones")


class RegistrationForm(forms.Form):
    full_name = forms.CharField(label="Nombre completo", max_length=120,
                               widget=forms.TextInput(attrs={"autocomplete": "name"}))
    email = forms.EmailField(label="Correo electrónico", max_length=254,
                            widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    form_token = forms.CharField(max_length=400, widget=forms.HiddenInput)

    def clean(self):
        values = super().clean()
        if "full_name" in values and "email" in values:
            try:
                values["full_name"], values["email"] = registration_values(values["full_name"], values["email"])
            except ValidationError as error:
                if hasattr(error, "message_dict"):
                    for field, messages in error.message_dict.items():
                        self.add_error(field, messages)
                else:
                    self.add_error(None, error)
        return values
