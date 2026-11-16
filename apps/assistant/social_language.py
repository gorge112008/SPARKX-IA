"""Finite local social language: no contacts, actions, storage or AI providers.

Responses come from a reviewed local bank. A person's validated name may appear
only in its greeting template. Time is deliberately left to the caller's clock.
"""

from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from apps.jobs import command_language


BANK_PATH = Path(__file__).with_name("data") / "gica_social.es.json"
CATALOG_VERSION = "social-es-2026-11-15.4"
_ALIASES = frozenset({"gica", "jica", "yica", "yika", "llica", "ilica", "chica"})
_AGENT_TOKENS = _ALIASES | frozenset(f"{alias}-1" for alias in _ALIASES)
_GROUPS = {"greetings": "greeting", "time": "time"}
_GUARDS = frozenset({"negations", "conditions", "reported", "multiple", "person_blocked"})
_WRAPPERS = frozenset({
    "prefixes", "suffixes", "time_verbs", "time_targets", "greeting_fillers",
})
_PERSON_VOCABULARY = frozenset({"verbs", "direct_verbs", "nouns", "introducers"})
_CONCEPT_FIELDS = {
    "greeting": {
        "hello", "good", "day", "afternoon", "night", "fused_day", "fused_afternoon",
        "fused_night", "generic", "emphasis", "hello_reply", "day_reply", "afternoon_reply",
        "night_reply", "generic_reply",
    },
    "gratitude": {
        "nouns", "verbs", "giving_verbs", "pronouns", "articles", "intensifiers",
        "reason_markers", "help", "read_infinitives", "objects", "benefit", "function_words",
        "reply", "declined_reply",
    },
    "acknowledgement": {"tokens", "spelled", "state_verbs", "state", "reply"},
    "reciprocity": {
        "heads", "markers", "pronouns", "same", "article", "return_markers", "return_objects",
        "negative", "existence", "relative", "problem", "without", "reply", "return_reply",
    },
    "politeness": {
        "requests", "favor", "favor_markers", "permission", "permission_markers", "apologies",
        "apology_objects", "sorrow_verbs", "articles", "friendly", "degree", "reply",
        "apology_reply", "gratitude_reply",
    },
    "wellbeing": {"question_heads", "pronouns", "verbs", "state", "quantifiers", "reply"},
    "farewell": {
        "tokens", "until", "times", "next", "see_pronouns", "see_verbs", "articles", "reply",
    },
    "context": {"discourse", "emphasis", "emphasis_markers", "softeners", "decline", "accept"},
    "typos": {"eligible", "excluded", "max_distance", "max_token_length"},
}
_CONTROL = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_GREETING_REPLIES = frozenset({
    "Buenos días.", "Buenas tardes.", "Buenas noches.", "Hola.", "Buenas.",
})
_TOKEN = re.compile(r"[^\s¿?¡!.,:;]+", re.UNICODE)
_ALLOWED_PUNCTUATION = frozenset(" ¿?¡!.,:;-'")


def _fold(text):
    return "".join(
        char for char in unicodedata.normalize("NFKD", text).casefold()
        if not unicodedata.combining(char)
    )


def _tokens(text):
    return [(_fold(match.group()), match.start(), match.end())
            for match in _TOKEN.finditer(text)]


def _key(text):
    return tuple(token[0] for token in _tokens(text))


def _safe_text(text, limit=300):
    if not isinstance(text, str) or not 1 <= len(text) <= limit:
        return False
    if any(
        unicodedata.category(char) in _CONTROL
        or not (char.isalnum() or unicodedata.category(char).startswith("M")
                or char in _ALLOWED_PUNCTUATION)
        for char in text
    ):
        return False
    # Apostrophes inside a surname are allowed; quotation marks are not.
    return not re.search(r"(?<!\w)'|'(?!\w)|(?:https?|mailto|javascript|data):|www\.",
                         text, flags=re.IGNORECASE)


def _object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate social catalogue key")
    return result


def _reject_constant(value):
    raise ValueError("Non-finite social catalogue value")


def _phrases(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 80:
        raise ValueError("Invalid social vocabulary")
    phrases = []
    for value in values:
        if not _safe_text(value, 80) or not re.fullmatch(r"[\w '-]+", value):
            raise ValueError("Invalid social phrase")
        phrase = _key(value)
        if not phrase or phrase in phrases:
            raise ValueError("Duplicate social phrase")
        phrases.append(phrase)
    return tuple(sorted(phrases, key=lambda phrase: (-len(phrase), phrase)))


def _reply(value, *, empty=False):
    if value == "" and empty:
        return value
    if not _safe_text(value, 280):
        raise ValueError("Invalid social reply")
    return value


def _compile_concepts(data):
    if not isinstance(data, dict) or set(data) != set(_CONCEPT_FIELDS):
        raise ValueError("Invalid social concepts")
    compiled = {}
    for family, fields in _CONCEPT_FIELDS.items():
        values = data[family]
        if not isinstance(values, dict) or set(values) != fields:
            raise ValueError("Invalid social concept schema")
        concept = {}
        for key, value in values.items():
            if key == "reply" or key.endswith("_reply"):
                concept[key] = _reply(value)
            elif key in {"max_distance", "max_token_length"}:
                expected = 1 if key == "max_distance" else 32
                if type(value) is not int or value != expected:
                    raise ValueError("Invalid typo bound")
                concept[key] = value
            else:
                phrases = _phrases(value)
                if any(len(phrase) != 1 for phrase in phrases):
                    raise ValueError("Social concepts must contain individual lexemes")
                concept[key] = frozenset(phrase[0] for phrase in phrases)
        compiled[family] = concept
    typos = compiled["typos"]
    if typos["eligible"] != {"gracias", "agradezco"} or "gracia" not in typos["excluded"]:
        raise ValueError("Unreviewed typo target")
    for key in ("hello_reply", "day_reply", "afternoon_reply", "night_reply", "generic_reply"):
        if compiled["greeting"][key] not in _GREETING_REPLIES:
            raise ValueError("Unreviewed greeting reply")
    if compiled["acknowledgement"]["spelled"] != {"o", "k"}:
        raise ValueError("Unreviewed acknowledgement spelling")
    return compiled


def _greeting_patterns(concept):
    patterns = {(word,): concept["hello_reply"] for word in concept["hello"]}
    for word in concept["generic"]:
        patterns[(word,)] = concept["generic_reply"]
        for emphasis in concept["emphasis"]:
            patterns[(emphasis, word)] = concept["generic_reply"]
    for period in ("day", "afternoon", "night"):
        reply = concept[period + "_reply"]
        for head in concept[period]:
            for modifier in concept["good"]:
                patterns[(modifier, head)] = reply
        for fused in concept["fused_" + period]:
            patterns[(fused,)] = reply
    return patterns


@lru_cache(maxsize=1)
def _catalog():
    """Compile only bounded data; missing or malformed vocabulary fails closed."""
    try:
        raw = BANK_PATH.read_text(encoding="utf-8")
        if len(raw) > 16000:
            return None
        bank = json.loads(raw, object_pairs_hook=_object, parse_constant=_reject_constant)
        if (
            not isinstance(bank, dict)
            or set(bank) != {
                "catalog_version", "language", "agent_aliases", "person_greeting", "guards",
                "wrappers", "social_concepts", "composition", "time",
            }
            or bank["catalog_version"] != CATALOG_VERSION or bank["language"] != "es"
            or {_fold(alias) for alias in bank["agent_aliases"]} != _ALIASES
        ):
            return None
        _phrases(bank["agent_aliases"])
        concepts = _compile_concepts(bank["social_concepts"])
        groups = {"greetings": _greeting_patterns(concepts["greeting"])}
        for group in ("time",):
            entries, compiled = bank[group], {}
            if not isinstance(entries, list) or not 1 <= len(entries) <= 10:
                return None
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {"phrases", "reply"}:
                    return None
                reply = _reply(entry["reply"], empty=group == "time")
                if group == "greetings" and reply not in _GREETING_REPLIES:
                    return None
                if group == "time" and reply != "":
                    return None
                for phrase in _phrases(entry["phrases"]):
                    if phrase in compiled:
                        return None
                    compiled[phrase] = reply
            groups[group] = compiled
        person = bank["person_greeting"]
        if not isinstance(person, dict) or set(person) != _PERSON_VOCABULARY | {
            "reply_template", "missing_reply"
        }:
            return None
        template = person["reply_template"]
        if not isinstance(template, str) or template.count("{person_name}") != 1:
            return None
        _reply(template.replace("{person_name}", "Nombre"))
        guards = bank["guards"]
        if not isinstance(guards, dict) or set(guards) != _GUARDS:
            return None
        compiled_guards = {key: _phrases(values) for key, values in guards.items()}
        if not {("no",), ("nunca",), ("jamas",)}.issubset(compiled_guards["negations"]):
            return None
        wrappers = bank["wrappers"]
        if not isinstance(wrappers, dict) or set(wrappers) != _WRAPPERS:
            return None
        compiled_wrappers = {key: _phrases(values) for key, values in wrappers.items()}
        if compiled_wrappers["greeting_fillers"] != (("o",),):
            return None
        blocked_wrappers = sum(
            (compiled_guards[key] for key in ("negations", "conditions", "reported", "multiple")),
            (),
        )
        if any(
            _contains(phrase, blocked_wrappers)
            for key in ("prefixes", "suffixes", "time_verbs")
            for phrase in compiled_wrappers[key]
        ):
            return None
        composition = bank["composition"]
        if (
            not isinstance(composition, dict)
            or set(composition) != {"max_parts", "connectors"}
            or type(composition["max_parts"]) is not int or composition["max_parts"] != 3
            or set(_phrases(composition["connectors"])) != {("y",), ("e",)}
        ):
            return None
        return {
            "groups": groups,
            "person": {key: _phrases(person[key]) for key in _PERSON_VOCABULARY},
            "person_template": template,
            "missing_reply": _reply(person["missing_reply"]),
            "guards": compiled_guards,
            "wrappers": compiled_wrappers,
            "concepts": concepts,
            "composition": {"max_parts": 3, "connectors": frozenset({"y", "e"})},
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _without_leading_agent(tokens):
    if tokens and tokens[0][0] in _AGENT_TOKENS:
        size = 2 if len(tokens) > 1 and tokens[1][0] in {"uno", "1"} else 1
        return tokens[size:]
    return tokens


def _without_agent(tokens):
    tokens = _without_leading_agent(tokens)
    if tokens and tokens[-1][0] in {"uno", "1"} and len(tokens) > 1:
        if tokens[-2][0] in _ALIASES:
            return tokens[:-2]
    if tokens and tokens[-1][0] in _AGENT_TOKENS:
        return tokens[:-1]
    return tokens


def _leading_greeting(tokens, bank):
    # An agent vocative may also precede a greeting, but never a person's slot.
    tokens = _without_leading_agent(tokens)
    for phrase in sorted(bank["groups"]["greetings"], key=len, reverse=True):
        if tuple(token[0] for token in tokens[:len(phrase)]) == phrase:
            rest = tokens[len(phrase):]
            rest = _without_leading_agent(rest)
            return bank["groups"]["greetings"][phrase], rest
    return "", tokens


def _contains(words, phrases):
    return any(words[index:index + len(phrase)] == phrase
               for phrase in phrases for index in range(len(words)))


def _result(kind, reply, person_name=""):
    if len(reply) > 280:
        return None
    return {"kind": kind, "reply": reply, "person_name": person_name}


def _safe_name(name):
    if not 1 <= len(name) <= 80 or not name[0].isalpha():
        return False
    if not (name[-1].isalpha() or unicodedata.category(name[-1]).startswith("M")):
        return False
    return not re.search(r"[ '-]{2}", name) and all(
        unicodedata.category(char).startswith(("L", "M")) or char in " '-"
        for char in name
    )


def _consume_front(tokens, phrases):
    words = tuple(token[0] for token in tokens)
    phrase = next((phrase for phrase in phrases if words[:len(phrase)] == phrase), None)
    return (tokens[len(phrase):], True) if phrase else (tokens, False)


def _strip_wrappers(tokens, bank):
    """Remove reviewed edge grammar only, never a substring or interior name."""
    while tokens:
        rest, matched = _consume_front(tokens, bank["wrappers"]["prefixes"])
        if not matched:
            break
        tokens = rest
    while tokens:
        words = tuple(token[0] for token in tokens)
        suffix = next(
            (phrase for phrase in bank["wrappers"]["suffixes"]
             if len(phrase) <= len(words) and words[-len(phrase):] == phrase),
            None,
        )
        if suffix is None:
            break
        tokens = tokens[:-len(suffix)]
    return tokens


def _exact_social(tokens, bank, greeting=""):
    words = tuple(token[0] for token in _without_agent(tokens))
    for group, kind in _GROUPS.items():
        if words in bank["groups"][group]:
            reply = bank["groups"][group][words]
            return _result(kind, " ".join(part for part in (greeting, reply) if part))
    return None


def _form(words, *roles):
    return len(words) == len(roles) and all(word in role for word, role in zip(words, roles))


def _social_words(tokens, bank):
    """Discard only edge vocatives and concept-level discourse/emphasis."""
    words = tuple(token[0] for token in _without_agent(tokens))
    context = bank["concepts"]["context"]
    for _ in range(3):
        previous = words
        if words and words[0] in context["discourse"] | context["softeners"]:
            words = words[1:]
        if words and words[-1] in context["softeners"]:
            words = words[:-1]
        if len(words) >= 2 and _form(
            words[:2], context["emphasis_markers"], context["emphasis"]
        ):
            words = words[2:]
        if len(words) >= 2 and _form(
            words[-2:], context["emphasis_markers"], context["emphasis"]
        ):
            words = words[:-2]
        words = tuple(token[0] for token in _without_agent([(word, 0, 0) for word in words]))
        if words == previous:
            break
    return words


def _one_edit(left, right):
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1
    short, long = (left, right) if len(left) < len(right) else (right, left)
    index = next((index for index, pair in enumerate(zip(short, long)) if pair[0] != pair[1]),
                 len(short))
    return short[index:] == long[index + 1:]


def _nucleus(word, bank):
    gratitude = bank["concepts"]["gratitude"]
    if word in gratitude["nouns"] | gratitude["verbs"]:
        return word, False, False
    typos = bank["concepts"]["typos"]
    if word in typos["excluded"] or not 5 <= len(word) <= typos["max_token_length"]:
        return None
    collapsed = re.sub(r"(.)\1+", r"\1", word)
    if collapsed != word and collapsed in typos["eligible"]:
        return collapsed, True, True
    matches = [candidate for candidate in typos["eligible"] if _one_edit(word, candidate)]
    return (matches[0], True, False) if len(matches) == 1 else None


def _benefit_context(words, concept):
    if not words:
        return False
    allowed = (
        concept["reason_markers"] | concept["help"] | concept["read_infinitives"]
        | concept["objects"] | concept["benefit"] | concept["function_words"]
        | concept["intensifiers"]
    )
    if not all(word in allowed for word in words):
        return False
    read_verbs = [word for word in words if word in concept["read_infinitives"]]
    if read_verbs:
        # A gratitude reason may refer to an action; a leading command may not.
        content = [word for word in words if word not in (
            concept["reason_markers"] | concept["function_words"] | concept["intensifiers"]
        )]
        return (
            words[0] in concept["reason_markers"] and len(read_verbs) == 1
            and len(content) >= 2 and content[0] in concept["read_infinitives"]
            and all(word in concept["objects"] for word in content[1:])
        )
    return any(
        word in concept["help"] | concept["read_infinitives"] | concept["benefit"]
        for word in words
    )


def _gratitude_atom(words, bank):
    concept = bank["concepts"]["gratitude"]
    context = bank["concepts"]["context"]
    nuclei = [(index, _nucleus(word, bank)) for index, word in enumerate(words)]
    nuclei = [(index, match) for index, match in nuclei if match is not None]
    if len(nuclei) != 1:
        return None
    index, (nucleus, corrected, repeated) = nuclei[0]
    prefix, suffix = words[:index], words[index + 1:]
    declined = bool(prefix and prefix[0] in context["decline"])
    accepted = bool(prefix and prefix[0] in context["accept"])
    if declined or accepted:
        # A polite 'no, gracias' is not 'no te doy las gracias' or a condition.
        if (
            nucleus not in concept["nouns"] or (declined and suffix)
            or any(word not in concept["intensifiers"] for word in prefix[1:])
        ):
            return None
        prefix = prefix[1:]
    if sum(word in concept["intensifiers"] for word in (*prefix, *suffix)) > 2:
        return None
    frame = concept["pronouns"] | concept["articles"] | concept["intensifiers"]
    if nucleus in concept["nouns"]:
        frame |= concept["giving_verbs"]
    if prefix and not (all(word in frame for word in prefix) or _benefit_context(prefix, concept)):
        return None
    if suffix:
        reason = suffix
        while reason and reason[0] in concept["intensifiers"]:
            reason = reason[1:]
        if reason and not (
            reason[0] in concept["reason_markers"] and _benefit_context(reason, concept)
        ):
            return None
    # A single edit needs a grammatical frame; repeated-letter errors are unambiguous.
    if corrected and not repeated and not (prefix or suffix):
        return None
    reply = concept["declined_reply"] if declined else concept["reply"]
    return _result("courtesy", reply)


def _concept_atom(words, bank):
    if not words:
        return None
    concepts = bank["concepts"]
    acknowledgement = concepts["acknowledgement"]
    if (
        (len(words) == 1 and words[0] in acknowledgement["tokens"])
        or words == ("o", "k")
        or _form(words, acknowledgement["state_verbs"], acknowledgement["state"])
    ):
        return _result("courtesy", acknowledgement["reply"])
    reciprocal = concepts["reciprocity"]
    recipient = (reciprocal["markers"], reciprocal["pronouns"])
    if (
        (len(words) == 1 and words[0] in reciprocal["heads"])
        or _form(words, *recipient)
        or _form(words, reciprocal["heads"], *recipient)
        or _form(words, *recipient, reciprocal["heads"])
        or _form(words, reciprocal["article"], reciprocal["same"], *recipient)
    ):
        return _result("courtesy", reciprocal["reply"])
    if (
        _form(words, reciprocal["return_markers"], reciprocal["return_objects"])
        or _form(words, reciprocal["negative"], reciprocal["existence"],
                 reciprocal["return_markers"], reciprocal["relative"])
        or _form(words, reciprocal["negative"], reciprocal["existence"], reciprocal["problem"])
        or _form(words, reciprocal["without"], reciprocal["problem"])
    ):
        return _result("courtesy", reciprocal["return_reply"])
    polite = concepts["politeness"]
    if (
        (len(words) == 1 and words[0] in polite["requests"] | polite["permission"])
        or _form(words, polite["favor_markers"], polite["favor"])
        or _form(words, polite["permission_markers"], polite["permission"])
    ):
        return _result("courtesy", polite["reply"])
    if (
        (len(words) == 1 and words[0] in polite["apologies"])
        or _form(words, polite["apologies"], polite["articles"], polite["apology_objects"])
        or _form(words, polite["articles"], polite["sorrow_verbs"])
    ):
        return _result("courtesy", polite["apology_reply"])
    if _form(words, polite["degree"], polite["friendly"]):
        return _result("courtesy", polite["gratitude_reply"])
    wellbeing = concepts["wellbeing"]
    if (
        _form(words, wellbeing["question_heads"], wellbeing["verbs"])
        or _form(words, wellbeing["question_heads"], wellbeing["pronouns"], wellbeing["verbs"])
        or _form(words, wellbeing["question_heads"], wellbeing["state"])
        or _form(words, wellbeing["quantifiers"], wellbeing["state"])
    ):
        return _result("wellbeing", wellbeing["reply"])
    farewell = concepts["farewell"]
    if (
        (len(words) == 1 and words[0] in farewell["tokens"])
        or (len(words) == 2 and words[0] == words[1] and words[0] in farewell["tokens"])
        or _form(words, farewell["until"], farewell["times"])
        or _form(words, farewell["until"], farewell["articles"], farewell["next"])
        or _form(words, farewell["see_pronouns"], farewell["see_verbs"])
    ):
        return _result("farewell", farewell["reply"])
    return _gratitude_atom(words, bank)


def _social_atom(tokens, bank):
    literal = _exact_social(tokens, bank)
    if literal is not None and literal["kind"] == "greeting":
        return literal
    return _concept_atom(_social_words(tokens, bank), bank)


def _social_sequence(tokens, bank):
    """Every token must belong to at most three complete social atoms.

    This branch cannot contain an action or a free-text person slot. In
    particular, 'no hay de qué' is an authored whole atom, never a removed 'no'.
    """
    if not tokens:
        return None

    @lru_cache(maxsize=None)
    def match(start, depth):
        for end in range(min(len(tokens), start + 16), start, -1):
            atom = _social_atom(tokens[start:end], bank)
            if atom is None:
                continue
            if end == len(tokens):
                return (atom,)
            if depth == bank["composition"]["max_parts"]:
                continue
            next_start = end
            if tokens[next_start][0] in bank["composition"]["connectors"]:
                next_start += 1
            if next_start < len(tokens):
                tail = match(next_start, depth + 1)
                if tail is not None:
                    return (atom, *tail)
        return None

    atoms = match(0, 1)
    if atoms is None:
        return None
    replies = list(dict.fromkeys(atom["reply"] for atom in atoms))
    return _result(atoms[-1]["kind"], " ".join(replies))


def _person_slot(tokens, bank):
    """Verb + greeting noun + introducer + one unmodified name slot."""
    vocabulary = bank["person"]
    rest, direct = _consume_front(tokens, vocabulary["direct_verbs"])
    if not direct:
        rest, verb = _consume_front(tokens, vocabulary["verbs"])
        rest, noun = _consume_front(rest if verb else tokens, vocabulary["nouns"])
        if not noun:
            return None
    if not rest:
        return []
    rest, introduced = _consume_front(rest, vocabulary["introducers"])
    return rest if introduced else None


def resolve(text):
    """Resolve only a whole social turn. Mixed commands remain command language."""
    if not _safe_text(text):
        return None
    bank = _catalog()
    if bank is None:
        return None
    text = unicodedata.normalize("NFC", text).strip()
    tokens = _tokens(text)
    literal = _exact_social(tokens, bank)
    if literal is not None:
        return literal
    sequence = _social_sequence(tokens, bank)
    if sequence is not None:
        return sequence
    # STT can prepend a literal 'O'. It is harmless only before a whole greeting.
    filler_rest, filler = _consume_front(tokens, bank["wrappers"]["greeting_fillers"])
    if filler:
        literal = _exact_social(filler_rest, bank)
        if literal is not None and literal["kind"] == "greeting":
            return literal
    words = tuple(token[0] for token in tokens)
    blocked = sum(
        (bank["guards"][key] for key in ("negations", "conditions", "reported", "multiple")),
        (),
    )
    # Check the original utterance before removing any polite/modal grammar.
    if _contains(words, blocked):
        return None
    core = _strip_wrappers(_without_leading_agent(tokens), bank)
    greeting, core = _leading_greeting(core, bank)
    core = _strip_wrappers(core, bank)
    if greeting and not core:
        return _result("greeting", greeting)
    literal = _exact_social(core, bank, greeting)
    if literal is not None:
        return literal
    time_rest, time_verb = _consume_front(core, bank["wrappers"]["time_verbs"])
    time_words = tuple(token[0] for token in _without_agent(time_rest))
    if time_verb and (
        time_words in bank["wrappers"]["time_targets"]
        or time_words in bank["groups"]["time"]
    ):
        return _result("time", greeting)
    # Do not strip a trailing agent alias: it can be the requested real name.
    name_tokens = _person_slot(core, bank)
    if name_tokens is None:
        return None
    if not name_tokens:
        reply = " ".join(part for part in (greeting, bank["missing_reply"]) if part)
        return _result("person_greeting", reply)
    name = text[name_tokens[0][1]:name_tokens[-1][2]]
    if (
        not _safe_name(name) or len(name_tokens) > 12
        or _contains(tuple(token[0] for token in name_tokens), bank["guards"]["person_blocked"])
    ):
        return None
    reply = bank["person_template"].replace("{person_name}", name)
    return _result("person_greeting", " ".join(part for part in (greeting, reply) if part), name)


def greet_only(text):
    """Whether the complete text is a greeting, without discarding a suffix."""
    result = resolve(text)
    return result is not None and result["kind"] == "greeting"


def greeting_prefix(text):
    """A finite greeting reply only before the same single understood command."""
    if not _safe_text(text):
        return ""
    bank = _catalog()
    if bank is None:
        return ""
    text = unicodedata.normalize("NFC", text).strip()
    greeting, rest = _leading_greeting(_tokens(text), bank)
    if not greeting or not rest:
        return ""
    complete = command_language.interpret(text)
    suffix = command_language.interpret(text[rest[0][1]:])
    if (
        complete["status"] == suffix["status"] == "understood"
        and complete["action"] == suffix["action"]
        and complete["query"] == suffix["query"]
    ):
        return greeting
    return ""
