"""HTTP input validation; browser-local times use the event's selected zone."""

from datetime import date, datetime
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from django import forms
from django.utils import timezone as django_timezone
from apps.directory.models import EventPerson, Organization, Person

from .interview import MAX_ANSWER_LENGTH, QUESTIONS, STATUS_CHOICES, normalize_interview_answers


class EventForm(forms.Form):
    title = forms.CharField(max_length=200, label="Nombre del evento", widget=forms.TextInput(attrs={"placeholder": "Ej. Seminario de innovación académica", "autocomplete": "off"}))
    brief = forms.CharField(min_length=3, max_length=12000, label="Descripción y objetivos", widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Objetivos, público, formato y restricciones conocidas"}))
    starts_at = forms.CharField(required=False, label="Fecha y hora de inicio", widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}))
    scheduled_dates = forms.CharField(required=False, max_length=6000, label="Fechas del evento",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "05/09/2026, 06/09/2026, 07/09/2026"}),
        help_text="Una o varias fechas DD/MM/AAAA, separadas por coma. La hora de inicio se configura debajo.")
    timezone = forms.ChoiceField(initial="America/Lima", label="Zona horaria", choices=[(zone, zone) for zone in sorted(available_timezones())])
    capacity = forms.IntegerField(min_value=1, max_value=100000, initial=100, label="Capacidad prevista")
    organization_id = forms.ModelChoiceField(queryset=Organization.objects.none(), required=False,
        label="Empresa o institución organizadora", empty_label="Sin institución asignada")
    speaker_id = forms.ModelChoiceField(queryset=Person.objects.none(), required=False,
        label="Expositor", empty_label="Expositor por confirmar")
    is_synthetic = forms.BooleanField(required=False, label="Evento de demostración con datos ficticios")
    objective = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Objetivo",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Qué podrán hacer los participantes al terminar"}))
    audience = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Perfil del público",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "A quién está dirigido y qué experiencia necesita"}))
    modality = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Modalidad",
        widget=forms.Select(choices=[("", "Por definir"), ("Virtual", "Virtual"), ("Presencial", "Presencial"), ("Híbrida", "Híbrida")]))
    duration_minutes = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Duración total · minutos",
        widget=forms.TextInput(attrs={"type": "number", "min": "1", "max": "1440", "step": "1", "placeholder": "Ej. 90"}))
    location = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Lugar o acceso",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Plataforma, lugar o enlace. Indica lo pendiente."}))
    resources = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Recursos y equipo",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Personas, materiales y recursos disponibles o por confirmar"}))
    constraints = forms.CharField(required=False, max_length=MAX_ANSWER_LENGTH, label="Condiciones y restricciones",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Horario, presupuesto, accesibilidad u otros límites"}))

    def __init__(self, *args, instance=None, actor=None, **kwargs):
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = {"title": instance.title, "brief": instance.brief, "timezone": instance.timezone, "capacity": instance.capacity}
            kwargs["initial"].update(organization_id=instance.organization_id, is_synthetic=instance.is_synthetic,
                                     scheduled_dates=", ".join(date.fromisoformat(day).strftime("%d/%m/%Y") for day in instance.scheduled_dates))
            kwargs["initial"].update({key: answer["value"] for key, answer in normalize_interview_answers(instance.interview_answers).items()})
            kwargs["initial"]["speaker_id"] = instance.directory_people.filter(
                role=Person.Category.SPEAKER, status__in=[EventPerson.Status.PLANNED, EventPerson.Status.CONFIRMED]
            ).order_by("id").values_list("person_id", flat=True).first()
            if instance.starts_at:
                kwargs["initial"]["starts_at"] = instance.starts_at.astimezone(ZoneInfo(instance.timezone)).strftime("%Y-%m-%dT%H:%M")
        super().__init__(*args, **kwargs)
        self.event_instance = instance
        if actor is not None:
            from apps.directory.queries import organizations_for, people_for
            self.fields["organization_id"].queryset = organizations_for(actor).filter(is_active=True)
            self.fields["speaker_id"].queryset = people_for(actor).filter(is_active=True, category=Person.Category.SPEAKER)
        selected_modality = self.initial.get("modality", "")
        if selected_modality and selected_modality not in {value for value, _ in self.fields["modality"].widget.choices}:
            self.fields["modality"].widget.choices = [*self.fields["modality"].widget.choices, (selected_modality, selected_modality)]

    def clean_organization_id(self):
        organization = self.cleaned_data.get("organization_id")
        return organization.pk if organization else None

    def clean_speaker_id(self):
        person = self.cleaned_data.get("speaker_id")
        return person.pk if person else None

    def _clean_preparation(self, cleaned):
        # Old clients may omit the newer inputs. Omission is not a command to
        # clear an existing declaration or a directory assignment.
        previous = normalize_interview_answers(self.event_instance.interview_answers) if self.event_instance else {}
        answers = dict(previous)
        submitted = False
        for question in QUESTIONS:
            key = question.key
            value = cleaned.pop(key, None)
            if key not in self.data or key in self.errors or value is None:
                continue
            submitted = True
            old = previous.get(key)
            answer = old if old and old["value"] == value else {"status": "confirmed" if value else "pending", "value": value}
            try:
                answers[key] = normalize_interview_answers({key: answer})[key]
            except ValueError as error:
                self.add_error(key, str(error))
        if submitted:
            cleaned["interview_answers"] = answers
        if "speaker_id" not in self.data:
            cleaned.pop("speaker_id", None)

    def clean_scheduled_dates(self):
        from .schedule_dates import normalize_scheduled_dates
        raw = self.cleaned_data.get("scheduled_dates")
        if not raw:
            raw = []
        elif raw.startswith("["):
            try:
                raw = json.loads(raw)
            except ValueError as error:
                raise forms.ValidationError("Revisa la lista de fechas del evento.") from error
        else:
            try:
                raw = [datetime.strptime(item.strip(), "%d/%m/%Y").date().isoformat()
                       if "/" in item else date.fromisoformat(item.strip()).isoformat()
                       for item in raw.split(",")]
            except ValueError as error:
                raise forms.ValidationError("Indica fechas válidas DD/MM/AAAA separadas por coma.") from error
        # Unchanged historical dates remain editable after a new calendar year.
        try:
            canonical = normalize_scheduled_dates(raw)
            unchanged = self.event_instance is not None and canonical == self.event_instance.scheduled_dates
            return normalize_scheduled_dates(canonical, reference_year=None if unchanged else django_timezone.localdate().year)
        except ValueError as error:
            raise forms.ValidationError(str(error)) from error

    def clean(self):
        cleaned = super().clean()
        self._clean_preparation(cleaned)
        raw = cleaned.get("starts_at")
        dates = cleaned.get("scheduled_dates", [])
        selected_zone = cleaned.get("timezone")
        if not raw:
            cleaned["starts_at"] = None
            return cleaned
        if not selected_zone:
            return cleaned
        try:
            zone = ZoneInfo(selected_zone)
            if "T" not in raw:
                raise ValueError
            local = datetime.fromisoformat(raw)
            if local.tzinfo is not None:
                raise ValueError
            first = local.replace(tzinfo=zone, fold=0)
            second = local.replace(tzinfo=zone, fold=1)
            if first.utcoffset() != second.utcoffset():
                self.add_error("starts_at", "Esta hora es ambigua o no existe por un cambio horario. Selecciona otra hora.")
            else:
                cleaned["starts_at"] = first
                unchanged_start = self.event_instance is not None and self.event_instance.starts_at == first
                if not unchanged_start and not django_timezone.localdate().year <= local.year <= 2099:
                    self.add_error("starts_at", "Indica un año de cuatro cifras igual o posterior al actual, hasta 2099.")
                if dates and local.date().isoformat() != dates[0]:
                    self.add_error("starts_at", "El inicio debe corresponder al primer día seleccionado.")
        except (ValueError, TypeError, ZoneInfoNotFoundError):
            self.add_error("starts_at", "Escribe una fecha y hora local válida y selecciona su zona horaria.")
        return cleaned


class EventEditForm(EventForm):
    expected_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, instance, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        self.initial["expected_revision"] = instance.revision


class InterviewForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    question_key = forms.ChoiceField(choices=(), widget=forms.HiddenInput)
    status = forms.ChoiceField(label="Cómo debemos usar este dato", choices=())
    value = forms.CharField(label="Tu respuesta", required=False, max_length=MAX_ANSWER_LENGTH,
                           widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, instance, question, **kwargs):
        answer = instance.interview_answers.get(question.key, {"status": "pending", "value": ""})
        kwargs.setdefault("initial", {"expected_revision": instance.revision, "question_key": question.key,
                                      "status": answer["status"], "value": answer["value"]})
        super().__init__(*args, **kwargs)
        self.question = question
        self.fields["question_key"].choices = [(question.key, question.label)]
        self.fields["status"].choices = [
            (key, label) for key, label in STATUS_CHOICES
            if (key != "not_applicable" or question.key in {"location", "resources", "constraints"})
            and (key != "in_brief" or question.key != "duration_minutes")
        ]
        self.fields["value"].help_text = (
            "Indica los minutos totales (1 a 1440). Puedes dejarlo pendiente."
            if question.key == "duration_minutes" else
            "Para «Ya está en la ficha» o «No aplica», deja la respuesta vacía."
        )
        if question.key == "duration_minutes":
            self.fields["value"].widget = forms.TextInput(attrs={"inputmode": "numeric", "maxlength": MAX_ANSWER_LENGTH})

    def clean(self):
        cleaned = super().clean()
        if "status" not in cleaned or "value" not in cleaned:
            return cleaned
        try:
            answer = normalize_interview_answers({self.question.key: {
                "status": cleaned["status"], "value": cleaned["value"],
            }})[self.question.key]
        except ValueError as exc:
            self.add_error("value", str(exc))
        else:
            cleaned.update(answer)
        return cleaned


class AIRequestForm(forms.Form):
    brief = forms.CharField(required=False, max_length=6000, strip=True)
    idempotency_key = forms.UUIDField()
    expected_revision = forms.IntegerField(min_value=1, required=False)
    accept_model_policy = forms.BooleanField(required=False)
    model_policy_token = forms.CharField(required=False, max_length=4096)


class ChatForm(forms.Form):
    message = forms.CharField(min_length=3, max_length=4000, strip=True)
    idempotency_key = forms.UUIDField()
    accept_model_policy = forms.BooleanField(required=False)
    model_policy_token = forms.CharField(required=False, max_length=4096)


class TaskStatusForm(forms.Form):
    """Explicit manual command; actor and timestamps are never browser inputs."""

    expected_plan = forms.UUIDField(widget=forms.HiddenInput)
    task_id = forms.CharField(max_length=64, widget=forms.HiddenInput)
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    status = forms.ChoiceField(label="Estado", choices=[
        ("not_started", "No iniciado"),
        ("in_progress", "En proceso"),
        ("completed", "Completado"),
    ])
    note = forms.CharField(
        label="Nota de seguimiento", required=False, max_length=1000,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Qué se hizo o por qué cambia el estado…"}),
        help_text="Obligatoria al completar o reabrir una tarea.",
    )
