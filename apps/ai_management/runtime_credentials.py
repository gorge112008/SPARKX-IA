"""Process-local private credentials, with scoped references and revocation.

Only metadata leaves this module for presentation. No persistence, browser storage
or provider validation. Production multi-process workers require an external vault.
"""
from dataclasses import dataclass, field
import threading
import secrets
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.assistant.execution import require_human_superadmin

PROVIDERS = {"openai": "OpenAI", "groq": "Groq", "gemini": "Google Gemini"}
_lock = threading.RLock()


@dataclass(repr=False)
class _Credential:
    secret: str | None = field(repr=False)
    version: int
    changed_at: object
    reference: str
    expires_at: object


_entries = {}


def credential_status(owner_id, provider):
    with _lock:
        entry = _entries.get((owner_id, provider))
        if entry and entry.expires_at <= timezone.now():
            entry.secret = None
        setting = {"openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider)
        environment_available = bool(entry is None and setting and getattr(settings, setting, ""))
        return {"provider": provider, "name": PROVIDERS.get(provider, provider),
                "environment_available": environment_available,
                "managed": entry is not None, "available": bool(entry and entry.secret),
                "version": entry.version if entry else 0,
                "changed_at": entry.changed_at if entry else None,
                "reference": entry.reference if entry else None,
                "expires_at": entry.expires_at if entry else None}


@sensitive_variables()
def set_credential(*, actor, provider, secret):
    current = require_human_superadmin(actor)
    if provider not in PROVIDERS:
        raise ValidationError("El proveedor no admite claves en este panel.")
    if (type(secret) is not str or not 16 <= len(secret.strip()) <= 1024
            or any(ord(char) < 33 or ord(char) > 126 for char in secret.strip())):
        raise ValidationError("La clave requiere entre 16 y 1024 caracteres sin espacios ni saltos de línea.")
    with _lock:
        previous = _entries.get((current.pk, provider))
        now = timezone.now()
        _entries[(current.pk, provider)] = _Credential(secret.strip(), (previous.version if previous else 0) + 1, now,
            secrets.token_urlsafe(24), now + timedelta(hours=2))
    return credential_status(current.pk, provider)


def disconnect_credential(*, actor, provider):
    current = require_human_superadmin(actor)
    if provider not in PROVIDERS:
        raise ValidationError("El proveedor no está disponible.")
    with _lock:
        previous = _entries.get((current.pk, provider))
        # A tombstone overrides an inherited environment credential too.
        now = timezone.now()
        _entries[(current.pk, provider)] = _Credential(None, (previous.version if previous else 0) + 1, now,
            secrets.token_urlsafe(24), now)


@sensitive_variables()
def key_reference(snapshot, provider):
    """Return (managed, secret) only to the adapter; stale references fail closed."""
    if not isinstance(snapshot, dict) and not hasattr(snapshot, "get"):
        return False, ""
    owner_id = snapshot.get("credential_owner_id")
    with _lock:
        entry = _entries.get((owner_id, provider))
        if entry is None:
            if snapshot.get("credential_ref") or snapshot.get("credential_version", 0):
                return True, ""
            return False, ""
        # Managed API keys are available only through a server-issued agent grant.
        if (not snapshot.get("agent_grant_id") or snapshot.get("credential_version") != entry.version
                or snapshot.get("credential_ref") != entry.reference or entry.expires_at <= timezone.now()):
            return True, ""
        return True, entry.secret or ""
