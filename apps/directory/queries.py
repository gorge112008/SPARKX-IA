"""Bounded filters shared by HTTP and local assistant tools."""
import re
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Q

from apps.accounts.access import can_organize
from apps.events.models import Event
from .models import EventPerson, Organization, Person
from .normalization import search_key


def directory_actor(actor):
    current = get_user_model().objects.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if current is None or not can_organize(current):
        raise PermissionDenied("El directorio es privado del organizador.")
    return current


def organizations_for(actor):
    return Organization.objects.filter(owner=directory_actor(actor), archived_at__isnull=True)


def people_for(actor):
    # A historically corrupt foreign affiliation must not expose its name.
    return Person.objects.filter(owner=directory_actor(actor), archived_at__isnull=True).filter(
        Q(organization__isnull=True) | Q(organization__owner_id=F("owner_id"), organization__archived_at__isnull=True)
    ).select_related("organization")


def exact_directory_matches(actor, name, *, kind="organization"):
    """An exact reviewed name/alias may resolve several homonyms: never pick one."""
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise ValidationError("Indica un nombre o alias de hasta 160 caracteres.")
    key = search_key(name)
    source = organizations_for(actor) if kind == "organization" else people_for(actor) if kind == "person" else None
    if source is None:
        raise ValidationError("Tipo de registro no permitido.")
    return source.filter(is_active=True).filter(Q(name_key=key) | Q(alias_keys__contains="\n" + key + "\n")).order_by("pk")


def suggested_directory_matches(actor, name, *, kind="organization"):
    """All useful normalized terms must match; suggestions never prove identity.

    The caller must show these records for an explicit selection, including when
    only one record is returned. Never broaden a private query to other owners.
    """
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise ValidationError("Indica un nombre o alias de hasta 160 caracteres.")
    source = organizations_for(actor) if kind == "organization" else people_for(actor) if kind == "person" else None
    if source is None:
        raise ValidationError("Tipo de registro no permitido.")
    terms = set(re.findall(r"\w+", search_key(name))) - {
        "de", "del", "la", "las", "el", "los", "y", "en", "un", "una", "es", "sera", "seria",
        "institucion", "empresa", "organizacion", "organiza", "organizador", "organizadora",
        "por", "para", "evento", "favor", "mi", "su", "quiero", "que", "sea", "se", "llama", "llamado", "llamada",
    }
    terms = sorted(term for term in terms if len(term) >= 2)
    result = source.filter(is_active=True)
    if not terms:
        return result.none()
    for term in terms:
        result = result.filter(Q(name_key__contains=term) | Q(alias_keys__contains=term))
    return result.order_by("name_key", "pk")


def search_people(actor, query="", category="", organization_id="", include_inactive=False):
    if not isinstance(query, str) or len(query) > 200:
        raise ValidationError("La búsqueda admite hasta 200 caracteres.")
    if category and category not in Person.Category.values:
        raise ValidationError("La categoría no es válida.")
    if type(include_inactive) is not bool:
        raise ValidationError("El estado del filtro no es válido.")
    result = people_for(actor)
    if not include_inactive:
        result = result.filter(is_active=True)
    for term in search_key(query).split():
        result = result.filter(Q(name_key__contains=term) | Q(alias_keys__contains=term) |
                               Q(organization__name_key__contains=term) | Q(organization__alias_keys__contains=term))
    if category:
        result = result.filter(category=category)
    if organization_id:
        try:
            identifier = uuid.UUID(str(organization_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValidationError("La institución no es válida.") from error
        # A foreign UUID returns an empty result, without disclosing its existence.
        result = result.filter(organization_id=identifier)
    return result


def event_people(actor, event_id):
    actor = directory_actor(actor)
    event = Event.objects.filter(owner=actor, pk=event_id, archived_at__isnull=True).first()
    if event is None:
        raise Event.DoesNotExist
    return EventPerson.objects.filter(event=event, person__owner=actor).filter(
        Q(person__organization__isnull=True) | Q(person__organization__owner_id=actor.pk)
    ).select_related("person", "person__organization", "event")
