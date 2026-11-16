"""Allowlisted mechanical reads. No model, shell, provider, write or approval."""
import json
import uuid

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.events.catalog import find_events
from .queries import directory_actor, event_people, search_people

TOOL_ARGUMENTS = {
    "search_people": {"q", "category", "organization", "limit"},
    "search_events": {"q", "organization", "from", "to", "plan", "limit"},
    "event_people": {"event", "limit"},
}


def _person(person):
    return {"id": str(person.pk), "name": person.full_name, "category": person.category,
            "organization": {"id": str(person.organization_id), "name": person.organization.name} if person.organization_id else None,
            "is_synthetic": person.is_synthetic, "version": person.version}


def execute_tool(*, actor, name, arguments):
    """Use server identity; validate before lookup; expose explicit fields only.

    This is a local entry point, not an integrated LLM tool loop. A future
    adapter must preserve these permissions and approval boundaries.
    """
    actor = directory_actor(actor)
    if not isinstance(name, str) or name not in TOOL_ARGUMENTS or not isinstance(arguments, dict) or set(arguments) - TOOL_ARGUMENTS[name]:
        raise ValidationError("Herramienta o argumentos no permitidos.")
    limit = arguments.get("limit", 10)
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValidationError("El límite debe ser un entero entre 1 y 20.")
    if any(not isinstance(value, str) or len(value) > 200 for key, value in arguments.items() if key != "limit"):
        raise ValidationError("Los filtros deben ser textos de hasta 200 caracteres.")
    if name == "search_people":
        records = search_people(actor, query=arguments.get("q", ""), category=arguments.get("category", ""),
                                organization_id=arguments.get("organization", ""))
        total = records.count()
        items = [_person(person) for person in records[:limit]]
    elif name == "search_events":
        try:
            found = find_events(actor=actor, params={k: v for k, v in arguments.items() if k != "limit"}, limit=limit)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        total = found["total"]
        items = [{"id": str(entry["event"].pk), "title": entry["event"].title,
                  "date": entry["date"].isoformat() if entry["date"] else None,
                  "starts_at": entry["starts_at"].isoformat() if entry["starts_at"] else None,
                  "timezone": entry["timezone"], "date_source": entry["date_source"],
                  "has_approved_plan": entry["has_plan"], "plan_version": entry["plan_version"],
                  "organization": {"id": str(entry["organization"].pk), "name": entry["organization"].name} if entry["organization"] else None,
                  "is_synthetic": entry["is_synthetic"]} for entry in found["entries"]]
    else:
        try:
            event_id = uuid.UUID(arguments.get("event", ""))
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError("Selecciona un evento válido.") from error
        from apps.events.models import Event
        try:
            records = event_people(actor, event_id)
        except Event.DoesNotExist as error:
            raise ValidationError("No se encontró el evento en tu espacio.") from error
        total = records.count()
        items = [{"person": _person(link.person), "role": link.role,
                  "status": link.status, "version": link.version} for link in records[:limit]]
    result = {"tool": name, "items": items, "total": total, "has_more": total > limit,
              "limit": limit, "captured_at": timezone.now().isoformat(),
              "read_only": True, "source": "local_database", "model_invoked": False}
    # Bytes are measurable here. They are NOT an exact model-token estimate.
    result["payload_bytes_without_this_field"] = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    return result
