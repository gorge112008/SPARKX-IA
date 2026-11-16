from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from .models import PortalAccount


class PortalAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Correo o usuario", max_length=254,
                               widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}))
    error_messages = {**AuthenticationForm.error_messages,
                      "invalid_login": "No pudimos iniciar sesión. Revisa tu correo o usuario y contraseña.",
                      "inactive": "No pudimos iniciar sesión. Revisa tu correo o usuario y contraseña."}


class CreateAccountForm(forms.Form):
    full_name = forms.CharField(label="Nombre", max_length=150)
    email = forms.EmailField(label="Correo de acceso", max_length=150)
    role = forms.ChoiceField(label="Rol", choices=PortalAccount.Role.choices, initial=PortalAccount.Role.ORGANIZER)
    password = forms.CharField(label="Contraseña inicial", min_length=16, max_length=128, strip=False,
                               widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))


class UpdateAccountForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=[("role", "Rol"), ("status", "Estado")])
    role = forms.ChoiceField(choices=PortalAccount.Role.choices, required=False)
    is_active = forms.ChoiceField(choices=[("1", "Activo"), ("0", "Inactivo")], required=False)

    def clean(self):
        cleaned = super().clean()
        field = "role" if cleaned.get("action") == "role" else "is_active"
        if not cleaned.get(field):
            self.add_error(field, "Selecciona un valor válido.")
        return cleaned


class ReviewersForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reviewers = forms.ModelMultipleChoiceField(
        label="Revisores con acceso", required=False, queryset=get_user_model().objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, event, **kwargs):
        from django.db.models import F
        initial = {"expected_version": event.review_access_version, "reviewers": list(
            event.review_assignments.filter(
                reviewer__is_active=True, reviewer__portal_account__role=PortalAccount.Role.REVIEWER,
                reviewer_version=F("reviewer__portal_account__access_version"),
            ).values_list("reviewer_id", flat=True)
        )}
        kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)
        self.fields["reviewers"].queryset = get_user_model().objects.filter(
            is_active=True, is_staff=False, is_superuser=False, portal_account__role=PortalAccount.Role.REVIEWER,
        ).order_by("first_name", "username")
        self.fields["reviewers"].label_from_instance = lambda user: user.get_full_name() or user.username


class PortalPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].max_length = 128
        self.fields["new_password2"].max_length = 128
