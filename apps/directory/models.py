"""Private contact records, independent from login accounts and approved plans."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .normalization import normalize_aliases, search_key


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    name_key = models.CharField(max_length=320, editable=False, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    alias_keys = models.TextField(blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    is_synthetic = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name_key", "id")
        constraints = [
            models.UniqueConstraint(fields=("owner", "name_key"), condition=models.Q(archived_at__isnull=True), name="directory_org_owner_name"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="directory_org_positive_version"),
        ]

    def clean(self):
        super().clean()
        self.name = " ".join(self.name.split())
        self.name_key = search_key(self.name)
        self.aliases, self.alias_keys = normalize_aliases(self.aliases)
        if not self.name_key:
            raise ValidationError({"name": "Escribe el nombre de la empresa o institución."})
        if len(self.name_key) > self._meta.get_field("name_key").max_length:
            raise ValidationError({"name": "El nombre normalizado es demasiado largo para la búsqueda."})

    def __str__(self):
        return self.name


class Person(models.Model):
    class Category(models.TextChoices):
        SPEAKER = "speaker", "Expositor"
        PARTICIPANT = "participant", "Participante"
        GUEST = "guest", "Invitado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    full_name = models.CharField(max_length=160)
    name_key = models.CharField(max_length=320, editable=False, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    alias_keys = models.TextField(blank=True, editable=False)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.PARTICIPANT)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, null=True, blank=True, related_name="people")
    email = models.EmailField(max_length=254, blank=True)
    email_key = models.CharField(max_length=254, editable=False, blank=True)
    expertise = models.CharField(max_length=600, blank=True)
    is_active = models.BooleanField(default=True)
    is_synthetic = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name_key", "id")
        constraints = [
            models.UniqueConstraint(fields=("owner", "email_key"), condition=~models.Q(email_key="") & models.Q(archived_at__isnull=True), name="directory_person_owner_email"),
            models.CheckConstraint(condition=models.Q(category__in=["speaker", "participant", "guest"]), name="directory_person_category"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="directory_person_positive_version"),
        ]
        indexes = [models.Index(fields=("owner", "category", "is_active"), name="directory_person_scope")]

    def clean(self):
        super().clean()
        self.full_name = " ".join(self.full_name.split())
        self.name_key = search_key(self.full_name)
        self.aliases, self.alias_keys = normalize_aliases(self.aliases)
        self.email = self.email.strip()
        self.email_key = self.email.casefold()
        self.expertise = self.expertise.strip()
        if not self.name_key:
            raise ValidationError({"full_name": "Escribe el nombre de la persona."})
        if len(self.name_key) > self._meta.get_field("name_key").max_length:
            raise ValidationError({"full_name": "El nombre normalizado es demasiado largo para la búsqueda."})
        if len(self.email_key) > self._meta.get_field("email_key").max_length:
            raise ValidationError({"email": "El correo normalizado es demasiado largo."})
        if self.organization_id and self.organization.owner_id != self.owner_id:
            raise ValidationError({"organization": "La institución no pertenece a tu directorio."})
        if self.organization_id and self.archived_at is None and self.organization.archived_at is not None:
            raise ValidationError({"organization": "La institución fue retirada del directorio."})

    def __str__(self):
        return self.full_name


class EventPerson(models.Model):
    Role = Person.Category

    class Status(models.TextChoices):
        PLANNED = "planned", "Por confirmar"
        CONFIRMED = "confirmed", "Confirmado por el organizador"
        CANCELLED = "cancelled", "Cancelado"

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="directory_people")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="event_links")
    role = models.CharField(max_length=16, choices=Person.Category.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("role", "person__name_key", "id")
        constraints = [
            models.UniqueConstraint(fields=("event", "person", "role"), name="directory_event_person_role"),
            models.CheckConstraint(condition=models.Q(role__in=["speaker", "participant", "guest"]), name="directory_event_person_kind"),
            models.CheckConstraint(condition=models.Q(status__in=["planned", "confirmed", "cancelled"]), name="directory_event_person_status"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="directory_link_positive_version"),
        ]

    def clean(self):
        super().clean()
        if self.event_id and self.person_id and self.event.owner_id != self.person.owner_id:
            raise ValidationError("La persona y el evento deben pertenecer al mismo organizador.")


class DirectoryAudit(models.Model):
    """Metadata only: no copies of email, name, notes or before/after values."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="directory_changes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="directory_actions")
    entity_type = models.CharField(max_length=24)
    entity_id = models.CharField(max_length=64)
    action = models.CharField(max_length=16)
    changed_fields = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
