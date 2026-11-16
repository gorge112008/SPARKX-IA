"""Bounded grammar-token normalization, never a name or an executable rule.

The caller selects grammar spans only after checking the original request.
Edits are measured against each original token; fixed-point passes cannot build
an unbounded correction chain or modify the offsets used for a raw name slice.
"""

from dataclasses import dataclass
import re
import unicodedata


_CONCEPTS = {
    "calendar": ("calendario", 2), "events": ("eventos", 1),
    "directory": ("directorio", 2), "contacts": ("contactos", 1),
    "people": ("personas", 1), "theme": ("tema", 0), "mode": ("modo", 0),
    "light": ("claro", 1), "dark": ("oscuro", 1),
}
_LIMITS = {
    "max_passes": 3, "max_tokens": 80, "max_token_length": 32, "max_distance": 2,
    "distance_one_min_length": 5, "distance_two_min_length": 9,
}
_SCOPE_DETERMINERS = {
    "los": "el", "las": "la", "mis": "mi", "nuestros": "nuestro", "nuestras": "nuestra",
}
_GRAMMAR_VARIANTS = {
    "vista": {"vista", "vistas"}, "lista": {"lista", "listas"},
    "listado": {"listado", "listados"}, "agenda": {"agenda", "agendas"},
    "repositorio": {"repositorio", "repositorios"}, "seccion": {"seccion", "secciones"},
    "modulo": {"modulo", "modulos"}, "panel": {"panel", "paneles"},
    "gestor": {"gestor", "gestores"}, "programa": {"programa", "programas"},
    "programacion": {"programacion", "programaciones"},
    "cronograma": {"cronograma", "cronogramas"},
}


@dataclass(frozen=True)
class NormalizedTokens:
    tokens: tuple
    ambiguous: bool = False
    bounded: bool = True
    passes: int = 0


def fold(word):
    return "".join(
        char for char in unicodedata.normalize("NFKD", word).casefold()
        if not unicodedata.combining(char)
    )


def compile_rules(data, *, version):
    """Validate reviewed concept classes; the JSON cannot add an action/verb kind."""
    if (
        not isinstance(data, dict)
        or set(data) != {"catalog_version", "language", "limits", "concepts",
                         "scope_determiners", "verb_variants", "grammar_variants"}
        or data["catalog_version"] != version or data["language"] != "es"
        or data["limits"] != _LIMITS or data["scope_determiners"] != _SCOPE_DETERMINERS
        or not isinstance(data["concepts"], dict) or set(data["concepts"]) != set(_CONCEPTS)
    ):
        raise ValueError("Invalid normalization schema")
    aliases, concepts = {}, {}
    for name, (canonical, max_distance) in _CONCEPTS.items():
        spec = data["concepts"][name]
        if (
            not isinstance(spec, dict) or set(spec) != {"canonical", "variants", "max_distance"}
            or spec["canonical"] != canonical or type(spec["max_distance"]) is not int
            or spec["max_distance"] != max_distance or not isinstance(spec["variants"], list)
            or not 1 <= len(spec["variants"]) <= 8
        ):
            raise ValueError("Invalid normalization concept")
        variants = []
        for word in spec["variants"]:
            if not isinstance(word, str) or not re.fullmatch(r"[a-z]{4,32}", word):
                raise ValueError("Invalid nominal variant")
            if word in aliases or word in variants:
                raise ValueError("Overlapping nominal variants")
            variants.append(word)
        if canonical not in variants:
            raise ValueError("Missing canonical noun")
        for word in variants:
            aliases[word] = canonical
        concepts[canonical] = {"variants": tuple(variants), "max_distance": max_distance}
    grammar = data["grammar_variants"]
    if not isinstance(grammar, dict) or set(grammar) != set(_GRAMMAR_VARIANTS):
        raise ValueError("Invalid grammar noun classes")
    for canonical, forms in grammar.items():
        if (
            not isinstance(forms, list) or any(not isinstance(form, str) for form in forms)
            or len(forms) != len(set(forms)) or set(forms) != _GRAMMAR_VARIANTS[canonical]
        ):
            raise ValueError("Unreviewed grammatical variant")
        aliases.update({form: canonical for form in forms})
    verbs = data["verb_variants"]
    if not isinstance(verbs, dict) or set(verbs) != {"open", "search", "theme"}:
        raise ValueError("Invalid verb classes")
    compiled_verbs = {}
    for kind, mapping in verbs.items():
        if not isinstance(mapping, dict) or not 1 <= len(mapping) <= 8:
            raise ValueError("Invalid verb inflections")
        compiled_verbs[kind] = {}
        for canonical, forms in mapping.items():
            if not re.fullmatch(r"[a-z]{2,20}", canonical) or not isinstance(forms, list):
                raise ValueError("Invalid canonical verb")
            if not 1 <= len(forms) <= 8 or any(
                not isinstance(form, str) or not re.fullmatch(r"[a-z]{3,24}", form)
                for form in forms
            ):
                raise ValueError("Invalid verb variant")
            compiled_verbs[kind][canonical] = tuple(forms)
    return {
        "aliases": aliases, "concepts": concepts, "limits": dict(_LIMITS),
        "scope_determiners": dict(_SCOPE_DETERMINERS), "verb_variants": compiled_verbs,
    }


def _distance(left, right, cap=2):
    """Restricted Damerau distance: adjacent transpositions count once."""
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    previous = list(range(len(right) + 1))
    older = None
    for index, char in enumerate(left, 1):
        current = [index]
        for other, target in enumerate(right, 1):
            cost = char != target
            value = min(current[-1] + 1, previous[other] + 1, previous[other - 1] + cost)
            if older is not None and other > 1 and char == right[other - 2] and left[index - 2] == target:
                value = min(value, older[other - 2] + 1)
            current.append(value)
        older, previous = previous, current
    return previous[-1]


def canonical_word(word, rules, *, strong_context=False, fuzzy=True, scope=False):
    """Return (canonical, ambiguous); this function must never receive a name slot."""
    word = fold(word)
    if scope and word in rules["scope_determiners"]:
        return rules["scope_determiners"][word], False
    if word in rules["aliases"]:
        return rules["aliases"][word], False
    limits = rules["limits"]
    if not fuzzy or not limits["distance_one_min_length"] <= len(word) <= limits["max_token_length"]:
        return word, False
    matches = []
    for canonical, concept in rules["concepts"].items():
        maximum = concept["max_distance"]
        if maximum == 0:
            continue
        for variant in concept["variants"]:
            distance = _distance(word, variant, maximum)
            if not 1 <= distance <= maximum:
                continue
            if distance == 2 and not (
                strong_context and min(len(word), len(variant)) >= limits["distance_two_min_length"]
            ):
                continue
            matches.append((distance, canonical))
    if not matches:
        return word, False
    best = min(distance for distance, canonical in matches)
    choices = {canonical for distance, canonical in matches if distance == best}
    return (choices.pop(), False) if len(choices) == 1 else (word, True)


def normalize_tokens(tokens, rules, *, strong_context=False, fuzzy=True, scope=False):
    """Reach a bounded fixed point while retaining original start/end positions."""
    original = tuple(tokens)
    if len(original) > rules["limits"]["max_tokens"]:
        return NormalizedTokens(original, bounded=False)
    if any(
        not isinstance(token, tuple) or len(token) != 3 or not isinstance(token[0], str)
        or type(token[1]) is not int or type(token[2]) is not int
        or not 0 <= token[1] <= token[2] <= 300
        for token in original
    ):
        return NormalizedTokens(original, bounded=False)
    current, ambiguous = original, False
    for turn in range(1, rules["limits"]["max_passes"] + 1):
        following = []
        for word, start, end in original:
            canonical, uncertain = canonical_word(
                word, rules, strong_context=strong_context, fuzzy=fuzzy, scope=scope
            )
            ambiguous |= uncertain
            following.append((canonical, start, end))
        following = tuple(following)
        if following == current:
            return NormalizedTokens(following, ambiguous=ambiguous, passes=turn)
        current = following
    return NormalizedTokens(current, ambiguous=ambiguous, passes=rules["limits"]["max_passes"])
