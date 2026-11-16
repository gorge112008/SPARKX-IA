"""A repeatable, local demonstration; never registers or contacts anybody."""

from collections import Counter
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.accounts.access import can_organize
from apps.directory.models import EventPerson, Organization, Person
from apps.directory.services import assign_person, upsert_organization, upsert_person
from apps.events.models import Event
from apps.events.services import create_event
from apps.planning.domain import validate_plan
from apps.planning.services import create_candidate


TITLES = (
    "Claves para desarrollar Tesis I, II y III",
    "Tu ruta hacia el Grado de Maestro",
    "De la idea al proyecto de tesis aprobado",
    "Del proyecto a la sustentación de tesis",
    "Últimos pasos para obtener tu Grado de Maestro",
    "Claves para desarrollar Tesis I, II y III",
)
SESSION_TITLES = (
    ("Delimitar el tema de tesis", "Relacionar preguntas y objetivos", "Organizar los hitos de Tesis I, II y III"),
    ("Reconocer la ruta académica", "Ordenar requisitos y evidencias", "Preparar una consulta sobre el grado"),
    ("Convertir una idea en pregunta", "Esbozar un diseño viable", "Revisar el proyecto antes de presentarlo"),
    ("Planificar la ejecución del proyecto", "Construir el argumento de resultados", "Ensayar preguntas de sustentación"),
    ("Revisar actas y documentos pendientes", "Ordenar el expediente de grado", "Preparar el seguimiento del cierre"),
    ("Reconocer las etapas de investigación", "Practicar una matriz de consistencia", "Definir próximos pasos de tutoría"),
)
SPEAKERS = (
    ("Expositor ficticio A", "Metodología y proyecto de tesis"),
    ("Expositor ficticio B", "Escritura y sustentación"),
    ("Expositor ficticio C", "Ruta académica y cierre"),
)
LIMA = ZoneInfo("America/Lima")


def synthetic_id(owner_id, key):
    """Separate each owner's demonstration without depending on names or email."""
    return uuid5(NAMESPACE_URL, f"sparkx:synthetic-directory-week:v1:{owner_id}:{key}")


def proposed_plan(day, starts_at):
    """Maintained content in the application's strict plan contract, without AI."""
    sessions = [
        {
            "id": f"s{index + 1}",
            "title": title,
            "start": (starts_at + timedelta(minutes=30 * index)).isoformat(),
            "duration_minutes": 30,
            "speaker": SPEAKERS[(index + day) % len(SPEAKERS)][0],
            "resource": "Sala virtual ficticia; pendiente de confirmar",
        }
        for index, title in enumerate(SESSION_TITLES[day])
    ]
    return {
        "title": TITLES[day],
        "summary": (
            "Demostración sintética preparada localmente, sin inferencia de IA. "
            "Propuesta pendiente de revisión y aprobación del organizador. "
            "Supuestos: horario de ejemplo en America/Lima, tres expositores ficticios "
            "y una sala virtual ficticia. Su disponibilidad y participación no están confirmadas. "
            "Los vínculos previstos del directorio no acreditan inscripción ni asistencia."
        ),
        "sessions": sessions,
        "tasks": [
            {
                "id": "t1", "title": f"Revisar el alcance: {SESSION_TITLES[day][0]}",
                "depends_on": [], "status": "pending",
                "purpose": "Revisar el contenido de demostración antes de usarlo para un evento real.",
            },
            {
                "id": "t2", "title": "Consultar disponibilidad de ponentes y sala",
                "depends_on": ["t1"], "status": "pending",
                "purpose": "Obtener confirmaciones reales por un proceso autorizado; esta semilla no las solicita.",
            },
            {
                "id": "t3", "title": "Revisar y aprobar la agenda propuesta",
                "depends_on": ["t2"], "status": "pending",
                "purpose": "Reservar la decisión sobre el plan al organizador, sin aprobarlo automáticamente.",
            },
        ],
        "risks": [
            "Los horarios, la sala y los expositores son supuestos ficticios sin confirmación.",
            "Las personas de demostración no representan inscripciones ni asistencia real.",
        ],
    }


class Command(BaseCommand):
    help = "Crea una semana de demostración sintética sin aprobar planes ni contactar personas."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Usuario organizador existente, por ejemplo adminjorge.")
        parser.add_argument("--dry-run", action="store_true", help="Valida toda la carga y revierte sus cambios.")

    def _existing(self, model, identity, owner):
        current = model.objects.select_for_update().filter(pk=identity).first()
        if current is not None and (current.owner_id != owner.pk or not current.is_synthetic):
            raise CommandError("Colisión con un registro ajeno o no sintético; no se modificó la carga.")
        return current

    def _organization(self, owner, code, counts):
        identity = synthetic_id(owner.pk, f"organization:{code}")
        existing = self._existing(Organization, identity, owner)
        if existing is not None:
            counts["organizaciones reutilizadas"] += 1
            return existing
        value = upsert_organization(
            actor=owner, name=f"{code} · Demostración sintética", is_active=True,
            is_synthetic=True, object_id=identity, expected_version=None,
        )
        counts["organizaciones creadas"] += 1
        return value

    def _person(self, owner, key, name, category, organization, counts, expertise=""):
        identity = synthetic_id(owner.pk, f"person:{key}")
        existing = self._existing(Person, identity, owner)
        if existing is not None:
            if existing.category != category:
                raise CommandError("Colisión con una categoría diferente; no se modificó la carga.")
            counts["personas reutilizadas"] += 1
            return existing
        value = upsert_person(
            actor=owner, full_name=name, category=category, email=f"{key}@sparkx-demo.invalid",
            expertise=expertise, organization_id=organization.pk if organization else None,
            is_active=True, is_synthetic=True, object_id=identity, expected_version=None,
        )
        counts["personas creadas"] += 1
        return value

    def _assign(self, owner, event, person, role, counts):
        if EventPerson.objects.select_for_update().filter(event=event, person=person, role=role).exists():
            # Confirmations, cancellations and versions already edited by a human survive retries.
            counts["vínculos reutilizados"] += 1
            return
        assign_person(actor=owner, event_id=event.pk, person_id=person.pk, role=role, status="planned", expected_version=0)
        counts["vínculos creados"] += 1

    def _seed(self, owner, counts):
        organizations = {code: self._organization(owner, code, counts) for code in ("UNAC", "GICA")}
        speakers = [
            self._person(owner, f"speaker-{index + 1}", name, "speaker", None, counts, expertise)
            for index, (name, expertise) in enumerate(SPEAKERS)
        ]
        for day, title in enumerate(TITLES):
            organization = organizations["GICA" if day == 5 else "UNAC"]
            starts_at = datetime(2026, 11, 16 + day, 17, 0, tzinfo=LIMA)
            identity = synthetic_id(owner.pk, f"event:{day + 1}")
            event = self._existing(Event, identity, owner)
            if event is None:
                event = create_event(
                    actor=owner, event_id=identity, title=title, starts_at=starts_at,
                    timezone="America/Lima", capacity=80, organization_id=organization.pk,
                    is_synthetic=True,
                    brief=(
                        f"Demostración sintética de {organization.name}, del 16 al 21 de noviembre de 2026. "
                        f"Tema: {title}. Horario y sala son supuestos de ejemplo. "
                        "Las personas son ficticias y sus correos usan el dominio reservado .invalid. "
                        "Los vínculos son previstos: no acreditan inscripción, confirmación ni asistencia. "
                        "La candidata local requiere revisión humana; no se ejecuta IA ni se envían mensajes."
                    ),
                )
                payload = proposed_plan(day, starts_at)
                errors = validate_plan(payload)
                if errors:
                    raise CommandError("La propuesta sintética no supera la validación: " + "; ".join(errors))
                create_candidate(event=event, actor=owner, payload=payload, base_revision=event.revision, base_plan_id=event.active_plan_id)
                counts["eventos creados"] += 1
                counts["candidatas creadas"] += 1
            else:
                if event.organization_id != organization.pk:
                    raise CommandError("Colisión con una organización de evento diferente; no se modificó la carga.")
                counts["eventos reutilizados"] += 1
                # Never regenerate a proposal or alter a plan/task on a previously seeded event.
                counts["candidatas conservadas"] += event.candidates.count()
            for speaker in speakers:
                self._assign(owner, event, speaker, "speaker", counts)
            for index in range(5):
                number = day * 5 + index + 1
                person = self._person(owner, f"participant-{number:02d}", f"Participante ficticio {number:02d}", "participant", organization, counts)
                self._assign(owner, event, person, "participant", counts)
            for index in range(2):
                number = day * 2 + index + 1
                person = self._person(owner, f"guest-{number:02d}", f"Invitado ficticio {number:02d}", "guest", organization, counts)
                self._assign(owner, event, person, "guest", counts)

    def handle(self, *args, **options):
        counts = Counter()
        try:
            with transaction.atomic():
                user_model = get_user_model()
                try:
                    owner = user_model.objects.select_for_update().get(**{user_model.USERNAME_FIELD: options["owner"]})
                except user_model.DoesNotExist as exc:
                    raise CommandError("El propietario debe ser un usuario existente; la semilla no crea cuentas.") from exc
                if not can_organize(owner):
                    raise CommandError("El propietario debe ser un organizador activo.")
                self._seed(owner, counts)
                if options["dry_run"]:
                    transaction.set_rollback(True)
        except (ValidationError, PermissionDenied, IntegrityError) as exc:
            raise CommandError("La carga sintética fue revertida: " + str(exc)) from exc
        mode = "Simulación revertida" if options["dry_run"] else "Carga sintética completada"
        self.stdout.write(mode + ": " + "; ".join(f"{label}: {count}" for label, count in counts.items()) + ".")
        self.stdout.write("Planes sin aprobación automática; vínculos previstos, sin inscripción ni asistencia acreditada.")
