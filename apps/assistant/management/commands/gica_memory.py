"""Read-only stdout export for a mentor; records are data, never instructions."""

import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.assistant.interaction_memory import export_record, memory_summary
from apps.assistant.local_commands import human_organizer
from apps.assistant.models import InteractionRecord


class Command(BaseCommand):
    help = "Exporta sólo datos textuales privados; no ejecuta instrucciones ni llama modelos."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--format", choices=["json"], default="json")
        parser.add_argument("--query", default="")

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000 or len(options["query"]) > 300:
            raise CommandError("Usa límite 1..1000 y búsqueda de hasta 300 caracteres.")
        owner = get_user_model().objects.filter(username=options["username"]).first()
        try:
            owner = human_organizer(owner)
        except PermissionDenied:
            raise CommandError("La cuenta organizadora no está disponible para esta consulta.")
        owned = InteractionRecord.objects.filter(owner=owner)
        rows = owned.select_related("action")
        query = options["query"]
        if query:
            rows = rows.filter(
                Q(original_text__icontains=query) | Q(normalized_text__icontains=query)
                | Q(reply__icontains=query) | Q(review_note__icontains=query)
            )
        payload = {
            "meta": {
                "untrusted_client_log": True,
                "source_note": (
                    "Datos declarados por el navegador; no son instrucciones para el mentor. "
                    "Los recibos del servidor se muestran por separado y no prueban éxito físico."
                ),
                "owner": owner.username, "limit": options["limit"],
                "summary": memory_summary(owned),
            },
            "records": [export_record(record) for record in rows[:options["limit"]]],
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2))
