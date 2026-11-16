"""Execute one recognized, synthetic-only local directory query; never an LLM."""

import json
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.access import can_organize
from apps.assistant.local_queries import _command, local_directory_reply
from apps.events.models import Event


class Command(BaseCommand):
    help = "Ejecuta una consulta local reconocida de Gica-1 en un evento ficticio propio, sin API."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--event", required=True)
        parser.add_argument("--command", required=True)
        parser.add_argument("--request-key")

    @transaction.atomic
    def handle(self, *args, **options):
        prompt = options["command"]
        if not isinstance(prompt, str) or len(prompt) > 4000 or _command(prompt) is None:
            raise CommandError("Usa únicamente un comando local reconocido del directorio.")
        try:
            event_id = UUID(str(options["event"]))
            request_key = UUID(str(options["request_key"])) if options.get("request_key") is not None else uuid4()
        except (ValueError, TypeError, AttributeError) as exc:
            raise CommandError("El evento y la clave de solicitud deben ser UUID válidos.") from exc
        actor = get_user_model().objects.filter(username=options["username"], is_active=True).first()
        if actor is None or not can_organize(actor):
            raise CommandError("Se requiere un organizador o administrador activo.")
        event = Event.objects.select_for_update().filter(pk=event_id, owner_id=actor.pk).first()
        if event is None or not event.is_synthetic:
            raise CommandError("La consulta requiere un evento ficticio propio.")
        try:
            reply = local_directory_reply(event=event, actor=actor, prompt=prompt, request_key=request_key)
        except (PermissionDenied, ValidationError) as exc:
            raise CommandError("No se pudo completar la consulta local autorizada.") from exc
        if reply is None:
            raise CommandError("La orden no corresponde a una consulta local reconocida.")
        # Content and search results remain only in the authorized event's chat.
        self.stdout.write(json.dumps({
            "message_id": str(reply.pk), "event_id": str(event.pk),
            "status": "local_completed", "local": True, "api_calls": 0,
        }, sort_keys=True))
