"""Prepare the authorized credit pilot. No network request or plan changes."""
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.ai_management.catalog import catalog_entry
from apps.ai_management.agent_identity import AGENT_DISPLAY_NAME
from apps.ai_management.models import AIAccount, AIProfile
from apps.events.models import Event

DEMO_ID = uuid.uuid5(uuid.NAMESPACE_URL, "sparkx:romeo-1:controlled-unac-event:v1")


class Command(BaseCommand):
    help = "Prepara Gica-1 con GPT-5.4 mini y tope USD 1; no realiza llamadas."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="adminjorge")

    @transaction.atomic
    def handle(self, *args, **options):
        owner = get_user_model().objects.filter(username=options["username"], is_active=True, is_superuser=True).first()
        if owner is None:
            raise CommandError("Se requiere la cuenta técnica administradora activa del piloto.")
        spec = catalog_entry("openai_54_mini")
        # The public label must not create a second financial/model identity
        # when invoked on an installation whose cosmetic migration is pending.
        profile_name = AGENT_DISPLAY_NAME + " · GPT-5.4 mini"
        profile = AIProfile.objects.filter(owner=owner, name__in=(profile_name, "Romeo-1 · GPT-5.4 mini")).order_by("pk").first()
        created = profile is None
        if created:
            profile = AIProfile(owner=owner, name=profile_name, **{
                key: spec[key] for key in ("provider", "model", "mode", "input_rate", "cached_rate", "output_rate", "source_url", "verified_on")
            })
        if not created and (profile.provider, profile.model, profile.mode) != ("openai", "gpt-5.4-mini", "paid"):
            raise CommandError("El perfil Gica-1 existente tiene otra configuración; revísalo antes de continuar.")
        profile.name = profile_name
        profile.max_input_tokens, profile.max_output_tokens = 24000, 2500
        profile.input_rate, profile.cached_rate, profile.output_rate = spec["input_rate"], spec["cached_rate"], spec["output_rate"]
        profile.source_url, profile.verified_on, profile.enabled = spec["source_url"], spec["verified_on"], True
        if not created:
            profile.version += 1
        profile.save()
        account, _ = AIAccount.objects.get_or_create(owner=owner)
        account.active_profile, account.paid_enabled = profile, True
        account.monthly_budget_usd = Decimal("1")
        account.monthly_token_limit = min(account.monthly_token_limit or 200000, 200000)
        account.version += 1
        account.save()
        from apps.ai_management.agent_access import update_agent_grant
        from apps.ai_management.models import AgentGrant
        if not AgentGrant.objects.filter(account=account).exists():
            update_agent_grant(actor=owner, account=account, expected_version=0, name=AGENT_DISPLAY_NAME, enabled=True,
                budget_usd=Decimal("1"), primary_profile=profile)
        event, created = Event.objects.get_or_create(pk=DEMO_ID, defaults={
            "owner": owner, "title": "UNAC · Claves para desarrollar Tesis I, II y III · Demo Gica-1",
            "is_synthetic": True, "capacity": 20, "timezone": "America/Lima",
            "brief": "Demostración ficticia y controlada. Organizar un seminario virtual de 90 minutos para 20 estudiantes ficticios de maestría de UNAC. Objetivo: explicar la ruta de Tesis I, II y III. Proponer tres sesiones consecutivas y seis tareas de preparación con dependencias simples. No inventar nombres ni confirmaciones de expositores, enlaces Zoom, precios, correos o asistencia. Horario y ponentes pendientes de confirmar por el organizador. Usar español claro. Todo el contenido es sintético para revisar una propuesta; no publicar ni contactar a terceros.",
        })
        if event.owner_id != owner.pk or not event.is_synthetic:
            raise CommandError("La demo existente no pertenece al piloto sintético esperado.")
        self.stdout.write(self.style.SUCCESS("Gica-1 preparado. Tope global estimado USD 1, sin llamadas ni aprobaciones."))
        self.stdout.write(f"Evento controlado: /events/{event.pk}/")
