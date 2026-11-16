"""Owner-scoped event commands. Material edits invalidate old snapshots."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone as django_timezone
from apps.directory.models import EventPerson, Person

from .models import Event
from .interview import QUESTION_BY_KEY, normalize_interview_answers
from apps.accounts.access import can_organize


class InterviewConflict(ValidationError):
    """The organizer must review the current context before resubmitting."""


def require_event_owner(event, actor):
    if not can_organize(actor) or actor.pk != event.owner_id or event.archived_at is not None:
        raise PermissionDenied("No tienes permiso para modificar este evento.")


@transaction.atomic
def archive_event(*, actor, event_id, expected_revision):
    """Retire an event without erasing protected model usage or approved history."""
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    if type(expected_revision) is not int or event.revision != expected_revision:
        raise ValidationError("La ficha cambió. Recarga antes de retirar el evento.")
    if event.jobs.filter(status__in=["queued", "running"]).exists():
        raise ValidationError("Espera a que termine la solicitud del evento antes de retirarlo.")
    event.archived_at = django_timezone.now()
    event.revision += 1
    event.review_access_version += 1
    event.save(update_fields=["archived_at", "revision", "review_access_version", "updated_at"])
    return event


def _check_event_values(event):
    if event.starts_at is not None and django_timezone.is_naive(event.starts_at):
        raise ValidationError({"starts_at": "La fecha debe incluir una zona horaria."})
    if type(event.capacity) is not int or not 1 <= event.capacity <= 100000:
        raise ValidationError({"capacity": "La capacidad debe ser un entero entre 1 y 100000."})
    event.full_clean()


def _selected_speaker(actor, speaker_id):
    if speaker_id is None:
        return None
    from apps.directory.queries import people_for
    try:
        person = people_for(actor).filter(pk=speaker_id, is_active=True, category=Person.Category.SPEAKER).first()
    except (ValidationError, ValueError, TypeError) as error:
        raise ValidationError({"speaker_id": "Selecciona un expositor activo de tu directorio."}) from error
    if person is None:
        raise ValidationError({"speaker_id": "Selecciona un expositor activo de tu directorio."})
    return person


def _assign_primary_speaker(*, event, actor, person):
    """A role at this event never rewrites the person's institutional affiliation."""
    from apps.directory.services import assign_person
    changed = False
    links = list(event.directory_people.select_for_update().filter(role=Person.Category.SPEAKER))
    for link in links:
        if link.status != EventPerson.Status.CANCELLED and (person is None or link.person_id != person.pk):
            assign_person(actor=actor, event_id=event.pk, person_id=link.person_id, role=Person.Category.SPEAKER,
                          status=EventPerson.Status.CANCELLED, expected_version=link.version)
            changed = True
    selected = next((link for link in links if person is not None and link.person_id == person.pk), None)
    if person is not None and (selected is None or selected.status == EventPerson.Status.CANCELLED):
        assign_person(actor=actor, event_id=event.pk, person_id=person.pk, role=Person.Category.SPEAKER,
                      status=EventPerson.Status.PLANNED, expected_version=selected.version if selected else 0)
        changed = True
    return changed


@transaction.atomic
def create_event(*, actor, title, brief, starts_at=None, timezone="America/Lima", capacity=100, event_id=None, organization_id=None,
                 is_synthetic=False, scheduled_dates=None, interview_answers=None, speaker_id=None):
    if not can_organize(actor):
        raise PermissionDenied("Inicia sesión para crear un evento.")
    identity = {"id": event_id} if event_id is not None else {}
    event = Event(**identity, owner=actor, title=title.strip(), brief=brief.strip(), starts_at=starts_at, timezone=timezone, capacity=capacity,
                  organization_id=organization_id, is_synthetic=is_synthetic, scheduled_dates=[] if scheduled_dates is None else scheduled_dates,
                  interview_answers={} if interview_answers is None else interview_answers)
    speaker = _selected_speaker(actor, speaker_id)
    try:
        event.interview_answers = normalize_interview_answers(event.interview_answers)
    except ValueError as error:
        raise ValidationError({"interview_answers": str(error)}) from error
    _check_event_values(event)
    event.save(force_insert=True)
    if speaker is not None:
        _assign_primary_speaker(event=event, actor=actor, person=speaker)
    return event


@transaction.atomic
def update_event(*, event_id, actor, **changes):
    allowed = {"title", "brief", "starts_at", "timezone", "capacity", "organization_id", "is_synthetic", "scheduled_dates", "interview_answers", "speaker_id"}
    if set(changes) - allowed:
        raise ValidationError("La solicitud contiene campos de evento no permitidos.")
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    change_speaker = "speaker_id" in changes
    speaker = _selected_speaker(actor, changes.pop("speaker_id")) if change_speaker else None
    if "interview_answers" in changes:
        try:
            changes["interview_answers"] = normalize_interview_answers(changes["interview_answers"])
        except ValueError as error:
            raise ValidationError({"interview_answers": str(error)}) from error
    changed = []
    for name, value in changes.items():
        if name in {"title", "brief"} and isinstance(value, str):
            value = value.strip()
        if getattr(event, name) != value:
            setattr(event, name, value)
            changed.append(name)
    if "brief" in changed:
        # A reference to the previous description is no longer a declaration
        # about the new one. Explicitly written answers remain the user's data.
        answers = normalize_interview_answers(event.interview_answers)
        revised = {
            key: {"status": "pending", "value": ""} if answer["status"] == "in_brief" else answer
            for key, answer in answers.items()
        }
        if revised != answers:
            event.interview_answers = revised
            changed.append("interview_answers")
    _check_event_values(event)
    speaker_changed = _assign_primary_speaker(event=event, actor=actor, person=speaker) if change_speaker else False
    if not changed and not speaker_changed:
        return event
    event.revision += 1
    event.save(update_fields=[*changed, "revision", "updated_at"])
    return event


@transaction.atomic
def update_interview(*, event_id, actor, expected_revision, question_key, status, value):
    event = Event.objects.select_for_update().get(pk=event_id)
    require_event_owner(event, actor)
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValidationError("Falta una revisión válida del evento.")
    if expected_revision != event.revision:
        raise InterviewConflict("El evento cambió. Compara la respuesta actual antes de guardar de nuevo.")
    if not isinstance(question_key, str) or question_key not in QUESTION_BY_KEY:
        raise ValidationError("La pregunta no es válida.")
    try:
        answers = normalize_interview_answers({
            **event.interview_answers, question_key: {"status": status, "value": value},
        })
    except (ValueError, TypeError) as exc:
        raise ValidationError(str(exc)) from exc
    if answers == event.interview_answers:
        return event
    event.interview_answers = answers
    _check_event_values(event)
    event.revision += 1
    event.save(update_fields=["interview_answers", "revision", "updated_at"])
    return event
