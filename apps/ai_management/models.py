"""Owner-scoped AI configuration and a durable, conservative spending ledger."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .agent_identity import AGENT_DISPLAY_NAME


class AIProfile(models.Model):
    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        GROQ = "groq", "Groq"
        GEMINI = "gemini", "Google Gemini"
        OLLAMA = "ollama", "Ollama local"
        OPENCODE = "opencode", "OpenCode · demostración gratuita"

    class Mode(models.TextChoices):
        FREE = "free", "Cuota gratuita"
        PAID = "paid", "API de pago"
        LOCAL = "local", "Modelo local"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ai_profiles")
    name = models.CharField(max_length=80)
    provider = models.CharField(max_length=12, choices=Provider.choices)
    model = models.CharField(max_length=128)
    mode = models.CharField(max_length=8, choices=Mode.choices)
    enabled = models.BooleanField(default=True)
    free_tier_confirmed = models.BooleanField(default=False)
    max_input_tokens = models.PositiveIntegerField(default=24000)
    max_output_tokens = models.PositiveIntegerField(default=2500)
    input_rate = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("0"), validators=[MinValueValidator(0)])
    cached_rate = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("0"), validators=[MinValueValidator(0)])
    output_rate = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("0"), validators=[MinValueValidator(0)])
    source_url = models.URLField(blank=True)
    verified_on = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(condition=models.Q(input_rate__gte=0, cached_rate__gte=0, output_rate__gte=0), name="ai_profile_positive_rates"),
            models.CheckConstraint(condition=models.Q(max_input_tokens__gte=1, max_output_tokens__gte=1, version__gte=1), name="ai_profile_positive_limits"),
            models.CheckConstraint(condition=models.Q(provider__in=["openai", "groq", "gemini", "ollama", "opencode"]), name="ai_profile_known_provider"),
            models.CheckConstraint(condition=models.Q(mode__in=["free", "paid", "local"]), name="ai_profile_known_mode"),
        ]

    def __str__(self):
        return self.name


class AIAccount(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ai_account")
    active_profile = models.ForeignKey(AIProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="active_accounts")
    paid_enabled = models.BooleanField(default=False)
    monthly_budget_usd = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("0"), validators=[MinValueValidator(0)])
    monthly_token_limit = models.PositiveIntegerField(default=200000)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(monthly_budget_usd__gte=0), name="ai_account_nonnegative_budget"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="ai_account_positive_version"),
        ]


class OpenAIPilotLock(models.Model):
    """Migration-seeded mutex for one server-owned, lifetime OpenAI pilot cap."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="openai_pilot_singleton")]


class AgentGrant(models.Model):
    """One server-checked agent assignment per account, containing no secrets."""

    account = models.OneToOneField(AIAccount, on_delete=models.PROTECT, related_name="agent_grant")
    code = models.SlugField(max_length=64, default="romeo-1")
    name = models.CharField(max_length=80, default=AGENT_DISPLAY_NAME)
    enabled = models.BooleanField(default=False)
    free_pool_enabled = models.BooleanField(default=False)
    free_pool_for_plans = models.BooleanField(default=False)
    budget_usd = models.DecimalField(max_digits=7, decimal_places=6, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(1)])
    primary_profile = models.ForeignKey(AIProfile, on_delete=models.PROTECT, related_name="primary_agent_grants")
    fallback_profile = models.ForeignKey(AIProfile, null=True, blank=True, on_delete=models.PROTECT,
        related_name="fallback_agent_grants")
    fallback_policy_fingerprint = models.CharField(max_length=64, blank=True)
    fallback_policy_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="approved_agent_fallbacks")
    fallback_policy_approved_at = models.DateTimeField(null=True, blank=True)
    configured_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="configured_agent_grants")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(budget_usd__gte=0, budget_usd__lte=1), name="agent_grant_pilot_budget"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="agent_grant_positive_version"),
        ]


class AgentPoolEntry(models.Model):
    """A human-approved free model assignment, never a provider quota claim."""

    class Roles(models.TextChoices):
        CHAT = "chat", "Conversación"
        PLAN = "plan", "Propuestas"
        BOTH = "both", "Conversación y propuestas"

    grant = models.ForeignKey(AgentGrant, on_delete=models.PROTECT, related_name="pool_entries")
    profile = models.ForeignKey(AIProfile, on_delete=models.PROTECT, related_name="pool_entries")
    roles = models.CharField(max_length=8, choices=Roles.choices, default=Roles.CHAT)
    enabled = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    version = models.PositiveIntegerField(default=1)
    policy_fingerprint = models.CharField(max_length=64, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="approved_agent_pool_entries")
    approved_at = models.DateTimeField(null=True, blank=True)
    daily_request_limit = models.PositiveIntegerField(default=5,
        validators=[MinValueValidator(1), MaxValueValidator(100)])
    daily_token_limit = models.PositiveIntegerField(default=60000,
        validators=[MinValueValidator(2049), MaxValueValidator(1000000)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "id")
        constraints = [
            models.UniqueConstraint(fields=["grant", "profile"], name="agent_pool_unique_profile"),
            models.CheckConstraint(condition=models.Q(roles__in=["chat", "plan", "both"]), name="agent_pool_known_role"),
            models.CheckConstraint(condition=models.Q(priority__gte=1, priority__lte=100, version__gte=1), name="agent_pool_valid_order"),
            models.CheckConstraint(condition=models.Q(daily_request_limit__gte=1, daily_request_limit__lte=100), name="agent_pool_request_limit"),
            models.CheckConstraint(condition=models.Q(daily_token_limit__gte=2049, daily_token_limit__lte=1000000), name="agent_pool_token_limit"),
        ]


class FreeGatewayState(models.Model):
    """Shared cooldown for this account's gateway, without raw remote errors."""

    account = models.OneToOneField(AIAccount, on_delete=models.PROTECT, related_name="free_gateway_state")
    cooldown_until = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class AIUsage(models.Model):
    class AccountingSource(models.TextChoices):
        UNKNOWN = "unknown", "Desconocido"
        PROVIDER = "provider", "Proveedor"
        MANUAL = "manual", "Conciliación manual"

    class Status(models.TextChoices):
        RESERVED = "reserved", "Reservado"
        DISPATCHED = "dispatched", "Solicitud enviada"
        SETTLED = "settled", "Consumo observado"
        UNCERTAIN = "uncertain", "Por conciliar"
        RELEASED = "released", "Reserva liberada"

    job = models.OneToOneField("jobs.Job", on_delete=models.PROTECT, related_name="ai_usage")
    account = models.ForeignKey(AIAccount, on_delete=models.PROTECT, related_name="usage")
    month = models.DateField()
    snapshot = models.JSONField(default=dict)
    reserved_input_tokens = models.PositiveIntegerField()
    reserved_output_tokens = models.PositiveIntegerField()
    reserved_usd = models.DecimalField(max_digits=14, decimal_places=6)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RESERVED)
    dispatch_token = models.UUIDField(null=True, blank=True, editable=False)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    cached_tokens = models.PositiveIntegerField(null=True, blank=True)
    reasoning_tokens = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost_usd = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    accounting_source = models.CharField(max_length=10, choices=AccountingSource.choices, default=AccountingSource.UNKNOWN)
    reconciled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="ai_reconciliations")
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_note = models.TextField(max_length=1000, blank=True)
    reconciliation_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=["account", "month", "status"], name="ai_usage_account_month_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(reserved_usd__gte=0), name="ai_usage_nonnegative_reserve"),
            models.CheckConstraint(condition=models.Q(estimated_cost_usd__isnull=True) | models.Q(estimated_cost_usd__gte=0), name="ai_usage_nonnegative_cost"),
            models.CheckConstraint(condition=models.Q(status__in=["reserved", "dispatched", "settled", "uncertain", "released"]), name="ai_usage_known_status"),
            models.CheckConstraint(condition=models.Q(accounting_source__in=["unknown", "provider", "manual"]), name="ai_usage_known_source"),
        ]
