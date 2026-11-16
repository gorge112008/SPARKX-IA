"""Prepare a fictional manual event without consuming API or approving plans."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from apps.events.journey_demo import JOURNEY_NOTICE, seed_journey_demo


class Command(BaseCommand):
    help = "Crea una segunda demo guiada con datos ficticios y propuesta pendiente; no usa IA ni aprueba planes."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Usuario de acceso del propietario existente.")

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            actor = user_model.objects.get(**{user_model.USERNAME_FIELD: options["owner"]})
        except user_model.DoesNotExist as exc:
            raise CommandError("El propietario no existe. La demo no crea usuarios ni contraseñas.") from exc
        try:
            result = seed_journey_demo(actor=actor)
        except (PermissionDenied, ValidationError) as exc:
            raise CommandError(
                "No se pudo preparar la demo: " + "; ".join(getattr(exc, "messages", [str(exc)]))
            ) from exc
        if result.created:
            self.stdout.write(self.style.SUCCESS(
                "Demo guiada creada con una propuesta base pendiente de tu revisión y aprobación."
            ))
        else:
            self.stdout.write("La demo ya existe. Se conservaron sus datos, propuestas, planes y estados de tareas.")
        self.stdout.write(JOURNEY_NOTICE)
        self.stdout.write("http://127.0.0.1:8000" + reverse("events:journey_demo", args=[result.event.pk]))
