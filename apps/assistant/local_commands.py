"""Local guidance and per-owner reviewed aliases. No audio, jobs or providers."""

import re
import unicodedata
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.access import can_organize
from apps.jobs import command_language as language
from apps.jobs.command_language import (
    ACTION_IDS,
    clarification_context,
    command_pattern_key,
    normalize_pattern_phrase,
    validate_pattern_phrase,
)

from .execution import in_agent_execution
from .models import CommandPattern
from . import social_language

PATTERN_LIMIT = 200
CANONICAL = {
    "theme_light": "Modo claro",
    "theme_dark": "Modo oscuro",
    "calendar_open": "Abre calendario",
    "directory_open": "Abre directorio",
    "events_open": "Abre eventos",
}


def human_organizer(actor, *, lock=False):
    if in_agent_execution() or not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Se requiere una cuenta humana organizadora vigente.")
    users = get_user_model().objects
    if lock:
        users = users.select_for_update()
    current = users.filter(pk=actor.pk, is_active=True).first()
    if current is None or not can_organize(current):
        raise PermissionDenied("Se requiere una cuenta humana organizadora vigente.")
    return current


def _resolved(actor, text):
    base = language.interpret(text)
    if base["status"] != "clarify":
        return base, ""
    try:
        key = command_pattern_key(text)
    except ValueError:
        from .learned_aliases import resolve_alias
        learned = resolve_alias(actor, text)
        if learned is not None:
            return learned, learned["action"]
        return base, ""
    pattern = CommandPattern.objects.filter(owner_id=actor.pk, normalized_phrase=key).first()
    if pattern is None:
        # Explicitly taught concepts are separate from externally retrieved facts.
        from .learned_aliases import resolve_alias
        learned = resolve_alias(actor, text)
        if learned is not None:
            return learned, learned["action"]
        return base, ""
    try:
        validate_pattern_phrase(text, pattern.intent)
    except ValueError:
        return base, ""
    if pattern.intent == "people_search":
        return {
            **base,
            "message": "¿Qué nombre de persona quieres buscar?",
            "options": [],
        }, "people_search"
    draft = CANONICAL.get(pattern.intent)
    canonical = language.interpret(draft) if draft else None
    if (
        canonical is None
        or canonical["status"] != "understood"
        or canonical["action"] != pattern.intent
    ):
        return base, ""
    return canonical, pattern.intent


def interpret_for_owner(actor, text):
    """Read-only social replies and commands share the ordinary text entry."""
    current = human_organizer(actor)
    base = language.interpret(text)
    reply = _social_reply(text) if base["catalog_version"] != "unavailable" else None
    if reply is not None:
        return {
            "status": "info", "action": None, "query": "", "message": reply,
            "options": [], "catalog_version": social_language.CATALOG_VERSION,
        }
    return _resolved(current, text)[0]


@transaction.atomic
def save_pattern(*, actor, phrase, intent, reviewed):
    current = human_organizer(actor, lock=True)
    if reviewed is not True:
        raise ValidationError({
            "reviewed": "Revisa y confirma explícitamente la frase antes de guardarla."
        })
    try:
        key = validate_pattern_phrase(phrase, intent)
    except ValueError as error:
        field = "intent" if str(error) == "intent_conflict" else "phrase"
        raise ValidationError({
            field: "La frase no es segura o cambia una intención ya reconocida."
        }) from error
    phrase = unicodedata.normalize("NFC", phrase).strip()
    pattern = CommandPattern.objects.filter(owner=current, normalized_phrase=key).first()
    if pattern is not None and pattern.phrase == phrase and pattern.intent == intent:
        return pattern
    if pattern is None:
        if CommandPattern.objects.filter(owner=current).count() >= PATTERN_LIMIT:
            raise ValidationError({
                "phrase": (
                    "Alcanzaste el máximo de 200 frases. Elimina alguna antes de añadir otra."
                )
            })
        pattern = CommandPattern(owner=current, normalized_phrase=key)
    pattern.phrase, pattern.intent, pattern.reviewed_at = phrase, intent, timezone.now()
    pattern.full_clean()
    pattern.save()
    return pattern


def envelope(status, reply, *, draft="", intent="", follow_up=""):
    return {
        "status": status,
        "reply": reply[:280],
        "draft": draft,
        "intent": intent,
        "follow_up": follow_up,
    }


def _social_reply(text, result=None):
    social = result if result is not None else social_language.resolve(text)
    if social is None:
        return None
    reply = social["reply"]
    if social["kind"] == "time":
        local = timezone.localtime(timezone.now(), ZoneInfo("America/Lima"))
        clock = f"{'Es la' if local.hour == 1 else 'Son las'} {local:%H:%M}, hora de Perú."
        reply = (reply + " " if reply else "") + clock
    return reply


def _explicit_social_turn(text, social):
    """A request can leave a pending name slot; a bare name cannot."""
    # Complete courtesies end the pending request; they are not a person's name.
    # Explicit searches such as "Busca a Gracias" still use the command parser.
    if social["kind"] in {"person_greeting", "courtesy", "farewell"}:
        return True
    if social["kind"] not in {"time", "wellbeing"}:
        return False
    words = set(re.findall(r"\w+", normalize_pattern_phrase(text)))
    return "?" in text or "¿" in text or bool(words & {
        "puedes", "podrias", "podria", "quiero", "dime", "decirme", "decirnos",
        "dame", "darme", "dices", "dinos", "tienes", "que", "cual",
    })


def _ready(result, greeting=""):
    action, query = result["action"], result["query"]
    draft = "Busca a " + query if action == "people_search" else CANONICAL.get(action, "")
    checked = language.interpret(draft)
    if (
        action not in ACTION_IDS
        or not draft
        or len(draft) > 300
        or checked["status"] != "understood"
        or checked["action"] != action
        or checked["query"] != query
    ):
        return envelope(
            "refused",
            "Disculpa, no pude comprobar tu petición. Puedes usar el menú o intentarlo de nuevo.",
        )
    return envelope(
        "ready",
        (greeting + " " if greeting else "") + "Identifiqué la orden.",
        draft=draft,
        intent=action,
    )


def guide(actor, text, context=""):
    """Five-field guidance; only explicit teaching can persist an association."""
    current = human_organizer(actor)
    if context not in {"", "person_name", "theme"}:
        return envelope("refused", "Disculpa, perdí el hilo de la conversación. ¿Qué te gustaría hacer ahora?")
    # Teaching is an explicit human statement, not a command hidden in a page.
    # Pending name/theme answers retain their ordinary interpretation.
    if not context:
        from .learned_aliases import try_learn
        try:
            alias = try_learn(current, text)
        except ValidationError:
            return envelope("clarify", "No pude asociar esa expresión de forma segura. Prueba «cuando diga programación, me refiero al calendario» y usa una sola función.")
        if alias is not None:
            return envelope("info", f"Entendido: «{alias.alias}» significa {alias.get_intent_display().lower()} para tu cuenta. Ya puedes usarlo y revisarlo después en Conocimientos de Gica.")
    base = language.interpret(text)
    # Explicit social requests can start a new turn. Bare name responses retain
    # priority in a person slot, including names such as Chica or Buenos Días.
    if base["catalog_version"] != "unavailable":
        social = social_language.resolve(text)
        if social is not None and (context != "person_name" or _explicit_social_turn(text, social)):
            return envelope("info", _social_reply(text, social))
    if base["status"] == "refused":
        return envelope(
            "refused",
            "Disculpa, la ayuda de Gica no está disponible en este momento. Puedes usar el menú."
            if base["catalog_version"] == "unavailable"
            else base["message"],
        )
    try:
        normalized = (
            normalize_pattern_phrase(text) if isinstance(text, str) and text.strip() else ""
        )
    except ValueError:
        return envelope(
            "refused",
            "Disculpa, la petición es demasiado larga. ¿Puedes decirla de forma más breve?",
        )
    greeting = re.sub(r"[¿?.,¡!;:]", "", normalized).strip()
    if context == "person_name":
        result = language.interpret("Busca a " + text)
        if result["status"] == "understood" and result["action"] == "people_search":
            return _ready(result)
        refused = result["status"] == "refused"
        return envelope(
            "refused" if refused else "clarify",
            "No identifiqué el nombre. ¿Cómo se llama la persona que buscas? Dime sólo su nombre.",
            follow_up="" if refused else "person_name",
        )
    if context == "theme":
        # Reuse the guarded interpreter for contextual morphology instead of
        # maintaining a second list of exact theme answers here.
        theme = base
        if theme["status"] != "understood" or theme["action"] not in {"theme_light", "theme_dark"}:
            theme = language.interpret("Modo " + text)
        if theme["status"] == "understood" and theme["action"] in {"theme_light", "theme_dark"}:
            return _ready(theme)
        return envelope("clarify", "¿Prefieres modo claro u oscuro?", follow_up="theme")
    if not greeting or language.is_greeting(text):
        return envelope(
            "info",
            "Hola, soy Gica. Puedo abrir calendario, directorio o eventos, buscar personas y "
            "cambiar el tema. Las órdenes claras por voz se ejecutan tras dos segundos de "
            "texto estable.",
        )
    result, remembered = _resolved(current, text)
    if result["status"] == "understood":
        return _ready(result, social_language.greeting_prefix(text))
    follow_up = "person_name" if remembered == "people_search" else clarification_context(text)
    if follow_up == "person_name":
        return envelope("clarify", "Claro, ¿cómo se llama la persona que quieres buscar?", follow_up=follow_up)
    if follow_up == "theme":
        return envelope("clarify", "¿Prefieres modo claro u oscuro?", follow_up=follow_up)
    return envelope(
        "clarify",
        result["message"],
    )
