"""Account commands serialize privileges without granting technical staff access.

Lock order: optional Event, then AdminRosterLock, then User rows by primary key,
then PortalAccount and assignment rows. Account changes never acquire Event locks.
PostgreSQL is required to verify the concurrent guarantees; SQLite is local only.
"""
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .access import can_organize, get_role, require_portal_admin
from .models import AdminRosterLock, EventReviewAssignment, PortalAccount


def normalize_identifier(value):
    return unicodedata.normalize("NFKC", value).strip().casefold() if isinstance(value, str) else ""


def _lock_roster():
    # Reads and requests must not silently create the global serialization row.
    return AdminRosterLock.objects.select_for_update().get(pk=1)


def _locked_users(*user_ids):
    users = get_user_model().objects.select_for_update().filter(pk__in=user_ids).order_by("pk")
    return {user.pk: user for user in users}


def _current_admin(actor, users):
    current = users.get(getattr(actor, "pk", None))
    require_portal_admin(current)
    return current


def _validate_identity(*, email, username):
    if not isinstance(email, str) or not email.strip() or len(email.strip()) > 254:
        raise ValidationError({"email": "Introduce un correo de acceso válido."})
    email = normalize_identifier(email)
    validate_email(email)
    username = email if username is None else username
    if not isinstance(username, str) or not username.strip() or len(username.strip()) > 150:
        raise ValidationError({"email" if username == email else "username": "El identificador de acceso admite hasta 150 caracteres."})
    username = unicodedata.normalize("NFKC", username).strip()
    identifiers = {normalize_identifier(username), normalize_identifier(email)}
    # Email on the legacy Django User is not unique. Check both namespaces and
    # Unicode casefold explicitly; iexact varies across SQLite/PostgreSQL locales.
    for old_username, old_email in get_user_model().objects.values_list("username", "email"):
        old_identifiers = {normalize_identifier(value) for value in (old_username, old_email) if value}
        if identifiers & old_identifiers:
            raise ValidationError("El correo o identificador ya pertenece a otra cuenta.", code="duplicate_identity")
    return email, username


def _validate_role(role):
    if role not in PortalAccount.Role.values:
        raise ValidationError({"role": "Selecciona un rol válido."})


@transaction.atomic
def create_portal_user(*, actor, full_name, email, role, password, username=None):
    _lock_roster()
    current = _current_admin(actor, _locked_users(getattr(actor, "pk", None)))
    _validate_role(role)
    if not isinstance(full_name, str) or not full_name.strip() or len(full_name.strip()) > 150:
        raise ValidationError({"full_name": "Introduce un nombre de hasta 150 caracteres."})
    email, username = _validate_identity(email=email, username=username)
    if not isinstance(password, str) or not 16 <= len(password) <= 128:
        raise ValidationError({"password": "Usa una contraseña de entre 16 y 128 caracteres."})
    user = get_user_model()(username=username, email=email, first_name=full_name.strip(),
                            is_active=True, is_staff=False, is_superuser=False)
    validate_password(password, user=user)
    user.set_password(password)
    user.full_clean()
    try:
        with transaction.atomic():
            user.save(force_insert=True)
    except IntegrityError as error:
        raise ValidationError("El identificador ya pertenece a otra cuenta.", code="duplicate_identity") from error
    PortalAccount.objects.create(user=user, role=role, must_change_password=True)
    return user


@transaction.atomic
def update_portal_user(*, actor, user_id, expected_version, role, is_active):
    _lock_roster()
    users = _locked_users(getattr(actor, "pk", None), user_id)
    current = _current_admin(actor, users)
    target = users.get(user_id)
    if target is None:
        raise get_user_model().DoesNotExist
    if target.is_staff or target.is_superuser:
        raise PermissionDenied("Las cuentas técnicas protegidas se administran fuera de este módulo.")
    _validate_role(role)
    if type(is_active) is not bool or type(expected_version) is not int or expected_version < 1:
        raise ValidationError("Falta un estado o versión de usuario válido.")
    profile = PortalAccount.objects.select_for_update().filter(user=target).first()
    version = profile.version if profile else 1
    if expected_version != version:
        raise ValidationError("La cuenta cambió en otra pestaña. Recarga antes de guardar.", code="stale_user")
    previous_role = get_role(target)
    changed = role != previous_role or is_active != target.is_active
    if not changed:
        return target
    if target.pk == current.pk and (role != PortalAccount.Role.ADMIN or not is_active):
        raise PermissionDenied("No puedes desactivar tu cuenta ni retirar tu propio rol de administrador.")
    if target.is_active and previous_role == PortalAccount.Role.ADMIN and (not is_active or role != PortalAccount.Role.ADMIN):
        remaining = get_user_model().objects.filter(is_active=True).exclude(pk=target.pk).filter(
            Q(is_staff=True) | Q(is_superuser=True) | Q(portal_account__role=PortalAccount.Role.ADMIN)
        ).exists()
        if not remaining:
            raise ValidationError("Debe permanecer al menos un administrador activo.", code="last_admin")
    profile = profile or PortalAccount(user=target)
    profile.role = role
    profile.version = version + 1
    profile.session_version += 1
    profile.access_version += 1
    profile.full_clean()
    target.is_active = is_active
    target.save(update_fields=["is_active"])
    profile.save()
    # Grants snapshot this epoch. Never acquire Event locks here: stale grants
    # remain ineffective even if the account is later reactivated or reclassified.
    return target


@transaction.atomic
def set_event_reviewers(*, actor, event_id, reviewer_ids, expected_version):
    from apps.events.models import Event
    event = Event.objects.select_for_update().get(pk=event_id)
    _lock_roster()
    if not isinstance(reviewer_ids, (list, tuple, set)) or len(reviewer_ids) > 100:
        raise ValidationError("Selecciona hasta 100 revisores válidos.")
    if any(type(value) is not int or value < 1 for value in reviewer_ids):
        raise ValidationError("Los identificadores de revisor no son válidos.")
    selected = set(reviewer_ids)
    users = _locked_users(getattr(actor, "pk", None), *selected)
    current = users.get(getattr(actor, "pk", None))
    if not can_organize(current) or current.pk != event.owner_id:
        raise PermissionDenied("Sólo el organizador propietario puede asignar revisores a este evento.")
    if type(expected_version) is not int or expected_version < 1:
        raise ValidationError("Falta una versión válida de los accesos del evento.")
    if event.review_access_version != expected_version:
        raise ValidationError("Los accesos cambiaron en otra pestaña. Recarga antes de guardar.", code="stale_access")
    if any(user_id not in users or not users[user_id].is_active or get_role(users[user_id]) != PortalAccount.Role.REVIEWER
           for user_id in selected):
        raise ValidationError("Sólo puedes asignar cuentas activas con rol Revisor.")
    profiles = {profile.user_id: profile for profile in PortalAccount.objects.select_for_update().filter(user_id__in=selected).order_by("user_id")}
    epochs = {user_id: profiles[user_id].access_version for user_id in selected}
    existing = EventReviewAssignment.objects.filter(event=event)
    existing_epochs = dict(existing.values_list("reviewer_id", "reviewer_version"))
    if existing_epochs == epochs:
        return list(existing.select_related("reviewer"))
    existing.exclude(reviewer_id__in=selected).delete()
    existing_ids = set(existing_epochs) & selected
    for user_id in sorted(existing_ids):
        if existing_epochs[user_id] != epochs[user_id]:
            existing.filter(reviewer_id=user_id).update(reviewer_version=epochs[user_id], assigned_by=current, created_at=timezone.now())
    EventReviewAssignment.objects.bulk_create([
        EventReviewAssignment(event=event, reviewer_id=user_id, assigned_by=current, reviewer_version=epochs[user_id])
        for user_id in sorted(selected - existing_ids)
    ])
    event.review_access_version += 1
    event.save(update_fields=["review_access_version"])
    return list(EventReviewAssignment.objects.filter(event=event).select_related("reviewer"))
