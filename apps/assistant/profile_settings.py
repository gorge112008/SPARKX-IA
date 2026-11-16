"""Closed presentation catalog. No prompts, tools, provider or permission settings."""

from .models import GicaProfile


PERSONALITIES = {
    "friendly": "Te acompaña con un saludo cercano y preguntas claras.",
    "professional": "Te recibe con un tono formal y orientado a la gestión.",
    "direct": "Va al siguiente paso con un saludo breve.",
}


def profile_for(user):
    """Read-only defaults: rendering a page never creates a profile row."""
    values = {"personality": "friendly", "appearance": "ocean"}
    if user and getattr(user, "is_authenticated", False) and getattr(user, "is_active", False):
        saved = GicaProfile.objects.filter(owner_id=user.pk).values("personality", "appearance").first()
        if saved:
            if saved["personality"] in GicaProfile.Personality.values:
                values["personality"] = saved["personality"]
            if saved["appearance"] in GicaProfile.Appearance.values:
                values["appearance"] = saved["appearance"]
    return {
        **values,
        "name": "Gica-1",
        "personality_label": GicaProfile.Personality(values["personality"]).label,
        "appearance_label": GicaProfile.Appearance(values["appearance"]).label,
        "description": PERSONALITIES[values["personality"]],
    }


def greeting_for(personality, name, *, has_draft=False):
    """Authored greeting used by the profile preview; mirrors the voice catalog."""
    safe_name = str(name).strip()
    if not (1 <= len(safe_name) <= 60) or any(char in safe_name for char in "<>\r\n"):
        safe_name = ""
    prefix = f"Hola, {safe_name}." if safe_name else "Hola. Soy Gica."
    if personality == "professional":
        if safe_name and not has_draft:
            prefix += " Soy Gica."
        suffix = (" Tu borrador está disponible. Puedes continuar respondiendo o usar Continuar mi borrador."
                  if has_draft else " ¿Deseas crear un evento o realizar otra gestión?")
    elif personality == "direct":
        suffix = (" Tu borrador está listo para continuar. Responde o usa Continuar mi borrador."
                  if has_draft else " ¿Creamos un evento o hacemos otra tarea?")
    else:
        suffix = (" Tu borrador sigue disponible. Puedes continuar respondiendo o usar Continuar mi borrador."
                  if has_draft else " ¿Estás listo para crear un evento o deseas hacer otra cosa?")
    return prefix + suffix

