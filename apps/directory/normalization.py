"""One search normalization, never an automatic person-identity match."""
import unicodedata

from django.core.exceptions import ValidationError


def search_key(value):
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", str(value)))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).casefold().split())


def normalize_aliases(values):
    """Reviewed alternate names, never inferred or expanded automatically."""
    if not isinstance(values, list) or len(values) > 12:
        raise ValidationError({"aliases": "Usa hasta 12 nombres alternativos o siglas."})
    result, keys = [], []
    for value in values:
        if not isinstance(value, str) or any(unicodedata.category(c).startswith("C") for c in value):
            raise ValidationError({"aliases": "Cada alias debe ser texto sin caracteres de control."})
        value = " ".join(value.split())
        key = search_key(value)
        if not value or len(value) > 160 or len(key) > 320:
            raise ValidationError({"aliases": "Cada alias necesita entre 1 y 160 caracteres."})
        if key not in keys:
            result.append(value)
            keys.append(key)
    # Newlines cannot occur inside a normalized key: delimit exact matches for
    # SQLite/PostgreSQL without relying on unsupported JSON containment lookups.
    return result, "\n" + "\n".join(keys) + "\n" if keys else ""
