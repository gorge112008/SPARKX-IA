"""A finite Spanish command grammar, independent of HTTP, ORM and AI providers.

The JSON bank contains vocabulary only. It never supplies executable patterns,
URLs, selectors or permission decisions. An interpretation is not execution.
"""

from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from . import command_normalization as normalization

ACTION_IDS = frozenset({"theme_light", "theme_dark", "calendar_open", "directory_open", "people_search", "events_open"})
BANK_PATH = Path(__file__).with_name("data") / "romeo_intents.es.json"
_TOKEN = re.compile(r"[^\s,;:!?¿¡.()\"“”«»]+")
_UNSAFE_TEXT = re.compile(r"[<>\\/{}\[\]`]|\b(?:https?|ftp|file|data|javascript|mailto):|www\.", re.IGNORECASE)
_QUOTED = re.compile(r"[\"“”«»]|(?<!\w)'|'(?!\w)")
_LIST_KEYS = frozenset({
    "prefixes", "suffixes", "middle_fillers", "determiners", "search_introducers",
    "search_scopes", "negations", "conditional_terms", "reported_phrases",
    "information_phrases", "refused_terms", "filter_terms", "ambiguous_targets",
    "search_placeholders",
})
_CONTROL_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_REQUIRED_NEGATIONS = frozenset({("no",), ("nunca",), ("jamas",), ("tampoco",), ("ni",)})
_AGENT_NAMES = frozenset({"gica", "jica", "yica", "yika", "llica", "ilica", "chica"})
_AGENT_TOKENS = _AGENT_NAMES | frozenset(f"{name}-1" for name in _AGENT_NAMES)
_MODULE_FILES = {
    "vocabulary": "gica_vocabulary.es.json",
    "intents": "gica_intents.es.json",
    "dialogues": "gica_dialogues.es.json",
    "normalization": "gica_normalization.es.json",
}
_DIALOGUE_KEYS = frozenset({
    "clarify", "multiple", "conditional", "information", "missing_person",
    "unsupported_filters", "single_person", "person_length", "ambiguous_agenda",
    "negation", "quoted", "reported", "restricted", "unsafe", "invalid_text",
})


def _fold(value):
    return "".join(char for char in unicodedata.normalize("NFKD", value).casefold() if not unicodedata.combining(char))


def _phrase(value):
    return tuple(_fold(value).split())


def _vocabulary(values, *, empty=False):
    if not isinstance(values, list) or (not values and not empty) or len(values) > 100:
        raise ValueError
    if any(not isinstance(value, str) or not 1 <= len(value) <= 80
           or not re.fullmatch(r"[\w '-]+", value, flags=re.UNICODE) for value in values):
        raise ValueError
    phrases = [_phrase(value) for value in values]
    if any(not phrase or len(phrase) > 8 for phrase in phrases) or len(set(phrases)) != len(phrases):
        raise ValueError
    return tuple(sorted(phrases, key=lambda item: (-len(item), item)))


def _json_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate catalogue key")
    return result


def _reject_constant(value):
    raise ValueError("Non-finite catalogue value")


def _read_catalogue(path):
    text = path.read_text(encoding="utf-8")
    if len(text) > 30000:
        raise ValueError("Catalogue module too large")
    return json.loads(text, object_pairs_hook=_json_object, parse_constant=_reject_constant)


def _plain_text(value, limit):
    return (
        isinstance(value, str) and 1 <= len(value) <= limit
        and not any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in value)
        and not re.search(r"[<>]", value)
    )


def _compile_catalogue(manifest, modules):
    vocabulary, intents, dialogues = (
        modules[key] for key in ("vocabulary", "intents", "dialogues")
    )
    rules = normalization.compile_rules(
        modules["normalization"], version=manifest["catalog_version"]
    )
    common = {"catalog_version", "language"}
    if (
        not isinstance(vocabulary, dict)
        or set(vocabulary) != _LIST_KEYS | common | {"verbs", "agent_aliases"}
        or not isinstance(intents, dict) or set(intents) != common | {"actions", "slots"}
        or not isinstance(dialogues, dict) or set(dialogues) != common | {"messages", "greetings"}
    ):
        raise ValueError("Invalid catalogue module schema")
    if any(
        module["language"] != "es" or module["catalog_version"] != manifest["catalog_version"]
        for module in modules.values()
    ):
        raise ValueError("Catalogue versions differ")
    if set(vocabulary["agent_aliases"]) != _AGENT_NAMES:
        raise ValueError("Unreviewed agent alias")
    _vocabulary(vocabulary["agent_aliases"])
    if intents["slots"] != {"person_name": {"kind": "person_name", "max_length": 100}}:
        raise ValueError("Unreviewed slot")
    if not isinstance(intents["actions"], dict) or set(intents["actions"]) != ACTION_IDS:
        raise ValueError("Unreviewed action")
    actions = {}
    for name, spec in intents["actions"].items():
        if (
            not isinstance(spec, dict) or set(spec) != {"label", "command", "targets", "slot"}
            or spec["slot"] != ("person_name" if name == "people_search" else None)
            or any(not _plain_text(spec[key], 100) for key in ("label", "command"))
        ):
            raise ValueError("Invalid intent")
        actions[name] = {
            "label": spec["label"], "command": spec["command"],
            "targets": tuple(sorted({
                tuple(normalization.canonical_word(word, rules, fuzzy=False)[0] for word in phrase)
                for phrase in _vocabulary(spec["targets"], empty=name == "people_search")
            }, key=lambda phrase: (-len(phrase), phrase))),
        }
    verbs = vocabulary["verbs"]
    if not isinstance(verbs, dict) or set(verbs) != {"open", "search", "theme"}:
        raise ValueError("Invalid verb categories")
    words = {key: _vocabulary(vocabulary[key]) for key in _LIST_KEYS}
    if not _REQUIRED_NEGATIONS.issubset(words["negations"]) or any(
        (word,) in words["negations"] for phrase in words["prefixes"] for word in phrase
    ):
        raise ValueError("Unsafe negation vocabulary")
    messages = dialogues["messages"]
    if (
        not isinstance(messages, dict) or set(messages) != _DIALOGUE_KEYS
        or any(not _plain_text(message, 500) for message in messages.values())
    ):
        raise ValueError("Invalid dialogue messages")
    compiled_verbs = {key: _vocabulary(value) for key, value in verbs.items()}
    for kind, forms in rules["verb_variants"].items():
        additions = []
        for canonical, variants in forms.items():
            if (canonical,) not in compiled_verbs[kind]:
                raise ValueError("Verb inflection has no reviewed base")
            for variant in variants:
                if any((variant,) in words[key] for key in (
                    "negations", "refused_terms", "conditional_terms"
                )):
                    raise ValueError("Unsafe verb inflection")
                additions.append((variant,))
        compiled_verbs[kind] = tuple(sorted(
            set(compiled_verbs[kind]) | set(additions), key=lambda phrase: (-len(phrase), phrase)
        ))
    return {
        "version": manifest["catalog_version"], "actions": actions,
        "verbs": compiled_verbs, **words,
        "dialogues": messages,
        "greetings": tuple(" ".join(phrase) for phrase in _vocabulary(dialogues["greetings"])),
        "slots": intents["slots"],
        "normalization": rules,
    }


@lru_cache(maxsize=1)
def _catalog():
    """Compile only fixed local modules; invalid/missing modules fail closed."""
    try:
        data = _read_catalogue(BANK_PATH)
        if (
            not isinstance(data, dict)
            or set(data) != {"catalog_version", "language", "limits", "modules"}
            or data["language"] != "es" or data["limits"] != {"command": 300, "query": 100}
            or data["modules"] != _MODULE_FILES
            or not isinstance(data["catalog_version"], str)
            or not re.fullmatch(r"es-[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]{1,3}", data["catalog_version"])
        ):
            return None
        modules = {
            key: _read_catalogue(BANK_PATH.with_name(filename))
            for key, filename in _MODULE_FILES.items()
        }
        return _compile_catalogue(data, modules)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _matches(tokens, phrase, start=0):
    return tuple(item[0] for item in tokens[start:start + len(phrase)]) == phrase


def _contains(tokens, phrases):
    return any(_matches(tokens, phrase, start) for start in range(len(tokens)) for phrase in phrases)


def _strip_front(tokens, phrases, *, once=False):
    while tokens:
        phrase = next((phrase for phrase in phrases if _matches(tokens, phrase)), None)
        if phrase is None:
            break
        tokens = tokens[len(phrase):]
        if once:
            break
    return tokens


def _strip_end(tokens, phrases, text, *, preserve_names=False):
    while tokens:
        removed = False
        for phrase in phrases:
            start = len(tokens) - len(phrase)
            if start < 0 or not _matches(tokens, phrase, start):
                continue
            # A surname such as Gracias or Romeo remains part of a search.
            agent_suffix = phrase[0] in _AGENT_TOKENS | {"romeo", "romeo-1"}
            if preserve_names and (
                agent_suffix or (len(phrase) == 1 and phrase[0] not in {"porfa", "porfis"})
            ):
                gap = text[tokens[start - 1][2]:tokens[start][1]] if start else ""
                if "," not in gap and ";" not in gap:
                    continue
            tokens = tokens[:start]
            removed = True
            break
        if not removed:
            break
    return tokens


def _verb(tokens, bank):
    choices = [(phrase, kind) for kind, phrases in bank["verbs"].items() for phrase in phrases]
    choices.sort(key=lambda item: -len(item[0]))
    return next(((kind, len(phrase)) for phrase, kind in choices if _matches(tokens, phrase)), (None, 0))


def _action_count(tokens, bank):
    total = 0
    while tokens:
        kind, size = _verb(tokens, bank)
        if kind:
            total += 1
            tokens = tokens[size:]
        else:
            tokens = tokens[1:]
    return total


def _mentions(tokens, bank, *, theme=False):
    # A complete target such as "calendario de eventos" is one destination,
    # while "calendario y eventos" still contains two independent destinations.
    choices = [
        (phrase, action)
        for action, spec in bank["actions"].items() for phrase in spec["targets"]
        if theme or len(phrase) > 1 or action not in {"theme_light", "theme_dark"}
    ]
    found, index = [], 0
    while index < len(tokens):
        matches = [(phrase, action) for phrase, action in choices if _matches(tokens, phrase, index)]
        if matches:
            size = max(len(phrase) for phrase, action in matches)
            found.extend(action for phrase, action in matches if len(phrase) == size)
            index += size
        else:
            index += 1
    return list(dict.fromkeys(found))


def _result(bank, status, message, *, action=None, query="", choices=()):
    options = [{"label": bank["actions"][name]["label"], "command": bank["actions"][name]["command"]}
               for name in dict.fromkeys(choices) if name in ACTION_IDS][:3] if bank else []
    return {"status": status, "action": action, "query": query, "message": message,
            "options": options, "catalog_version": bank["version"] if bank else "unavailable"}


def _clarify(bank, message=None, choices=None):
    message = message or bank["dialogues"]["clarify"]
    return _result(bank, "clarify", message, choices=("calendar_open", "directory_open", "events_open") if choices is None else choices)


def normalize_agent_vocative(command):
    """Canonicalize a finite edge vocative, never a person-search name or instruction."""
    if not isinstance(command, str) or len(command) > 300:
        return command
    text = unicodedata.normalize("NFC", command).strip()
    bank = _catalog()
    if (
        bank is None
        or _UNSAFE_TEXT.search(text)
        or _QUOTED.search(text)
        or any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in text)
    ):
        return text
    tokens = [(_fold(match.group()), match.start(), match.end()) for match in _TOKEN.finditer(text)]
    if not tokens:
        return text
    prefixes = tuple(
        phrase for phrase in bank["prefixes"]
        if not any(part in _AGENT_TOKENS for part in phrase)
    )
    front = _strip_front(tokens, prefixes)
    if front and front[0][0] in _AGENT_TOKENS:
        size = 2 if len(front) > 1 and front[1][0] in {"1", "uno"} else 1
        following = front[size:]
        # A bare surname after a spoken name is not a command or a vocative.
        if not following or _verb(following, bank)[0] or _mentions(following, bank, theme=True):
            return text[:front[0][1]] + "Gica" + text[front[size - 1][2]:]
    size = 2 if len(tokens) > 1 and tokens[-1][0] in {"1", "uno"} else 1
    last = tokens[-size]
    if last[0] in _AGENT_TOKENS and len(tokens) > size:
        gap = text[tokens[-size - 1][2]:last[1]]
        if ("," in gap or ";" in gap) and (
            _verb(tokens, bank)[0] or _mentions(tokens[:-1], bank, theme=True)
        ):
            return text[:last[1]] + "Gica" + text[tokens[-1][2]:]
    return text


def is_greeting(text):
    """Match only a bounded exact greeting/help phrase from the reviewed bank."""
    if (
        not isinstance(text, str) or len(text) > 300
        or any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in text)
        or _UNSAFE_TEXT.search(text) or _QUOTED.search(text)
    ):
        return False
    bank = _catalog()
    if bank is None:
        return False
    key = " ".join(_fold(re.sub(r"[¿?.,¡!;:]", "", text)).split())
    return key in bank["greetings"]


def _grammar_phrase(phrase, bank, *, scope=False):
    return tuple(normalization.canonical_word(
        word, bank["normalization"], fuzzy=False, scope=scope
    )[0] for word in phrase)


def _strip_search_scope(tokens, bank, *, end=False):
    """Normalize only a preposition-led scope span, leaving name tokens untouched."""
    for phrase in bank["search_scopes"]:
        size = len(phrase)
        if len(tokens) < size:
            continue
        candidate = tokens[-size:] if end else tokens[:size]
        if candidate[0][0] != phrase[0]:
            continue
        normalized = normalization.normalize_tokens(
            candidate, bank["normalization"], strong_context=True, scope=True
        )
        if normalized.ambiguous or not normalized.bounded:
            continue
        if tuple(token[0] for token in normalized.tokens) == _grammar_phrase(phrase, bank, scope=True):
            return (tokens[:-size] if end else tokens[size:]), True
    return tokens, False


def _strip_search_introducer(tokens, bank):
    for phrase in bank["search_introducers"]:
        if len(tokens) < len(phrase):
            continue
        candidate = tokens[:len(phrase)]
        # Number variants are grammar; spelling guesses here could alter a name.
        actual = _grammar_phrase(tuple(token[0] for token in candidate), bank)
        if actual == _grammar_phrase(phrase, bank):
            return tokens[len(phrase):], True
    return tokens, False


def _unresolved_search_scope(tokens, bank):
    determiners = {"el", "la", "los", "las", "mi", "mis", "nuestro", "nuestros",
                   "nuestra", "nuestras"}
    destinations = {"calendario", "eventos", "directorio", "contactos", "personas",
                    "agenda", "programa", "programacion", "cronograma"}
    for index, token in enumerate(tokens):
        if token[0] not in {"en", "de", "del"}:
            continue
        following = index + 1
        while following < len(tokens) and tokens[following][0] in determiners:
            following += 1
        if following < len(tokens):
            word, ambiguous = normalization.canonical_word(
                tokens[following][0], bank["normalization"], strong_context=True
            )
            if ambiguous or word in destinations:
                return True
    return False


def interpret(command):
    """Return one bounded intention or a non-executing clarification/refusal."""
    bank = _catalog()
    if bank is None:
        return _result(None, "refused", "El catálogo de órdenes no está disponible. Puedes navegar manualmente.")
    if not isinstance(command, str) or len(command) > 300 or any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in command):
        return _result(bank, "refused", bank["dialogues"]["invalid_text"])
    text = unicodedata.normalize("NFC", command).strip()
    if _UNSAFE_TEXT.search(text):
        return _result(bank, "refused", bank["dialogues"]["unsafe"])
    if _QUOTED.search(text):
        return _result(bank, "refused", bank["dialogues"]["quoted"])
    text = normalize_agent_vocative(text)
    tokens = [(_fold(match.group()), match.start(), match.end()) for match in _TOKEN.finditer(text)]
    if len(tokens) > bank["normalization"]["limits"]["max_tokens"]:
        return _result(bank, "refused", bank["dialogues"]["invalid_text"])
    if _contains(tokens, bank["refused_terms"]):
        return _result(bank, "refused", bank["dialogues"]["restricted"])
    if _contains(tokens, bank["reported_phrases"]):
        return _result(bank, "refused", bank["dialogues"]["reported"])
    if _contains(tokens, bank["conditional_terms"]):
        return _clarify(bank, bank["dialogues"]["conditional"], choices=())
    if _contains(tokens, bank["information_phrases"]):
        return _clarify(bank, bank["dialogues"]["information"])
    core = _strip_front(tokens, bank["prefixes"])
    kind, size = _verb(core, bank)
    fillers = bank["middle_fillers"]
    if kind == "search":
        # 'Este', 'Paz', etc. can be parts of names, not disposable filler.
        fillers = tuple(phrase for phrase in fillers if phrase in {("por", "favor"), ("porfa",), ("porfis",), ("no", "se")})
    rest = _strip_front(core[size:], fillers) if kind else core
    original_checked = core[:size] + rest if kind else core
    if _contains(original_checked, bank["negations"]):
        return _result(bank, "refused", bank["dialogues"]["negation"])
    if _action_count(original_checked, bank) > 1:
        return _clarify(bank, bank["dialogues"]["multiple"])
    explicit_name = False
    if kind == "search":
        # A scope is grammar only at a slot edge; never remove words inside a name.
        rest, _ = _strip_search_scope(rest, bank)
        rest = _strip_front(rest, fillers)
        rest, explicit_name = _strip_search_introducer(rest, bank)
        rest = _strip_end(rest, bank["suffixes"], text, preserve_names=True)
        rest, _ = _strip_search_scope(rest, bank, end=True)
        rest = _strip_end(rest, bank["suffixes"], text, preserve_names=True)
    # Hesitation 'no sé' is allowed only after an explicit main verb.
    checked = core[:size] + rest if kind else core
    if _contains(checked, bank["negations"]):
        return _result(bank, "refused", bank["dialogues"]["negation"])
    if _action_count(checked, bank) > 1:
        return _clarify(bank, bank["dialogues"]["multiple"])
    if kind == "search":
        if not rest or tuple(item[0] for item in rest) in bank["search_placeholders"]:
            return _clarify(bank, bank["dialogues"]["missing_person"], choices=())
        mentions = [] if explicit_name else _mentions(rest, bank)
        if _unresolved_search_scope(rest, bank) or mentions or _contains(rest, bank["filter_terms"]):
            return _clarify(bank, bank["dialogues"]["unsupported_filters"], choices=mentions or ("directory_open",))
        if _contains(rest, (("y",), ("o",), ("u",), ("e",))):
            return _clarify(bank, bank["dialogues"]["single_person"], choices=())
        query = text[rest[0][1]:rest[-1][2]].strip()
        if not 1 <= len(query) <= 100:
            return _clarify(bank, bank["dialogues"]["person_length"], choices=())
        return _result(bank, "understood", "Entendí: buscar ese nombre en tu directorio de personas.", action="people_search", query=query)
    target_core = _strip_front(_strip_end(rest, bank["suffixes"], text), bank["determiners"])
    isolated_target = kind is None and len(target_core) == 1
    normalized = normalization.normalize_tokens(
        rest, bank["normalization"],
        strong_context=kind in {"open", "theme"} or isolated_target,
    )
    if not normalized.bounded:
        return _result(bank, "refused", bank["dialogues"]["invalid_text"])
    if normalized.ambiguous:
        return _clarify(bank)
    rest = list(normalized.tokens)
    checked = core[:size] + rest if kind else rest
    mentions = _mentions(checked, bank, theme=kind == "theme")
    if _action_count(checked, bank) > 1 or len(mentions) > 1:
        return _clarify(bank, bank["dialogues"]["multiple"], choices=mentions or None)
    rest = _strip_end(rest, bank["suffixes"], text)
    rest = _strip_front(rest, bank["determiners"])
    if tuple(item[0] for item in rest) in {
        _grammar_phrase(phrase, bank) for phrase in bank["ambiguous_targets"]
    }:
        return _clarify(
            bank, bank["dialogues"]["ambiguous_agenda"], choices=("calendar_open", "events_open")
        )
    for action, spec in bank["actions"].items():
        for phrase in spec["targets"]:
            if _matches(rest, phrase) and len(rest) == len(phrase):
                if not kind and action in {"theme_light", "theme_dark"} and len(phrase) == 1:
                    return _clarify(bank, "¿Quieres activar modo claro u oscuro?", choices=("theme_light", "theme_dark"))
                return _result(bank, "understood", "Entendí: " + spec["label"] + ".", action=action)
    if mentions:
        return _clarify(bank, "Puedo abrir esa sección. Los filtros o detalles adicionales todavía deben seleccionarse allí. ¿Quieres abrirla?", choices=mentions)
    return _clarify(bank)


def normalize_pattern_phrase(command):
    """A bounded exact-match key, never a fuzzy interpretation or executable rule."""
    if not isinstance(command, str) or not 1 <= len(command) <= 300:
        raise ValueError("invalid_phrase")
    text = unicodedata.normalize("NFC", command).strip()
    normalized = re.sub(r"\s+", " ", _fold(text))
    if not normalized or len(normalized) > 300:
        raise ValueError("invalid_phrase")
    return normalized


def command_pattern_key(command):
    """Apply the finite bank's guardrails before either reading or saving memory."""
    normalized = normalize_pattern_phrase(command)
    bank = _catalog()
    if bank is None or any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in command):
        raise ValueError("unsafe_phrase")
    text = unicodedata.normalize("NFC", command).strip()
    if _UNSAFE_TEXT.search(text) or _QUOTED.search(text):
        raise ValueError("unsafe_phrase")
    tokens = [(_fold(match.group()), match.start(), match.end()) for match in _TOKEN.finditer(text)]
    blocked = (
        bank["negations"]
        + bank["conditional_terms"]
        + bank["reported_phrases"]
        + bank["information_phrases"]
        + bank["refused_terms"]
    )
    voice_controls = tuple(
        _phrase(value)
        for value in (
            "hablemos", "ejecuta", "ejecutar", "cancela", "cancelar", "silencio",
            "deja de escuchar", "instala", "instalar", "descarga", "descargar",
            "formatea", "formatear", "script", "comando",
        )
    )
    core = _strip_front(tokens, bank["prefixes"])
    if (
        not core
        or _contains(tokens, blocked + voice_controls)
        or tuple(item[0] for item in core) in {
            ("si",), ("sip",), ("yes",), ("ok",), ("okay",), ("bien",)
        }
        or _action_count(core, bank) > 1
    ):
        raise ValueError("unsafe_phrase")
    result = interpret(command)
    if result["status"] == "refused" or (
        result["status"] == "clarify" and _mentions(core, bank, theme=True)
    ):
        # A remembered alias cannot complete unsupported filters or resolve an
        # already ambiguous destination/theme on behalf of the human.
        raise ValueError("unsafe_phrase")
    return normalized


def validate_pattern_phrase(command, intent):
    """Validate an explicitly selected meaning without expanding the six actions."""
    if intent not in ACTION_IDS:
        raise ValueError("invalid_intent")
    normalized = command_pattern_key(command)
    result = interpret(command)
    if result["status"] == "understood" and result["action"] != intent:
        raise ValueError("intent_conflict")
    bank = _catalog()
    tokens = [
        (_fold(match.group()), match.start(), match.end()) for match in _TOKEN.finditer(command)
    ]
    kind, _ = _verb(_strip_front(tokens, bank["prefixes"]), bank)
    if result["status"] != "understood" and (
        (kind == "search" and intent != "people_search")
        or (kind == "theme" and intent not in {"theme_light", "theme_dark"})
    ):
        raise ValueError("intent_conflict")
    return normalized


def clarification_context(command):
    """A local follow-up slot, never conversation history or inferred authority."""
    bank = _catalog()
    result = interpret(command)
    if bank is None or result["status"] != "clarify" or not isinstance(command, str):
        return ""
    tokens = [
        (_fold(match.group()), match.start(), match.end()) for match in _TOKEN.finditer(command)
    ]
    core = _strip_front(tokens, bank["prefixes"])
    if _action_count(core, bank) > 1 or len(_mentions(core, bank, theme=True)) > 1:
        return ""
    kind, _ = _verb(core, bank)
    if kind == "search" and not _mentions(core, bank):
        return "person_name"
    if kind == "theme" or tuple(item[0] for item in core) in {("claro",), ("oscuro",)}:
        return "theme"
    return ""
