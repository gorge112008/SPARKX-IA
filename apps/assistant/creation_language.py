"""Bounded Spanish slots for event creation; no database, models or services.

These helpers interpret explicit input. They never supply a missing date, time
period or field value, and cannot grant permissions or create an event.
"""

from datetime import date, timedelta
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata


_SECRET = re.compile(
    r"(?:\b(?:sk|gsk)[-_][A-Za-z0-9_-]{12,}|\bAIza[A-Za-z0-9_-]{20,}|"
    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----|\bbearer\s+\S+|"
    r"\b(?:api[_ -]?key|password|contrasena|clave\s+(?:api|secreta))\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


def clean_text(text, *, max_length=300):
    """Preserve original field spelling, including literal HTML, as plain data."""
    if not isinstance(text, str) or not isinstance(max_length, int) or not 1 <= max_length <= 300:
        raise ValueError("invalid_text")
    value = unicodedata.normalize("NFC", text)
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("invalid_text")
    value = value.strip()
    if not value or len(value) > max_length:
        raise ValueError("invalid_text")
    if _SECRET.search(_fold(value)):
        raise ValueError("secret_not_allowed")
    return value


def _fold(text):
    return "".join(
        character for character in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(character) != "Mn"
    )


def _normalized(text):
    return re.sub(r"\s+", " ", _fold(clean_text(text))).strip()


_CREATION_PATH = Path(__file__).with_name("data") / "gica_creation.es.json"
_CREATION_VERSION = "creation-keywords-es-2026-11-16.3"


def _lexemes(values, *, keep_accents=False):
    if type(values) is not list or not 1 <= len(values) <= 100:
        raise ValueError("invalid_creation_lexicon")
    result = set()
    for value in values:
        if not isinstance(value, str) or not 1 <= len(value) <= 80:
            raise ValueError("invalid_creation_lexicon")
        folded = _fold(value)
        if not re.fullmatch(r"[a-z]+", folded):
            raise ValueError("invalid_creation_lexicon")
        result.add(unicodedata.normalize("NFC", value).casefold() if keep_accents else folded)
    return frozenset(result)


def _alternatives(values):
    return "(?:" + "|".join(re.escape(value) for value in sorted(values, key=lambda item: (-len(item), item))) + ")"


@lru_cache(maxsize=1)
def _creation_catalog():
    """Single-word concepts only: no sentence templates or request grammar."""
    try:
        raw = _CREATION_PATH.read_bytes()
        if not 0 < len(raw) <= 32768:
            return None
        data = json.loads(raw.decode("utf-8"))
        if type(data) is not dict or set(data) != {"version", "language", "actions", "objects", "start_aliases", "guards"}:
            return None
        if data["version"] != _CREATION_VERSION or data["language"] != "es":
            return None
        if type(data["actions"]) is not dict or set(data["actions"]) != {"crear", "organizar", "armar", "preparar"}:
            return None
        actions = {lemma: _lexemes(forms) for lemma, forms in data["actions"].items()}
        action_words = frozenset().union(*actions.values())
        objects = data["objects"]
        if type(objects) is not dict or not 1 <= len(objects) <= 20 or any(not isinstance(key, str) for key in objects):
            return None
        nouns = frozenset().union(*(_lexemes(values) for values in objects.values()))
        guards = data["guards"]
        if type(guards) is not dict or set(guards) != {"negations", "conditions", "reports", "meta", "administrative", "other_actions", "coordinators"}:
            return None
        folded_guards = {key: _lexemes(value) for key, value in guards.items()}
        # Past accented forms (creé/creó) must not turn into present commands
        # (cree/creo) after accent folding. Preserve that distinction in guards.
        reports = _lexemes(guards["reports"], keep_accents=True)
        infinitives = _alternatives(actions.keys())
        return {
            "version": data["version"], "actions": action_words, "objects": nouns,
            "aliases": _lexemes(data["start_aliases"]), "guards": folded_guards,
            "reports": re.compile(r"\b" + _alternatives(reports) + r"\b", re.IGNORECASE),
            "joined_article": re.compile(r"\b(?P<verb>" + infinitives + r")(?P<article>una|un|unos|unas)(?=\s+" + _alternatives(nouns) + r"\b)"),
        }
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, re.error):
        return None


def is_creation_request(text):
    """An action keyword AND an event-type keyword open the interview only.

    Order, surrounding words and distance are irrelevant. Context guards can
    decline a negated/quoted/conflicting request; no accepted sentence is stored.
    Active interview fields do not call this recognizer and stay literal data.
    """
    try:
        original = clean_text(text)
    except ValueError:
        return False
    catalog = _creation_catalog()
    if catalog is None:
        return False
    if catalog["reports"].search(original):
        return False
    # Affirmative «sí» is not the conditional «si». This normalization is local
    # to intent detection; clean_text() still preserves all field spelling.
    original = re.sub(r"\bsí\b|\bsi(?=\s*,)", "afirmativo", original, flags=re.IGNORECASE)
    value = _fold(original)
    if re.search(r"[\"'«»“”;:\n]", value):
        return False
    value = catalog["joined_article"].sub(r"\g<verb> \g<article>", value)
    words = re.findall(r"\w+", value)
    present = set(words)
    action_words = catalog["actions"] | catalog["aliases"]
    action_positions = [index for index, word in enumerate(words) if word in action_words]
    object_positions = [index for index, word in enumerate(words) if word in catalog["objects"]]
    if not action_positions or not object_positions:
        return False
    guards = catalog["guards"]
    if present & (guards["negations"] | guards["meta"] | guards["administrative"] | guards["other_actions"]):
        return False
    # Conditional framing before the action is different from scheduling data
    # after it. «sin presupuesto» and «ya podemos» do not negate creation.
    before_action = set(words[:action_positions[0]])
    if before_action & guards["conditions"] or {"tal", "vez"} <= present or {"en", "caso"} <= before_action:
        return False
    if any(words[index] == "sin" and 0 < action - index <= 2
           and (index + 1 == len(words) or words[index + 1] not in {"duda", "problema"})
           for action in action_positions for index in range(action)):
        return False
    # Two event types are fine in a description («evento de conferencias»).
    # A coordinated second target needs clarification, not an implicit choice.
    for first, second in zip(object_positions, object_positions[1:]):
        middle = words[first + 1:second]
        coordinators = [index for index, word in enumerate(middle) if word in guards["coordinators"]]
        if coordinators and not set(middle[coordinators[-1] + 1:]) & {"de", "del", "para", "sobre"}:
            return False
    return True


_UNITS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3,
    "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21,
    "veintiun": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}
_TENS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
         "setenta": 70, "ochenta": 80, "noventa": 90}
_HUNDREDS = {"cien": 100, "ciento": 100, "doscientos": 200,
             "trescientos": 300, "cuatrocientos": 400, "quinientos": 500,
             "seiscientos": 600, "setecientos": 700, "ochocientos": 800,
             "novecientos": 900}


def _small_number(value):
    if value in _UNITS:
        return _UNITS[value]
    if value in _TENS:
        return _TENS[value]
    if value in _HUNDREDS:
        return _HUNDREDS[value]
    parts = value.split(" ", 1)
    if len(parts) == 2 and parts[0] in _HUNDREDS and parts[0] != "cien":
        remainder = _small_number(parts[1])
        if 0 < remainder < 100:
            return _HUNDREDS[parts[0]] + remainder
    parts = value.split(" y ")
    if len(parts) == 2 and parts[0] in _TENS and 0 < _UNITS.get(parts[1], 0) < 10:
        return _TENS[parts[0]] + _UNITS[parts[1]]
    raise ValueError("invalid_integer")


def _number(value):
    if re.fullmatch(r"[0-9]{1,6}", value):
        return int(value)
    parts = value.split(" mil ") if " mil " in value else None
    if value == "mil":
        return 1000
    if value.startswith("mil "):
        return 1000 + _small_number(value[4:])
    if value.endswith(" mil"):
        return _small_number(value[:-4]) * 1000
    if parts and len(parts) == 2:
        thousands, remainder = _small_number(parts[0]), _small_number(parts[1])
        if 0 < thousands <= 100 and 0 < remainder < 1000:
            return thousands * 1000 + remainder
        raise ValueError("invalid_integer")
    return _small_number(value)


def parse_integer(text, *, min_value=0, max_value=100000):
    """Parse a bounded whole number; units of hours are deliberately unsupported."""
    if (type(min_value) is not int or type(max_value) is not int
            or not 0 <= min_value <= max_value <= 100000):
        raise ValueError("invalid_integer_bounds")
    value = _normalized(text).rstrip(".")
    value = re.sub(r"^(?:seran|son|para|unos|unas) ", "", value)
    value = re.sub(r"\s*(?:personas|participantes|invitados|asistentes|cupos|minutos?)$", "", value)
    number = _number(value)
    if not min_value <= number <= max_value:
        raise ValueError("integer_out_of_range")
    return number


_MONTHS = {name: number for number, name in enumerate((
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
), 1)}
_MONTHS["setiembre"] = 9


def parse_date(text, *, reference_date=None):
    """Return ISO date. Relative dates require an explicit caller-supplied day."""
    value = _normalized(text).rstrip(".")
    value = re.sub(r"^(?:(?:sera|seria|es) (?:el )?|para (?:el )?|el )", "", value)
    relative = {"hoy": 0, "manana": 1, "pasado manana": 2}
    if value in relative:
        if type(reference_date) is not date:
            raise ValueError("explicit_reference_date_required")
        try:
            return (reference_date + timedelta(days=relative[value])).isoformat()
        except OverflowError as error:
            raise ValueError("invalid_date") from error
    match = re.fullmatch(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})", value)
    if match:
        year, month, day = map(int, match.groups())
    else:
        match = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", value)
        if match:
            day, month, year = map(int, match.groups())
        else:
            match = re.fullmatch(r"(.+?) de ([a-z]+) (?:de |del )?(.+)", value)
            if not match or match[2] not in _MONTHS:
                raise ValueError("invalid_date")
            day = 1 if match[1] == "primero" else parse_integer(match[1], min_value=1, max_value=31)
            month = _MONTHS[match[2]]
            year = parse_integer(match[3], min_value=1900, max_value=9999)
    try:
        return date(year, month, day).isoformat()
    except (ValueError, OverflowError) as error:
        raise ValueError("invalid_date") from error


def parse_time(text):
    """Return HH:MM, requiring a period for ambiguous spoken 1..12-hour times."""
    value = _normalized(text).rstrip(".")
    value = re.sub(r"^(?:(?:sera|seria|es) )?(?:a las?|las?) ", "", value)
    period_match = re.search(r"\s*(a\.?\s*m\.?|p\.?\s*m\.?|de la manana|de la tarde|de la noche|de madrugada)$", value)
    period = ""
    if period_match:
        period = period_match[1].replace(".", "").replace(" ", "")
        value = value[:period_match.start()].strip()
    if value in {"mediodia", "medianoche"} and not period:
        return "12:00" if value == "mediodia" else "00:00"
    value = re.sub(r"\s+horas?$", "", value)
    numeric = re.fullmatch(r"([0-9]{1,2}):([0-9]{2})", value)
    explicit_24h = bool(numeric and (len(numeric[1]) == 2 or int(numeric[1]) > 12))
    if numeric:
        hour, minute = int(numeric[1]), int(numeric[2])
    else:
        parts = value.split(" y ")
        if len(parts) > 2:
            raise ValueError("invalid_time")
        hour = parse_integer(parts[0], min_value=0, max_value=23)
        minute_text = parts[1] if len(parts) == 2 else "cero"
        if minute_text in {"media", "cuarto"}:
            minute = 30 if minute_text == "media" else 15
        else:
            minute = parse_integer(minute_text, min_value=0, max_value=59)
        explicit_24h = hour == 0 or hour > 12
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("invalid_time")
    if period:
        if not 1 <= hour <= 12:
            raise ValueError("invalid_time_period")
        hour %= 12
        if period in {"pm", "delatarde", "delanoche"}:
            hour += 12
    elif not explicit_24h:
        raise ValueError("ambiguous_time_period")
    return f"{hour:02}:{minute:02}"


def parse_bool(text):
    """Recognize a single yes/no answer with a small polite frame."""
    value = _normalized(text)
    value = re.sub(r"[¡!¿?.,]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    positive = r"(?:si|claro|correcto|de acuerdo|afirmativo)"
    negative = r"(?:no|negativo)"
    polite = r"(?:por favor|gracias|muchas gracias|esta bien|eso esta bien)"
    if re.fullmatch(rf"{positive}(?: (?:{positive}|{polite}))*", value):
        return True
    if re.fullmatch(rf"{negative}(?: {polite})*", value):
        return False
    raise ValueError("ambiguous_confirmation")
