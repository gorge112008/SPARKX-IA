"""Explicit owner-taught vocabulary for five existing, bounded UI actions.

External answers never call this service. A teaching turn stores an association,
not an action, and every later use goes through the ordinary action validator.
"""

import re
import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.jobs import command_language as language

from .models import CommandPattern, LearnedAlias
from . import social_language


ALIAS_LIMIT = 100
CANONICAL_COMMANDS = {
    "theme_light": "Modo claro",
    "theme_dark": "Modo oscuro",
    "calendar_open": "Abre calendario",
    "directory_open": "Abre directorio",
    "events_open": "Abre eventos",
}
_TEACHING = (
    re.compile(
        r"(?:Gica\s*,?\s+)?cuando diga\s+(?P<alias>.+?)\s*,?\s+"
        r"me refiero (?:a la|al|a)\s+(?P<target>.+)", re.IGNORECASE,
    ),
    re.compile(
        r"(?:Gica\s*,?\s+)?cuando diga\s+(?P<alias>.+?)\s*,?\s+"
        r"quiero abrir\s+(?P<target>.+)", re.IGNORECASE,
    ),
    re.compile(
        r"(?:Gica\s*,?\s+)?(?P<alias>.+?)\s+significa\s+(?P<target>.+)",
        re.IGNORECASE,
    ),
)
_CONCEPT = re.compile(r"[^\W\d_]+(?: [^\W\d_]+){0,2}", re.UNICODE)
_NON_CONCEPTS = frozenset({
    "yo", "tu", "usted", "ustedes", "el", "ella", "ellos", "ellas", "nosotros",
    "nosotras", "mi", "mis", "su", "sus", "me", "te", "se", "nos", "lo",
    "los", "la", "las", "le", "les", "a", "al", "del", "en", "que", "como",
    "cuando", "donde", "quien", "cual", "y", "o", "u", "e", "pero", "si",
    "entonces", "porque", "pues", "nombre", "nombres", "persona", "personas",
    "contacto", "contactos", "llamado", "llamada", "saluda", "saludar", "hora",
    "horas", "ayuda", "ayudar", "gracias", "hola", "adios", "bien", "ok",
    "entendido", "aprende", "aprender", "recuerda", "recordar", "significa",
    "diga", "digo", "refiero", "quiero", "ejecuta", "ejecutar", "cancela",
    "cancelar", "silencio", "hablemos", "script", "comando", "instala", "instalar",
    "descarga", "descargar", "formatea", "formatear", "sistema", "system",
    "prompt", "instrucciones", "seguridad", "secretos", "secreto", "dinero",
    "token", "tokens", "clave", "claves", "credencial", "credenciales",
    "contrasena", "contrasenas", "permiso", "permisos", "pago", "pagos",
    "presupuesto", "administracion", "administrador", "administradores",
})


def _invalid(message="Esa asociación no es segura o corresponde a una orden ya reconocida."):
    return ValidationError({"alias": message})


def parse_teaching(text):
    """Recognize complete teaching frames only; a definition question is not one."""
    if not isinstance(text, str) or not 1 <= len(text) <= 300 or any(char in text for char in "¿?"):
        return None
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in text):
        return None
    # A final period is ordinary punctuation, but a quoted/reported sentence is
    # never taken as a new vocabulary instruction.
    value = unicodedata.normalize("NFC", text).strip().removesuffix(".").strip()
    for expression in _TEACHING:
        match = expression.fullmatch(value)
        if match is not None:
            alias = match.group("alias").strip().rstrip(",")
            try:
                key = language.normalize_pattern_phrase(alias)
            except ValueError:
                return None
            if key.split()[0] in {"que", "como", "quien", "cual", "me", "te", "le", "se", "el", "ella", "ellos", "ellas", "nos", "por"}:
                return None
            return alias, match.group("target").strip()
    return None


def _concept_key(alias, intent):
    if intent not in CANONICAL_COMMANDS:
        raise _invalid("Sólo puedes asociar calendario, directorio, eventos y los dos temas.")
    try:
        key = language.normalize_pattern_phrase(alias)
    except ValueError as error:
        raise _invalid() from error
    if len(key) > 120 or not _CONCEPT.fullmatch(key) or len(key) < 4:
        raise _invalid("Usa un concepto breve de una a tres palabras, sin nombres ni instrucciones.")
    bank = language._catalog()
    if bank is None:
        raise _invalid("El diccionario de órdenes no está disponible en este momento.")
    words = set(key.split())
    reserved = _NON_CONCEPTS | set(bank["greetings"]) | {
        word for group in bank["verbs"].values() for phrase in group for word in phrase
    }
    if words & reserved or any(word in {"gica", "jica", "yica", "yika", "llica", "ilica", "chica"} for word in words):
        raise _invalid("La asociación debe ser un concepto, sin verbos, nombres de Gica ni controles.")
    # Reviewed vocabulary decides all negations, quotes, unsafe input and
    # protected resources. Ambiguous destinations may be explicitly assigned
    # by their human owner, but not silently inferred from external content.
    try:
        language.validate_pattern_phrase(alias, intent)
    except ValueError as error:
        raise _invalid() from error
    base = language.interpret(alias)
    if base["status"] != "clarify" or social_language.resolve(alias) is not None:
        raise _invalid()
    return key


def try_learn(actor, text):
    """Auto-activate a deliberate human definition; never execute its target."""
    definition = parse_teaching(text)
    if definition is None:
        return None
    alias, target = definition
    canonical = language.interpret(target)
    if canonical["status"] != "understood" or canonical["action"] not in CANONICAL_COMMANDS or canonical["query"]:
        raise _invalid("Indica una sola función existente: calendario, directorio, eventos, modo claro u oscuro.")
    intent = canonical["action"]
    key = _concept_key(alias, intent)
    # Ordinary conversation and invalid definitions must remain read-only SQL,
    # without creating even a transaction/savepoint. Lock only a valid teaching.
    return _store_alias(actor, alias, key, intent)


@transaction.atomic
def _store_alias(actor, alias, key, intent):
    # Lazy import avoids a cycle with the ordinary command resolver.
    from .local_commands import human_organizer

    current = human_organizer(actor, lock=True)
    manual = CommandPattern.objects.filter(owner=current, normalized_phrase=key).first()
    if manual is not None:
        raise _invalid("Ese concepto ya tiene una asociación revisada. Puedes cambiarla en la memoria.")
    existing = LearnedAlias.objects.filter(owner=current, normalized_key=key).first()
    if existing is not None:
        if existing.status == "disabled":
            raise _invalid("Esa asociación está desactivada. Puedes revisarla y reactivarla en la memoria.")
        if existing.intent != intent:
            raise _invalid("Ese concepto ya tiene otro significado. Revísalo en la memoria antes de cambiarlo.")
        return existing
    if LearnedAlias.objects.filter(owner=current).count() >= ALIAS_LIMIT:
        raise _invalid("Alcanzaste el límite de 100 asociaciones. Elimina alguna en la memoria antes de añadir otra.")
    entry = LearnedAlias(
        owner=current,
        alias=unicodedata.normalize("NFC", alias),
        normalized_key=key,
        intent=intent,
        status="auto",
    )
    entry.full_clean()
    entry.save()
    return entry


def _strip_phrases(words, phrases, *, end=False):
    """Trim only finite reviewed wrappers, bounded by the original word count."""
    for _ in range(len(words)):
        matching = next((phrase for phrase in phrases if (
            tuple(words[-len(phrase):] if end else words[:len(phrase)]) == phrase
        )), None)
        if matching is None:
            break
        words = words[:-len(matching)] if end else words[len(matching):]
    return words


def resolve_alias(actor, text):
    """Resolve only a complete exact concept or reviewed wrapper around it.

    The caller must retain priority for a pending person-name/theme slot. This
    service never consumes an arbitrary name or changes a search's arguments.
    """
    from .local_commands import human_organizer

    current = human_organizer(actor)
    base = language.interpret(text)
    if base["status"] != "clarify":
        return None
    try:
        language.command_pattern_key(text)
        normalized = language.normalize_pattern_phrase(text)
    except ValueError:
        return None
    bank = language._catalog()
    if bank is None:
        return None
    # Punctuation cannot join fragments into a new action. Commas/exclamation
    # marks are allowed only because wrappers still have to match in full.
    if re.search(r"[^\w\s,¡!.]", normalized) or any(char.isdigit() for char in normalized):
        return None
    words = re.sub(r"[,¡!.]", " ", normalized).split()
    words = _strip_phrases(words, bank["prefixes"])
    words = _strip_phrases(words, bank["suffixes"], end=True)
    verbs = tuple(sorted(
        bank["verbs"]["open"] + bank["verbs"]["theme"], key=lambda phrase: (-len(phrase), phrase)
    ))
    verb = next((phrase for phrase in verbs if tuple(words[:len(phrase)]) == phrase), None)
    if verb:
        words = words[len(verb):]
        words = _strip_phrases(words, bank["middle_fillers"])
        words = _strip_phrases(words, bank["determiners"])
    key = " ".join(words)
    entry = LearnedAlias.objects.filter(
        owner=current, normalized_key=key, status__in=("auto", "reviewed"),
    ).first()
    if entry is None:
        return None
    try:
        if _concept_key(entry.alias, entry.intent) != entry.normalized_key:
            return None
        language.validate_pattern_phrase(text, entry.intent)
    except (ValueError, ValidationError):
        return None
    result = language.interpret(CANONICAL_COMMANDS[entry.intent])
    if result["status"] != "understood" or result["action"] != entry.intent or result["query"]:
        return None
    return result
