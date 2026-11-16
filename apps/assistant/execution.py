"""Application-level agent provenance, not an operating-system sandbox.

Only the server enters this context. No prompt, tool parameter or user header can
clear it. Resetting nested contexts restores the previous execution identity.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


_agent_execution = ContextVar("sparkx_agent_execution", default=None)


def in_agent_execution():
    return _agent_execution.get() is not None


@contextmanager
def agent_execution(code="romeo-1"):
    if type(code) is not str or not code or len(code) > 64:
        raise ValueError("Falta una identidad válida del agente.")
    token = _agent_execution.set(code)
    try:
        yield
    finally:
        _agent_execution.reset(token)


def deny_agent_admin():
    if in_agent_execution():
        raise PermissionDenied("Un agente no puede acceder a la administración ni cambiar sus permisos o presupuesto.")


def require_human_superadmin(actor):
    """Re-query privilege; stale request objects cannot restore revoked access."""
    deny_agent_admin()
    if not actor or not getattr(actor, "pk", None):
        raise PermissionDenied("Esta operación requiere un superadministrador humano.")
    current = get_user_model().objects.filter(pk=actor.pk, is_active=True, is_superuser=True).first()
    if current is None:
        raise PermissionDenied("Esta operación requiere un superadministrador humano vigente.")
    return current
