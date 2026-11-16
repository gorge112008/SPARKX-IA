"""Short local transactions. Event -> User -> Page is the lock order.

PostgreSQL is required to verify concurrent capacity/closure behavior. SQLite
supports the local sequential prototype; it does not implement row locks.
"""
import uuid

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.access import can_organize, get_role
from apps.accounts.models import PortalAccount
from apps.events.models import Event
from .models import Registration, RegistrationPage, RegistrationSubmission
from .normalization import registration_values

FORM_SALT = "sparkx.event-registration.v1"
FORM_MAX_AGE = 2 * 60 * 60
RECEIPT_MESSAGE = (
    "Solicitud recibida. Si las inscripciones estaban abiertas y había cupo, "
    "se conservó una inscripción por correo. No se envían correos de confirmación. "
    "El organizador puede consultar el registro."
)


class RegistrationConflict(ValidationError):
    """The organizer must reload the current publication before acting."""


def _current_actor(actor, *, public=False):
    if not actor or not getattr(actor, "is_authenticated", False):
        if public:
            return None
        raise PermissionDenied("Inicia sesión para gestionar las inscripciones.")
    current = get_user_model().objects.select_for_update().filter(pk=actor.pk).first()
    if not current or not current.is_active:
        raise PermissionDenied("La cuenta ya no tiene acceso.")
    if get_role(current) == PortalAccount.Role.REVIEWER:
        raise PermissionDenied("El rol Revisor no permite gestionar ni enviar inscripciones.")
    if not public and not can_organize(current):
        raise PermissionDenied("No tienes permiso para gestionar las inscripciones.")
    return current


def _same_plan(expected_plan, current_plan):
    if expected_plan in (None, ""):
        return current_plan is None
    try:
        return uuid.UUID(str(expected_plan)) == current_plan
    except (ValueError, TypeError, AttributeError):
        return False


@transaction.atomic
def set_registration_state(*, event_id, actor, action, expected_version,
                           expected_revision, expected_plan, confirmed):
    event = Event.objects.select_for_update().get(pk=event_id)
    current = _current_actor(actor)
    if event.owner_id != current.pk:
        raise PermissionDenied("No tienes acceso a este evento.")
    if action not in {RegistrationPage.State.OPEN, RegistrationPage.State.CLOSED} or confirmed is not True:
        raise ValidationError("Confirma explícitamente la apertura o el cierre de inscripciones.")
    page = RegistrationPage.objects.select_for_update().filter(event=event).first()
    version = page.version if page else 0
    if (type(expected_version) is not int or expected_version != version
            or type(expected_revision) is not int or expected_revision != event.revision
            or not _same_plan(expected_plan, event.active_plan_id)):
        raise RegistrationConflict("El evento o las inscripciones cambiaron. Recarga y revisa antes de confirmar.")
    if action == RegistrationPage.State.OPEN:
        if not event.active_plan_id or not event.plan_revisions.filter(pk=event.active_plan_id).exists():
            raise ValidationError("Aprueba un plan de este evento antes de abrir las inscripciones.")
        if page is None:
            page = RegistrationPage.objects.create(
                event=event, state=RegistrationPage.State.OPEN, published_plan_id=event.active_plan_id,
                updated_by=current, opened_at=timezone.now(),
            )
            return page
    elif page is None:
        raise ValidationError("Este evento todavía no publicó una página de inscripción.")
    # A new approved plan pauses admission until the organizer explicitly
    # republishes it, even when the page's stored state is already OPEN.
    republishing = action == RegistrationPage.State.OPEN and page.published_plan_id != event.active_plan_id
    # Repeating the current command with the current version has no new effect.
    if page.state == action and not republishing:
        return page
    page.state = action
    page.version += 1
    page.updated_by = current
    if action == RegistrationPage.State.OPEN:
        page.published_plan_id = event.active_plan_id
        page.opened_at = timezone.now()
        page.closed_at = None
    else:
        page.closed_at = timezone.now()
    page.save(update_fields=["state", "version", "updated_by", "published_plan", "opened_at", "closed_at"])
    # Event.revision and Event.active_plan are deliberately untouched.
    return page


def submission_token(page):
    """Create an expiring form key in memory. A GET does not reserve a seat."""
    return signing.dumps({"page": page.pk, "version": page.version, "key": str(uuid.uuid4())}, salt=FORM_SALT)


def _read_submission_token(value, page_id):
    try:
        payload = signing.loads(value, salt=FORM_SALT, max_age=FORM_MAX_AGE)
        if (not isinstance(payload, dict) or payload.get("page") != page_id
                or type(payload.get("version")) is not int):
            raise ValueError
        return uuid.UUID(payload["key"]), payload["version"]
    except (signing.BadSignature, TypeError, ValueError, KeyError, AttributeError) as error:
        raise ValidationError("El formulario venció o no es válido. Recarga la página e inténtalo de nuevo.") from error


@transaction.atomic
def submit_registration(*, token, full_name, email, form_token, actor=None):
    name, normalized_email = registration_values(full_name, email)
    # Resolve by the opaque token only. There is no public event-ID lookup/list.
    page_ref = RegistrationPage.objects.only("pk", "event_id").get(public_token=token)
    request_key, form_version = _read_submission_token(form_token, page_ref.pk)
    event = Event.objects.select_for_update().get(pk=page_ref.event_id)
    _current_actor(actor, public=True)
    page = RegistrationPage.objects.select_for_update().get(pk=page_ref.pk)
    if RegistrationSubmission.objects.filter(page=page, request_key=request_key).exists():
        return RECEIPT_MESSAGE
    # Commit the consumed key together with any seat. Reusing a key with other
    # data never changes a previous registration or creates a second one.
    RegistrationSubmission.objects.create(page=page, request_key=request_key)
    if (page.state != RegistrationPage.State.OPEN or page.version != form_version
            or not event.active_plan_id or page.published_plan_id != event.active_plan_id):
        return RECEIPT_MESSAGE
    if Registration.objects.filter(event=event, email=normalized_email).exists():
        return RECEIPT_MESSAGE
    # Count ACTIVE records inside the Event transaction and lock, shared with
    # publication/closure and normal event edits. Never count directory contacts.
    active_count = Registration.objects.filter(event=event, status=Registration.Status.ACTIVE).count()
    if active_count < event.capacity:
        Registration.objects.create(event=event, full_name=name, email=normalized_email)
    # Full, closed, duplicate and accepted all return the same public message.
    return RECEIPT_MESSAGE


def availability(event):
    active = Registration.objects.filter(event=event, status=Registration.Status.ACTIVE).count()
    return {"active": active, "capacity": event.capacity, "remaining": max(0, event.capacity - active)}
