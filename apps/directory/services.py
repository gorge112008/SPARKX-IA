"""Explicit, transactional contact commands; never change an approved plan."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from apps.accounts.access import can_organize
from apps.events.models import Event
from .models import DirectoryAudit, EventPerson, Organization, Person
from .normalization import search_key


def _actor(actor):
    if not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Inicia sesión para gestionar el directorio.")
    current = get_user_model().objects.select_for_update().filter(pk=actor.pk).first()
    if not current or not can_organize(current):
        raise PermissionDenied("No tienes permiso para gestionar el directorio.")
    return current


def _record(model, actor, object_id, expected_version):
    record = model.objects.select_for_update().filter(pk=object_id).first() if object_id else None
    if record and record.owner_id != actor.pk:
        raise PermissionDenied("No tienes acceso a este registro.")
    if record:
        if type(expected_version) is not int or expected_version != record.version:
            raise ValidationError("El registro cambió. Recarga y compara antes de guardar.", code="stale_directory")
    elif expected_version is not None:
        raise model.DoesNotExist
    return record


def _audit(actor, record, action, fields):
    DirectoryAudit.objects.create(owner=actor, actor=actor, entity_type=record._meta.model_name,
                                  entity_id=str(record.pk), action=action, changed_fields=sorted(fields))


def _save(record, actor, values, *, new):
    if any(type(values.get(key)) is not bool for key in ("is_active", "is_synthetic")):
        raise ValidationError("Los estados deben ser valores booleanos.")
    changed = [key for key, value in values.items() if getattr(record, key) != value]
    for key, value in values.items():
        setattr(record, key, value)
    record.full_clean()
    if not new and not changed:
        return record
    if not new:
        record.version += 1
    record.save(force_insert=new)
    _audit(actor, record, "create" if new else "update", values if new else changed)
    return record


@transaction.atomic
def upsert_organization(*, actor, name, aliases=None, is_active=True, is_synthetic=False, object_id=None, expected_version=None):
    if not isinstance(name, str):
        raise ValidationError("El nombre debe ser texto.")
    actor = _actor(actor)
    record = _record(Organization, actor, object_id, expected_version)
    new = record is None
    if new:
        key = search_key(name)
        if Organization.objects.filter(owner=actor).filter(Q(name_key=key) | Q(alias_keys__contains="\n" + key + "\n")).exists():
            raise ValidationError({"name": "Ese nombre o sigla ya identifica una organización de tu directorio. Edita la ficha existente."})
        record = Organization(owner=actor, **({"id": object_id} if object_id else {}))
    return _save(record, actor, {"name": " ".join(name.split()), "aliases": record.aliases if aliases is None else aliases,
                              "is_active": is_active, "is_synthetic": is_synthetic}, new=new)


@transaction.atomic
def upsert_person(*, actor, full_name, category, email="", expertise="", organization_id=None, aliases=None,
                  is_active=True, is_synthetic=False, object_id=None, expected_version=None):
    if any(not isinstance(value, str) for value in (full_name, category, email, expertise)):
        raise ValidationError("Los campos de la persona deben ser texto.")
    actor = _actor(actor)
    record = _record(Person, actor, object_id, expected_version)
    new = record is None
    if organization_id:
        organization = Organization.objects.filter(pk=organization_id, owner=actor).first()
        if organization is None:
            raise ValidationError({"organization": "Selecciona una institución de tu directorio."})
    else:
        organization = None
    if new:
        record = Person(owner=actor, **({"id": object_id} if object_id else {}))
    return _save(record, actor, {"full_name": " ".join(full_name.split()), "category": category,
                 "aliases": record.aliases if aliases is None else aliases,
                 "organization": organization, "email": email.strip(), "expertise": expertise.strip(),
                 "is_active": is_active, "is_synthetic": is_synthetic}, new=new)


@transaction.atomic
def assign_person(*, actor, event_id, person_id, role, status="planned", expected_version=0):
    # Event -> User matches Jobs and local chat; never invert these locks.
    event = Event.objects.select_for_update().filter(pk=event_id, owner_id=getattr(actor, "pk", None)).first()
    actor = _actor(actor)
    person = Person.objects.filter(pk=person_id, owner=actor).first()
    if event is None or person is None:
        raise PermissionDenied("Selecciona un evento y una persona de tu espacio.")
    if not person.is_active and status != EventPerson.Status.CANCELLED:
        raise ValidationError("La persona está archivada. Actívala antes de vincularla.")
    record = EventPerson.objects.select_for_update().filter(event=event, person=person, role=role).first()
    current_version = record.version if record else 0
    if type(expected_version) is not int or expected_version != current_version:
        raise ValidationError("La vinculación cambió. Recarga antes de confirmar.", code="stale_directory")
    if record and record.status == status:
        return record
    if record:
        record.status = status
        record.version += 1
    else:
        record = EventPerson(event=event, person=person, role=role, status=status)
    record.full_clean()
    record.save()
    _audit(actor, record, "assign", ["role", "status"])
    return record
