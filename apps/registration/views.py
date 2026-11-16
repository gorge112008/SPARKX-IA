"""Owner-only management and a minimal, non-enumerating public form."""
from django.contrib import messages
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.accounts.access import can_organize, get_role
from apps.accounts.models import PortalAccount
from apps.events.models import Event
from .forms import PublicationForm, RegistrationForm
from .models import RegistrationPage
from .services import (RECEIPT_MESSAGE, RegistrationConflict, availability,
                       set_registration_state, submission_token, submit_registration)


def _owned_event(request, event_id):
    current = get_user_model().objects.filter(pk=request.user.pk, is_active=True).first()
    if not current or not can_organize(current):
        raise PermissionDenied("No tienes permiso para gestionar inscripciones.")
    return get_object_or_404(Event.objects.select_related("active_plan"), pk=event_id, owner=current)


def _public_actor(request):
    if request.user.is_authenticated:
        current = get_user_model().objects.filter(pk=request.user.pk, is_active=True).first()
        if not current or get_role(current) == PortalAccount.Role.REVIEWER:
            raise PermissionDenied("El rol Revisor no permite consultar ni enviar inscripciones.")


def _manage_context(request, event, *, form=None):
    page = RegistrationPage.objects.filter(event=event).first()
    counts = availability(event)
    paused = bool(page and page.state == RegistrationPage.State.OPEN
                  and (not event.active_plan_id or page.published_plan_id != event.active_plan_id))
    if form is None:
        form = PublicationForm(initial={
            "action": RegistrationPage.State.CLOSED if page and page.state == RegistrationPage.State.OPEN and not paused else RegistrationPage.State.OPEN,
            "expected_version": page.version if page else 0, "expected_revision": event.revision,
            "expected_plan": event.active_plan_id,
        })
    registrations = Paginator(event.registrations.all(), 25).get_page(request.GET.get("page"))
    public_path = reverse("event_registration:public", kwargs={"token": page.public_token}) if page else ""
    return {"event": event, "publication": page, "publication_paused": paused,
            "publication_action": form["action"].value(), "counts": counts, "form": form,
            "registrations": registrations,
            "public_path": public_path, "public_url": request.build_absolute_uri(public_path) if page else ""}


@login_required
@require_GET
def manage(request, event_id):
    event = _owned_event(request, event_id)
    return render(request, "event_registration/manage.html", _manage_context(request, event))


@login_required
@require_POST
def change_state(request, event_id):
    event = _owned_event(request, event_id)
    form = PublicationForm(request.POST)
    status = 400
    if form.is_valid():
        try:
            page = set_registration_state(event_id=event.pk, actor=request.user, **form.cleaned_data)
        except RegistrationConflict as error:
            form.add_error(None, error)
            status = 409
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Inscripciones abiertas. Puedes compartir el enlace." if page.state == RegistrationPage.State.OPEN
                             else "Inscripciones cerradas. Se conservaron los registros y el plan aprobado.")
            return redirect("event_registration:manage", event_id=event.pk)
    event = _owned_event(request, event_id)
    return render(request, "event_registration/manage.html", _manage_context(request, event, form=form), status=status)


def _public_response(request, template, context, *, status=200):
    response = render(request, template, context, status=status)
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@never_cache
@sensitive_post_parameters("full_name", "email", "form_token")
@require_http_methods(["GET", "POST"])
def public_registration(request, token):
    _public_actor(request)
    page = get_object_or_404(RegistrationPage.objects.select_related("event", "published_plan"), public_token=token)
    form = RegistrationForm(request.POST if request.method == "POST" else None,
                            initial={"form_token": submission_token(page)})
    if request.method == "POST" and form.is_valid():
        try:
            submit_registration(token=token, actor=request.user, **form.cleaned_data)
        except RegistrationPage.DoesNotExist as error:
            raise Http404 from error
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect("event_registration:received", token=token)
    counts = availability(page.event)
    is_open = (page.state == RegistrationPage.State.OPEN and bool(page.event.active_plan_id)
               and page.published_plan_id == page.event.active_plan_id)
    sessions = [{"title": item["title"], "start": datetime.fromisoformat(item["start"].replace("Z", "+00:00")),
                 "duration_minutes": item["duration_minutes"], "speaker": item["speaker"]}
                for item in page.published_plan.payload.get("sessions", [])]
    return _public_response(request, "event_registration/public.html", {
        "publication": page, "event": page.event, "counts": counts, "is_open": is_open,
        "form": form, "show_form": is_open and counts["remaining"] > 0, "sessions": sessions,
    }, status=400 if request.method == "POST" else 200)


@never_cache
@require_GET
def received(request, token):
    _public_actor(request)
    get_object_or_404(RegistrationPage.objects.only("pk"), public_token=token)
    return _public_response(request, "event_registration/received.html", {"receipt_message": RECEIPT_MESSAGE})
