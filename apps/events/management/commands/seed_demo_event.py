"""Load the manual GICA example without external side effects or credential changes."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from apps.events.demo import seed_demo_event


class Command(BaseCommand):
    help = "Crea una demo GICA manual e idempotente para un usuario existente; no usa IA ni servicios externos."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Identificador de inicio de sesión del propietario existente.")

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            actor = user_model.objects.get(**{user_model.USERNAME_FIELD: options["owner"]})
        except user_model.DoesNotExist as exc:
            raise CommandError("El propietario no existe. La demo no crea usuarios ni contraseñas.") from exc
        try:
            result = seed_demo_event(actor=actor)
        except (PermissionDenied, ValidationError) as exc:
            raise CommandError("No se pudo cargar la demo: " + "; ".join(getattr(exc, "messages", [str(exc)]))) from exc
        if result.created:
            self.stdout.write(self.style.SUCCESS("Demo GICA creada: plan base manual y alternativa pendiente."))
        else:
            self.stdout.write("La demo ya existe. Se conservaron todos sus datos, propuestas y cambios.")
        self.stdout.write("Demostración manual; no generado por IA. No se realizaron operaciones externas.")
        self.stdout.write("http://127.0.0.1:8000" + reverse("events:detail", args=[result.event.pk]))
