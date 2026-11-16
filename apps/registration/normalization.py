"""The same bounded normalization is used by forms and application commands."""
import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def registration_values(full_name, email):
    if not isinstance(full_name, str) or not isinstance(email, str):
        raise ValidationError("Escribe un nombre y un correo válidos.")
    name = " ".join(unicodedata.normalize("NFKC", full_name).split())
    normalized_email = unicodedata.normalize("NFKC", email).strip().casefold()
    if not name or len(name) > 120 or any(unicodedata.category(char).startswith("C") for char in name):
        raise ValidationError({"full_name": "Escribe un nombre de hasta 120 caracteres."})
    if not normalized_email or len(normalized_email) > 254:
        raise ValidationError({"email": "Escribe un correo válido de hasta 254 caracteres."})
    validate_email(normalized_email)
    return name, normalized_email
