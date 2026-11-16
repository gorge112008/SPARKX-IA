"""Explicit local maintenance of one owner's directory; never deletes events."""
import json
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.access import can_organize
from apps.assistant.models import EventCreationDraft
from apps.directory.models import DirectoryAudit, EventPerson, Organization, Person
from apps.directory.services import upsert_organization, upsert_person
from apps.events.models import Event
from apps.planning.models import TaskPreparation


ORGANIZATION_NAME = "Universidad Nacional del Callao - UNAC"
PERSON_NAME = "Dr. Robert Castillo Alva"
ORGANIZATION_ALIASES = ["UNAC", "Universidad Nacional del Callao"]
PERSON_ALIASES = ["Robert", "Robert Castillo Alva", "Doctor Robert Castillo Alva"]


class Command(BaseCommand):
    help = "Reinicia sólo el directorio de un propietario con UNAC y Robert; exige --apply y respaldo previo."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True)
        parser.add_argument("--apply", action="store_true", help="Aplica la limpieza expresamente autorizada.")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Elige --apply o --dry-run, no ambos.")
        owner = get_user_model().objects.filter(username=options["owner"]).first()
        if not owner or not can_organize(owner):
            raise CommandError("Selecciona un organizador activo existente.")
        # Keep the established Event -> User lock order for live application data.
        list(Event.objects.select_for_update().filter(owner=owner).values_list("pk", flat=True))
        owner = get_user_model().objects.select_for_update().get(pk=owner.pk)
        organizations = Organization.objects.filter(owner=owner)
        people = Person.objects.filter(owner=owner)
        org_ids, person_ids = list(organizations.values_list("pk", flat=True)), list(people.values_list("pk", flat=True))
        if (Event.objects.filter(organization_id__in=org_ids).exclude(owner=owner).exists()
                or Person.objects.filter(organization_id__in=org_ids).exclude(owner=owner).exists()
                or EventPerson.objects.filter(person_id__in=person_ids).exclude(event__owner=owner).exists()):
            raise CommandError("Hay referencias de otro propietario: no se modificó ningún registro.")
        if TaskPreparation.objects.filter(responsible_person_id__in=person_ids).exists():
            raise CommandError("Hay responsables vinculados a preparación de tareas. Conserva o archiva esas personas antes de reiniciar; no se borró evidencia.")
        org_id = uuid5(NAMESPACE_URL, f"sparkx:directory-clean:v1:{owner.pk}:unac")
        person_id = uuid5(NAMESPACE_URL, f"sparkx:directory-clean:v1:{owner.pk}:robert")
        canonical_org = organizations.filter(pk=org_id).first()
        canonical_person = people.filter(pk=person_id).first()
        if Organization.objects.filter(pk=org_id).exclude(owner=owner).exists() or Person.objects.filter(pk=person_id).exclude(owner=owner).exists():
            raise CommandError("Identidad canónica ocupada por otro propietario.")
        removed_org_ids = [value for value in org_ids if value != org_id]
        removed_person_ids = [value for value in person_ids if value != person_id]
        report = {"owner": owner.get_username(), "apply": bool(options["apply"]),
            "organizations_removed": len(removed_org_ids), "people_removed": len(removed_person_ids),
            "event_organizations_detached": Event.objects.filter(owner=owner, organization_id__in=removed_org_ids).count(),
            "event_people_removed": EventPerson.objects.filter(person_id__in=removed_person_ids).count(),
            "events_deleted": 0, "plans_deleted": 0}
        if not options["apply"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False))
            return
        changed = bool(removed_org_ids or removed_person_ids or canonical_org is None or canonical_person is None)
        Event.objects.filter(owner=owner, organization_id__in=removed_org_ids).update(
            organization=None, revision=F("revision") + 1, updated_at=timezone.now())
        EventPerson.objects.filter(person_id__in=removed_person_ids).delete()
        # Canonical Robert may have acquired a different affiliation after a
        # previous run; detach before deleting that organization, then restore.
        if canonical_person and canonical_person.organization_id in removed_org_ids:
            canonical_person.organization = None
            canonical_person.save(update_fields=["organization"])
        people.filter(pk__in=removed_person_ids).delete()
        organizations.filter(pk__in=removed_org_ids).delete()
        org = upsert_organization(actor=owner, object_id=org_id, expected_version=canonical_org.version if canonical_org else None,
            name=ORGANIZATION_NAME, aliases=ORGANIZATION_ALIASES)
        upsert_person(actor=owner, object_id=person_id, expected_version=canonical_person.version if canonical_person else None,
            full_name=PERSON_NAME, category="speaker", aliases=PERSON_ALIASES, organization_id=org.pk)
        removed_org_strings, removed_person_strings = set(map(str, removed_org_ids)), set(map(str, removed_person_ids))
        draft_count = 0
        for draft in EventCreationDraft.objects.select_for_update().filter(owner=owner, status__in=["collecting", "review"]):
            data, affected = dict(draft.data), False
            if data.get("organization_id") in removed_org_strings:
                data.update(organization_id=None, organization_name="")
                affected = True
            selected = data.get("directory_people", [])
            kept = [item for item in selected if item.get("id") not in removed_person_strings]
            if len(selected) != len(kept):
                data["directory_people"] = kept
                affected = True
            if "_directory_resolution" in data:
                data.pop("_directory_resolution")
                affected = True
            if affected:
                draft.data, draft.revision = data, draft.revision + 1
                draft.last_request_id, draft.last_request_hash, draft.last_response = None, "", {}
                draft.save()
                draft_count += 1
        if changed:
            DirectoryAudit.objects.create(owner=owner, actor=owner, entity_type="directory", entity_id=str(owner.pk),
                action="reset", changed_fields=["contacts", "organizations", "directory_links"])
        report["draft_links_cleared"] = draft_count
        self.stdout.write(self.style.SUCCESS(json.dumps(report, ensure_ascii=False)))
