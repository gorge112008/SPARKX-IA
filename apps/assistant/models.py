import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.conf import settings


class CompactPlanRequest(models.Model):
    """Private, versioned compact exchange; identity mapping never leaves the server."""
    job = models.OneToOneField("jobs.Job", on_delete=models.CASCADE, related_name="compact_request")
    parent = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="continuation")
    run_id = models.UUIDField()
    version = models.PositiveSmallIntegerField(default=1, editable=False)
    round_number = models.PositiveSmallIntegerField(default=1)
    review_only = models.BooleanField(default=False)
    context = models.JSONField()
    local_mapping = models.JSONField()
    response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(version=1, round_number__in=[1, 2]), name="compact_v1_two_rounds")]


class CompactRequestCancellation(models.Model):
    """A durable Stop receipt also fences a not-yet-committed enqueue."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    run_id = models.UUIDField()
    request_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "actor", "run_id", "request_key"], name="compact_cancel_once")]


class GicaProfile(models.Model):
    """Owner-private presentation preferences, never execution instructions."""

    class Personality(models.TextChoices):
        FRIENDLY = "friendly", "Cercano y claro"
        PROFESSIONAL = "professional", "Profesional"
        DIRECT = "direct", "Directo"

    class Appearance(models.TextChoices):
        OCEAN = "ocean", "Azul océano"
        SLATE = "slate", "Grafito"
        FOREST = "forest", "Verde bosque"

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gica_profile"
    )
    personality = models.CharField(max_length=16, choices=Personality.choices, default=Personality.FRIENDLY)
    appearance = models.CharField(max_length=12, choices=Appearance.choices, default=Appearance.OCEAN)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(personality__in=["friendly", "professional", "direct"]),
                                   name="gica_profile_known_personality"),
            models.CheckConstraint(condition=models.Q(appearance__in=["ocean", "slate", "forest"]),
                                   name="gica_profile_known_appearance"),
        ]


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Organizador"
        ASSISTANT = "assistant", "Agente"

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField(max_length=20000)
    # The response belongs to one job. User requests use a separate deduplication key.
    job = models.OneToOneField(
        "jobs.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="message"
    )
    request_key = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["event", "role", "request_key"], name="message_request_once"
            ),
            models.CheckConstraint(
                condition=models.Q(job__isnull=True) | models.Q(role="assistant"),
                name="message_job_is_response",
            ),
        ]


class CommandPattern(models.Model):
    """Only a human-reviewed phrase/meaning pair; no audio or conversation log."""

    class Intent(models.TextChoices):
        THEME_LIGHT = "theme_light", "Modo claro"
        THEME_DARK = "theme_dark", "Modo oscuro"
        CALENDAR_OPEN = "calendar_open", "Abrir calendario"
        DIRECTORY_OPEN = "directory_open", "Abrir directorio"
        PEOPLE_SEARCH = "people_search", "Buscar una persona"
        EVENTS_OPEN = "events_open", "Abrir eventos"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="command_patterns"
    )
    phrase = models.CharField(max_length=300)
    normalized_phrase = models.CharField(max_length=300, editable=False)
    intent = models.CharField(max_length=16, choices=Intent.choices)
    reviewed_at = models.DateTimeField()

    class Meta:
        ordering = ("-reviewed_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "normalized_phrase"], name="command_pattern_owner_phrase"
            ),
            models.CheckConstraint(
                condition=models.Q(intent__in=[
                    "theme_light", "theme_dark", "calendar_open", "directory_open", "people_search",
                    "events_open",
                ]),
                name="command_pattern_six_intents",
            ),
        ]


class InteractionRecord(models.Model):
    """Owner-private text declared by a client, never authority or training data."""

    class Phase(models.TextChoices):
        REQUEST = "request", "Petición"
        CONFIRMATION = "confirmation", "Confirmación"
        SYSTEM = "system", "Sistema"
        ACTION = "action", "Resultado de acción"

    class Status(models.TextChoices):
        READY = "ready", "Orden preparada"
        CLARIFY = "clarify", "Necesita aclaración"
        REFUSED = "refused", "Rechazada"
        INFO = "info", "Información"
        CONFIRMED = "confirmed", "Confirmación positiva"
        AMBIGUOUS = "ambiguous", "Confirmación ambigua"
        CANCELLED = "cancelled", "Cancelada"
        COMPLETED = "completed", "Completada por el cliente"
        FAILED = "failed", "Fallida"
        STOPPED = "stopped", "Detenida"
        UNKNOWN = "unknown", "No reconocida"

    class Outcome(models.TextChoices):
        NONE = "none", "Sin acción"
        CONFIRMED = "confirmed", "Confirmada por el cliente"
        COMPLETED = "completed", "Completada por el cliente"
        CANCELLED = "cancelled", "Cancelada"
        FAILED = "failed", "Fallida"
        ALREADY = "already", "Ya estaba aplicado"
        ARRIVED = "arrived", "Llegada declarada"
        UNRECORDED = "unrecorded", "Sin confirmación de registro"
        STOPPED = "stopped", "Detenida"

    class Source(models.TextChoices):
        VOICE = "voice", "Voz transcrita"
        TEXT = "text", "Texto"

    class TimingBasis(models.TextChoices):
        NONE = "", "No declarada"
        SPEECH_END = "speech_end", "Fin de voz observado por navegador"
        ESTIMATED = "estimated", "Estimación del navegador"
        TEXT = "text", "Entrada escrita"

    class Review(models.TextChoices):
        UNREVIEWED = "unreviewed", "Sin revisar"
        GOOD = "good", "Correcta"
        NEEDS_CHANGE = "needs_change", "Necesita mejora"
        IGNORE = "ignore", "Ignorar"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interaction_records"
    )
    request_id = models.UUIDField()
    session_id = models.UUIDField()
    sequence = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    original_text = models.CharField(max_length=300, blank=True)
    normalized_text = models.CharField(max_length=300, blank=True)
    reply = models.CharField(max_length=500, blank=True)
    draft = models.CharField(max_length=300, blank=True)
    source = models.CharField(max_length=8, choices=Source.choices)
    phase = models.CharField(max_length=16, choices=Phase.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    intent = models.CharField(max_length=16, choices=CommandPattern.Intent.choices, blank=True)
    action = models.ForeignKey(
        "jobs.UIAction", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="interaction_records",
    )
    outcome = models.CharField(max_length=16, choices=Outcome.choices, blank=True)
    timings = models.JSONField(default=dict, blank=True)
    timing_basis = models.CharField(max_length=16, choices=TimingBasis.choices, blank=True)
    consent_version = models.PositiveSmallIntegerField(default=3, editable=False)
    payload_hash = models.CharField(max_length=64, editable=False)
    received_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(
        max_length=16, choices=Review.choices, default=Review.UNREVIEWED
    )
    review_note = models.CharField(max_length=1000, blank=True)
    suggested_intent = models.CharField(
        max_length=16, choices=CommandPattern.Intent.choices, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-received_at", "id")
        indexes = [models.Index(fields=["owner", "received_at"], name="interaction_owner_time")]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "request_id"], name="interaction_owner_request"
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gte=1, sequence__lte=10000),
                name="interaction_sequence_bounds",
            ),
            models.CheckConstraint(
                condition=models.Q(phase__in=["request", "confirmation", "system", "action"]),
                name="interaction_known_phase",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=[
                    "ready", "clarify", "refused", "info", "confirmed", "ambiguous",
                    "cancelled", "completed", "failed", "stopped", "unknown",
                ]),
                name="interaction_known_status",
            ),
            models.CheckConstraint(
                condition=models.Q(review_status__in=[
                    "unreviewed", "good", "needs_change", "ignore",
                ]),
                name="interaction_known_review",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=["voice", "text"]),
                name="interaction_known_source",
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=[
                    "none", "confirmed", "cancelled", "failed", "completed", "already",
                    "arrived", "unrecorded", "stopped",
                ]),
                name="interaction_known_outcome",
            ),
            models.CheckConstraint(
                condition=models.Q(intent__in=["", *CommandPattern.Intent.values]),
                name="interaction_known_intent",
            ),
            models.CheckConstraint(
                condition=models.Q(suggested_intent__in=["", *CommandPattern.Intent.values]),
                name="interaction_suggested_intent",
            ),
            models.CheckConstraint(
                condition=models.Q(consent_version=3), name="interaction_consent_v3",
            ),
        ]


class KnowledgeEntry(models.Model):
    """Private cached external text, never instructions or execution authority."""

    class Status(models.TextChoices):
        AUTO = "auto", "Incorporado automáticamente"
        REVIEWED = "reviewed", "Revisado manualmente"
        DISABLED = "disabled", "Desactivado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="knowledge_entries"
    )
    question = models.CharField(max_length=300)
    normalized_key = models.CharField(max_length=300, editable=False)
    answer = models.TextField(max_length=1800)
    sources = models.JSONField(default=list)
    keywords = models.JSONField(default=list, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AUTO)
    fetched_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "normalized_key"], name="knowledge_owner_key"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["auto", "reviewed", "disabled"]),
                name="knowledge_known_status",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gte=models.F("fetched_at")),
                name="knowledge_expiry_after_fetch",
            ),
        ]


class LearnedAlias(models.Model):
    """Owner-taught synonyms for five existing controls, isolated from web data."""

    class Intent(models.TextChoices):
        THEME_LIGHT = "theme_light", "Modo claro"
        THEME_DARK = "theme_dark", "Modo oscuro"
        CALENDAR_OPEN = "calendar_open", "Abrir calendario"
        DIRECTORY_OPEN = "directory_open", "Abrir directorio"
        EVENTS_OPEN = "events_open", "Abrir eventos"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learned_aliases"
    )
    alias = models.CharField(max_length=120)
    normalized_key = models.CharField(max_length=120, editable=False)
    intent = models.CharField(max_length=16, choices=Intent.choices)
    status = models.CharField(
        max_length=12, choices=KnowledgeEntry.Status.choices, default=KnowledgeEntry.Status.AUTO
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-updated_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "normalized_key"], name="learned_alias_owner_key"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["auto", "reviewed", "disabled"]),
                name="learned_alias_known_status",
            ),
            models.CheckConstraint(
                condition=models.Q(intent__in=[
                    "theme_light", "theme_dark", "calendar_open", "directory_open", "events_open",
                ]),
                name="learned_alias_known_intent",
            ),
        ]


class PublicLookupAttempt(models.Model):
    """Owner-scoped reservations; hashes only, no copy of the external query."""

    class Status(models.TextChoices):
        PENDING = "pending", "En curso"
        SUCCEEDED = "succeeded", "Encontrado"
        NOT_FOUND = "not_found", "Sin resultados"
        FAILED = "failed", "No disponible"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="public_lookup_attempts"
    )
    request_id = models.UUIDField()
    query_hash = models.CharField(max_length=64, editable=False)
    network_requested = models.BooleanField(default=True, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    entry = models.ForeignKey(
        KnowledgeEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="lookups"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "id")
        indexes = [models.Index(fields=["owner", "created_at"], name="lookup_owner_time")]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "request_id"], name="lookup_owner_request"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "succeeded", "not_found", "failed"]),
                name="lookup_known_status",
            ),
        ]


class EventCreationDraft(models.Model):
    """Private human-provided event fields; never a plan or model execution."""

    class Status(models.TextChoices):
        COLLECTING = "collecting", "Completando datos"
        REVIEW = "review", "Listo para revisar"
        CREATED = "created", "Evento creado"
        CANCELLED = "cancelled", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="event_creation_drafts")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COLLECTING)
    data = models.JSONField(default=dict)
    step = models.CharField(max_length=32, default="title")
    revision = models.PositiveIntegerField(default=1)
    event = models.OneToOneField("events.Event", on_delete=models.PROTECT, null=True,
                                blank=True, related_name="creation_draft")
    expires_at = models.DateTimeField()
    last_request_id = models.UUIDField(null=True, blank=True)
    last_request_hash = models.CharField(max_length=64, blank=True)
    last_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "updated_at"], name="creation_owner_updated")]
        constraints = [
            models.UniqueConstraint(fields=["owner"], condition=models.Q(status__in=["collecting", "review"]),
                                    name="creation_one_active_owner"),
            models.CheckConstraint(condition=models.Q(status__in=["collecting", "review", "created", "cancelled"]),
                                   name="creation_known_status"),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="creation_positive_revision"),
            models.CheckConstraint(condition=~models.Q(status="created") | models.Q(event__isnull=False),
                                   name="creation_completed_has_event"),
        ]
