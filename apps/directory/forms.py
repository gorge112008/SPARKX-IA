"""Directory input forms; identities and ownership come from the server."""

from django import forms
from django.db.models import Q

from .models import EventPerson, Organization, Person
from .queries import organizations_for, people_for
from .normalization import normalize_aliases


class AliasForm(forms.Form):
    aliases = forms.CharField(label="Siglas o nombres alternativos", required=False, max_length=1940,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Un alias por línea; hasta 12. Por ejemplo: UNAC o Robert Castillo Alva.")

    def clean_aliases(self):
        values = [line.strip() for line in self.cleaned_data["aliases"].splitlines() if line.strip()]
        return normalize_aliases(values)[0]


class DirectoryFilterForm(forms.Form):
    q = forms.CharField(label="Buscar", max_length=200, required=False,
                        widget=forms.SearchInput(attrs={"placeholder": "Nombre de persona u organización"}))
    category = forms.ChoiceField(label="Categoría", required=False,
                                 choices=[("", "Todas las categorías"), *Person.Category.choices])
    organization = forms.ModelChoiceField(label="Empresa u organización", required=False,
                                          queryset=Organization.objects.none(), empty_label="Todas las organizaciones")
    include_inactive = forms.BooleanField(label="Incluir archivados", required=False)

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = organizations_for(actor).order_by("name", "pk")


class OrganizationForm(AliasForm):
    field_order = ["name", "aliases", "is_active", "is_synthetic", "expected_version"]
    name = forms.CharField(label="Nombre de la empresa u organización", max_length=160)
    is_active = forms.BooleanField(label="Organización activa", required=False, initial=True,
                                    help_text="Desmarca para archivar. Se conserva su historial y sus vínculos.")
    is_synthetic = forms.BooleanField(label="Dato sintético de demostración", required=False,
                                       help_text="Marca esta opción si es un ejemplo y no una organización real.")
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None:
            kwargs.setdefault("initial", {"name": instance.name, "aliases": "\n".join(instance.aliases), "is_active": instance.is_active,
                                          "is_synthetic": instance.is_synthetic,
                                          "expected_version": instance.version})
        super().__init__(*args, **kwargs)
        if instance is None:
            self.fields.pop("expected_version")


class PersonForm(AliasForm):
    field_order = ["full_name", "aliases", "category", "email", "expertise", "organization", "is_active", "is_synthetic", "expected_version"]
    full_name = forms.CharField(label="Nombre completo", max_length=160)
    category = forms.ChoiceField(label="Categoría", choices=Person.Category.choices)
    email = forms.EmailField(label="Correo de contacto", max_length=254, required=False)
    expertise = forms.CharField(label="Especialidad o experiencia", max_length=600, required=False,
                                 widget=forms.Textarea(attrs={"rows": 3}))
    organization = forms.ModelChoiceField(label="Empresa u organización", required=False,
                                          queryset=Organization.objects.none(), empty_label="Sin organización")
    is_active = forms.BooleanField(label="Persona activa", required=False, initial=True,
                                    help_text="Desmarca para archivar. Se conservan sus participaciones anteriores.")
    is_synthetic = forms.BooleanField(label="Dato sintético de demostración", required=False,
                                       help_text="Marca esta opción si es un ejemplo y no una persona real.")
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, actor, instance=None, **kwargs):
        if instance is not None:
            kwargs.setdefault("initial", {"full_name": instance.full_name, "aliases": "\n".join(instance.aliases), "category": instance.category,
                                          "email": instance.email, "expertise": instance.expertise,
                                          "organization": instance.organization_id, "is_active": instance.is_active,
                                          "is_synthetic": instance.is_synthetic,
                                          "expected_version": instance.version})
        super().__init__(*args, **kwargs)
        available = Q(is_active=True)
        if instance is not None and instance.organization_id:
            available |= Q(pk=instance.organization_id)
        self.fields["organization"].queryset = organizations_for(actor).filter(available).order_by("name", "pk")
        if instance is None:
            self.fields.pop("expected_version")


class EventPersonForm(forms.Form):
    person = forms.ModelChoiceField(label="Persona del directorio", queryset=Person.objects.none(),
                                    empty_label="Selecciona una persona")
    role = forms.ChoiceField(label="Rol en este evento", choices=EventPerson.Role.choices)
    status = forms.ChoiceField(label="Estado de participación", choices=EventPerson.Status.choices)
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, actor, assignment=None, people_queryset=None, **kwargs):
        kwargs.setdefault("initial", {"person": assignment.person_id if assignment else None,
                                      "role": assignment.role if assignment else Person.Category.PARTICIPANT,
                                      "status": assignment.status if assignment else EventPerson.Status.PLANNED,
                                      "expected_version": assignment.version if assignment else 0})
        super().__init__(*args, **kwargs)
        available = Q(is_active=True)
        if assignment is not None:
            available |= Q(pk=assignment.person_id)
            self.fields["person"].widget = forms.HiddenInput()
            self.fields["role"].widget = forms.HiddenInput()
            self.fields["role"].choices = [(assignment.role, assignment.get_role_display())]
        authorized = people_queryset if people_queryset is not None else people_for(actor)
        self.fields["person"].queryset = authorized.filter(available).order_by("full_name", "pk")
