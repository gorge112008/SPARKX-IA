"""Exact Spanish chat commands backed only by authorized local read tools."""

from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.directory.normalization import search_key
from apps.directory.queries import directory_actor, event_people, search_people
from apps.directory.tools import execute_tool
from apps.events.models import Event
from apps.events.services import require_event_owner

from .models import Message

COMMANDS = {
    "buscar expositores": ("search_people", "speaker", "Expositores"),
    "buscar participantes": ("search_people", "participant", "Participantes"),
    "buscar invitados": ("search_people", "guest", "Invitados"),
    "buscar eventos": ("search_events", None, "Eventos"),
}
ROLES = {"speaker": "Expositor", "participant": "Participante", "guest": "Invitado"}
STATUSES = {
    "planned": "Por confirmar",
    "confirmed": "Confirmado por el organizador",
    "cancelled": "Cancelado",
}
LOCAL_LIMIT = 10


def _command(prompt):
    if not isinstance(prompt, str):
        return None
    prefix, separator, query = prompt.partition(":")
    normalized = search_key(prefix)
    if normalized == "personas de este evento" and not separator:
        return "event_people", {}, "Personas de este evento"
    command = COMMANDS.get(normalized)
    if command is None:
        return None
    name, category, label = command
    arguments = {"q": query.strip() if separator else ""}
    if category:
        arguments["category"] = category
    return name, arguments, label


def _text(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


def _organization(item):
    organization = item.get("organization")
    return " · " + _text(organization["name"], 160) if organization else ""


def _person_line(item, *, role=None, status=None):
    line = _text(item["name"], 160) + " · " + ROLES.get(role or item["category"], "Categoría pendiente")
    line += _organization(item)
    if status is not None:
        line += " · Estado registrado: " + STATUSES.get(status, "Pendiente")
    if item["is_synthetic"]:
        line += " · Ficticio"
    return line


def _event_line(item):
    line = _text(item["title"]) + _organization(item)
    if item["date"]:
        source = "Fecha del plan" if item["date_source"] == "plan" else "Fecha"
        line += f" · {source}: {_text(item['date'], 10)} · {_text(item['timezone'], 64)}"
    else:
        line += " · Fecha pendiente"
    line += " · Plan aprobado" if item["has_approved_plan"] else " · Plan pendiente"
    if item["is_synthetic"]:
        line += " · Ficticio"
    return line


def _reply(result, label):
    items = result["items"][:LOCAL_LIMIT]
    lines = [
        "Consulta local del directorio, sin modelo de IA.",
        f"{label}: {result['total']} resultado(s); muestro {len(items)}.",
    ]
    for index, item in enumerate(items, start=1):
        if result["tool"] == "event_people":
            text = _person_line(item["person"], role=item["role"], status=item["status"])
        elif result["tool"] == "search_events":
            text = _event_line(item)
        else:
            text = _person_line(item)
        lines.append(f"{index}. {text}")
    if result["has_more"]:
        lines.append("Hay más resultados; afina la búsqueda.")
    if result["tool"] in {"search_people", "event_people"}:
        lines.append("Los registros no acreditan disponibilidad ni asistencia.")
    return "\n".join(lines)


def _synthetic_person(person):
    organization = person.organization if person.organization_id else None
    if organization and (organization.owner_id != person.owner_id or not organization.is_synthetic):
        organization = None
    return {"name": person.full_name, "category": person.category, "is_synthetic": True,
            "organization": {"name": organization.name} if organization else None}


def _synthetic_tool(*, actor, name, arguments):
    """Synthetic event queries cannot import real records or affiliations."""
    if name == "search_people":
        records = search_people(actor, query=arguments.get("q", ""), category=arguments.get("category", ""))
        records = records.filter(is_synthetic=True)
        total = records.count()
        items = [_synthetic_person(person) for person in records[:LOCAL_LIMIT]]
    elif name == "event_people":
        records = event_people(actor, arguments["event"]).filter(person__is_synthetic=True)
        total = records.count()
        items = [{"person": _synthetic_person(link.person), "role": link.role, "status": link.status}
                 for link in records[:LOCAL_LIMIT]]
    else:
        from apps.events.catalog import find_events
        try:
            found = find_events(actor=actor, params={"q": arguments.get("q", "")})
        except ValueError as error:
            raise ValidationError(str(error)) from error
        entries = [entry for entry in found["entries"] if entry["is_synthetic"]]
        total = len(entries)
        items = []
        for entry in entries[:LOCAL_LIMIT]:
            organization = entry["organization"]
            items.append({"title": entry["event"].title, "date": entry["date"].isoformat() if entry["date"] else None,
                          "date_source": entry["date_source"], "timezone": entry["timezone"],
                          "has_approved_plan": entry["has_plan"], "is_synthetic": True,
                          "organization": {"name": organization.name} if organization and organization.is_synthetic else None})
    return {"tool": name, "items": items, "total": total, "has_more": total > LOCAL_LIMIT,
            "captured_at": timezone.now().isoformat()}


def local_directory_reply(*, event, actor, prompt, request_key):
    """Persist one local user/assistant pair, or return None for other prompts.

    A recognized command obtains fresh owner authority before looking up an
    earlier response. Its ``local:<UUID>`` identity never creates a Job or usage
    reservation. An exact retry returns the original recorded response.
    """
    command = _command(prompt)
    if command is None:
        return None
    if len(prompt) > 4000:
        raise ValidationError("La consulta admite hasta 4000 caracteres.")
    try:
        key = "local:" + str(UUID(str(request_key)))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("La consulta local requiere una clave UUID válida.") from error
    name, arguments, label = command
    with transaction.atomic():
        current_event = Event.objects.select_for_update().get(pk=event.pk)
        locked_actor = get_user_model().objects.select_for_update().filter(pk=getattr(actor, "pk", None)).first()
        current_actor = directory_actor(locked_actor)
        require_event_owner(current_event, current_actor)
        previous = {
            message.role: message for message in Message.objects.filter(event=current_event, request_key=key)
        }
        if previous:
            if set(previous) != {Message.Role.USER, Message.Role.ASSISTANT}:
                raise ValidationError("La consulta local está incompleta y requiere revisión.")
            if previous[Message.Role.USER].content != prompt:
                raise ValidationError("La clave de solicitud ya se utilizó con otro contenido.", code="idempotency_conflict")
            return previous[Message.Role.ASSISTANT]
        arguments["limit"] = LOCAL_LIMIT
        if name == "event_people":
            arguments["event"] = str(current_event.pk)
        result = (_synthetic_tool(actor=current_actor, name=name, arguments=arguments) if current_event.is_synthetic
                  else execute_tool(actor=current_actor, name=name, arguments=arguments))
        content = _reply(result, label)
        Message.objects.create(event=current_event, role=Message.Role.USER, content=prompt, request_key=key)
        return Message.objects.create(
            event=current_event, role=Message.Role.ASSISTANT, content=content, request_key=key,
        )
