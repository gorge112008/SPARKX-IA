"""Explicit, CSRF-protected browser intentions; no model or shell access."""

from datetime import timedelta
from uuid import UUID
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.access import can_organize
from apps.assistant.execution import in_agent_execution
from .models import UIAction


ACTION_TTL = timedelta(seconds=60)
ACTIVE_STATES = (UIAction.State.PENDING, UIAction.State.EXECUTING)
OUTCOMES = (UIAction.State.COMPLETED, UIAction.State.CANCELLED, UIAction.State.FAILED)


def _error(status, text):
    return JsonResponse({"error": text}, status=status)


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError
    return UUID(value)


def _query(action, value):
    if not isinstance(value, str) or any(
        unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value
    ):
        raise ValueError
    value = unicodedata.normalize("NFC", value).strip()
    if len(value) > 100 or (action == UIAction.Action.PEOPLE_SEARCH) != bool(value):
        raise ValueError
    return value


def _authority(request):
    """Called under a transaction: the user lock serializes per-actor actions."""
    if in_agent_execution():
        raise PermissionDenied
    actor = get_user_model().objects.select_for_update().only(
        "id", "is_active", "is_staff", "is_superuser",
    ).filter(pk=request.user.pk, is_active=True).first()
    session_key = getattr(request.session, "session_key", None)
    if actor is None or not can_organize(actor) or not session_key:
        raise PermissionDenied
    digest = salted_hmac("sparkx.romeo-ui-session.v1", session_key, algorithm="sha256").hexdigest()
    return actor, digest


def _payload(action):
    return {"id": str(action.pk), "action": action.action, "query": action.query, "state": action.state,
            "expires_at": action.expires_at.isoformat()}


def _expired(action, now):
    if action.state in ACTIVE_STATES and action.expires_at <= now:
        action.state = UIAction.State.EXPIRED
        action.save(update_fields=["state", "updated_at"])
        return True
    return action.state == UIAction.State.EXPIRED


def _create(actor, digest, tab_id, action_name, query, request_key, now):
    earlier = UIAction.objects.filter(actor=actor, request_key=request_key).first()
    if earlier is not None:
        if not constant_time_compare(earlier.session_digest, digest):
            return _error(403, "Acceso no permitido.")
        if earlier.action != action_name or earlier.query != query or earlier.tab_id != tab_id:
            return _error(409, "La solicitud ya tiene otra acción, búsqueda o pestaña.")
        _expired(earlier, now)
        return JsonResponse(_payload(earlier))
    UIAction.objects.filter(actor=actor, tab_id=tab_id, state__in=ACTIVE_STATES, expires_at__lte=now).update(
        state=UIAction.State.EXPIRED, updated_at=now,
    )
    if UIAction.objects.filter(actor=actor, tab_id=tab_id, state__in=ACTIVE_STATES).exists():
        return _error(409, "Esta pestaña ya tiene una acción pendiente.")
    action = UIAction.objects.create(
        actor=actor, request_key=request_key, tab_id=tab_id, session_digest=digest,
        action=action_name, query=query, expires_at=now + ACTION_TTL,
    )
    return JsonResponse(_payload(action), status=201)


def _transition(actor, digest, tab_id, action_id, operation, outcome, now):
    action = UIAction.objects.select_for_update().filter(pk=action_id, actor=actor).first()
    if action is None or action.tab_id != tab_id or not constant_time_compare(action.session_digest, digest):
        return _error(403, "Acceso no permitido.")
    if _expired(action, now):
        return _error(409, "La acción ha caducado.")
    if operation == "start":
        if action.state != UIAction.State.PENDING:
            return _error(409, "La acción ya no está pendiente.")
        action.state = UIAction.State.EXECUTING
    else:
        if action.state not in ACTIVE_STATES:
            if action.state == outcome:
                return JsonResponse(_payload(action))
            return _error(409, "La acción ya terminó con otro estado.")
        if outcome != UIAction.State.CANCELLED and action.state != UIAction.State.EXECUTING:
            return _error(409, "La acción todavía no se ha iniciado.")
        action.state = outcome
    action.save(update_fields=["state", "updated_at"])
    return JsonResponse(_payload(action))


def _handle(request, operation, action_id=None):
    try:
        tab_id = _uuid(request.POST.get("tab_id"))
        action_name = request.POST.get("action")
        request_key = _uuid(request.POST.get("request_key")) if operation == "create" else None
        outcome = request.POST.get("outcome")
        if operation == "create" and action_name not in UIAction.Action.values:
            raise ValueError
        query = _query(action_name, request.POST.get("query", "")) if operation == "create" else ""
        if operation == "finish" and outcome not in OUTCOMES:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        return _error(400, "Revisa los campos de la acción permitida.")
    try:
        with transaction.atomic():
            actor, digest = _authority(request)
            now = timezone.now()
            if operation == "create":
                return _create(actor, digest, tab_id, action_name, query, request_key, now)
            return _transition(actor, digest, tab_id, action_id, operation, outcome, now)
    except PermissionDenied:
        return _error(403, "Acceso no permitido.")
    except IntegrityError:
        # The database also enforces the single active action if writers race.
        return _error(409, "La solicitud entra en conflicto con otra acción.")


@never_cache
@login_required
@require_POST
def interpret(request):
    """Interpret human text locally; no receipts, jobs, tools or user-text storage."""
    if len(request.POST.getlist("command")) != 1:
        return _error(400, "Escribe una única orden.")
    try:
        with transaction.atomic():
            actor, _ = _authority(request)
    except PermissionDenied:
        return _error(403, "Acceso no permitido.")
    from apps.assistant.local_commands import interpret_for_owner
    try:
        result = interpret_for_owner(actor, request.POST["command"])
    except (ValueError, RuntimeError, OSError):
        return _error(503, "El catálogo de órdenes no está disponible. No se ejecutó ninguna acción.")
    return JsonResponse(result)


@never_cache
@login_required
@require_POST
def create(request):
    return _handle(request, "create")


@never_cache
@login_required
@require_POST
def start(request, action_id):
    return _handle(request, "start", action_id)


@never_cache
@login_required
@require_POST
def finish(request, action_id):
    return _handle(request, "finish", action_id)
