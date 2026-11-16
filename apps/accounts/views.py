"""Portal account management; credentials never enter messages or audit payloads."""
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .access import can_organize, get_role, require_portal_admin
from .forms import CreateAccountForm, PortalAuthenticationForm, PortalPasswordChangeForm, ReviewersForm, UpdateAccountForm
from .models import PortalAccount
from .services import create_portal_user, set_event_reviewers, update_portal_user
from .throttle import allow_login_attempt


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class PortalLoginView(LoginView):
    authentication_form = PortalAuthenticationForm

    def post(self, request, *args, **kwargs):
        if not allow_login_attempt(request):
            # Unbound form: a blocked request must never authenticate a password.
            form = self.authentication_form(request=request, initial={"username": request.POST.get("username", "")[:254]})
            form.cleaned_data = {}
            form.add_error(None, "Demasiados intentos. Espera unos minutos y vuelve a intentarlo.")
            response = self.render_to_response(self.get_context_data(form=form), status=429)
            from django.conf import settings
            response["Retry-After"] = str(settings.LOGIN_WINDOW_SECONDS)
            return response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = PortalAccount.objects.filter(user_id=self.request.user.pk).first()
        self.request.session["portal_auth_version"] = profile.session_version if profile else 1
        if profile and profile.must_change_password:
            return redirect("password_change")
        return response


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters("old_password", "new_password1", "new_password2"), name="dispatch")
class PortalPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = PortalPasswordChangeForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["must_change_password"] = PortalAccount.objects.filter(
            user=self.request.user, must_change_password=True,
        ).exists()
        return context

    def form_valid(self, form):
        with transaction.atomic():
            current = get_user_model().objects.select_for_update().get(pk=self.request.user.pk)
            if not current.is_active or current.password != form.user.password:
                form.add_error(None, "La cuenta cambió. Inicia sesión de nuevo antes de cambiar la contraseña.")
                return self.form_invalid(form)
            form.save()
            profile, _ = PortalAccount.objects.get_or_create(user=current)
            profile = PortalAccount.objects.select_for_update().get(pk=profile.pk)
            profile.must_change_password = False
            profile.version += 1
            profile.session_version += 1
            profile.save(update_fields=["must_change_password", "version", "session_version"])
            update_session_auth_hash(self.request, form.user)
            self.request.session["portal_auth_version"] = profile.session_version
        messages.success(self.request, "Contraseña actualizada. Tus otras sesiones deberán iniciar sesión de nuevo.")
        return redirect("events:index")


def _users_context(request, *, form=None, create_open=False):
    users = get_user_model().objects.select_related("portal_account").order_by("first_name", "username")
    page = Paginator(users, 25).get_page(request.GET.get("page"))
    rows = []
    for user in page:
        profile = getattr(user, "portal_account", None) or SimpleNamespace(version=1)
        role = PortalAccount.Role.ADMIN if user.is_staff or user.is_superuser else getattr(profile, "role", PortalAccount.Role.ORGANIZER)
        rows.append({"user": user, "profile": profile, "role": role,
                     "role_label": PortalAccount.Role(role).label,
                     "is_protected": user.is_staff or user.is_superuser,
                     "is_self": user.pk == request.user.pk})
    return {"rows": rows, "users_page": page, "form": form if form is not None else CreateAccountForm(),
            "create_open": create_open, "role_choices": PortalAccount.Role.choices}


def _add_validation(form, error):
    if hasattr(error, "message_dict"):
        for name, problems in error.message_dict.items():
            form.add_error(name if name in form.fields else None, problems)
    else:
        form.add_error(None, error)


@login_required
@never_cache
@require_GET
def users(request):
    require_portal_admin(request.user)
    return render(request, "accounts/users.html", _users_context(request))


@login_required
@never_cache
@sensitive_post_parameters("password")
@require_POST
def create_user(request):
    require_portal_admin(request.user)
    form = CreateAccountForm(request.POST)
    if form.is_valid():
        try:
            create_portal_user(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_validation(form, error)
        else:
            messages.success(request, "Cuenta creada. La persona deberá cambiar su contraseña inicial al entrar.")
            return redirect("accounts:users")
    return render(request, "accounts/users.html", _users_context(request, form=form, create_open=True), status=400)


@login_required
@never_cache
@require_POST
def update_user(request, user_id):
    require_portal_admin(request.user)
    target = get_object_or_404(get_user_model(), pk=user_id)
    form = UpdateAccountForm(request.POST)
    response_status = 400
    if form.is_valid():
        data = form.cleaned_data
        try:
            update_portal_user(
                actor=request.user, user_id=target.pk, expected_version=data["expected_version"],
                role=data["role"] if data["action"] == "role" else get_role(target),
                is_active=(data["is_active"] == "1") if data["action"] == "status" else target.is_active,
            )
        except ValidationError as error:
            response_status = 409 if getattr(error, "code", "") == "stale_user" else 400
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, "Configuración de acceso guardada.")
            return redirect("accounts:users")
    else:
        messages.error(request, "Revisa el rol, estado y versión antes de guardar.")
    return render(request, "accounts/users.html", _users_context(request), status=response_status)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def event_reviewers(request, event_id):
    from apps.events.models import Event
    if not can_organize(request.user):
        raise PermissionDenied("Sólo un organizador puede asignar revisores.")
    event = get_object_or_404(Event, pk=event_id, owner=request.user)
    form = ReviewersForm(request.POST if request.method == "POST" else None, event=event)
    response_status, conflict = 200, False
    if request.method == "POST":
        response_status = 400
        if form.is_valid():
            try:
                set_event_reviewers(actor=request.user, event_id=event.pk,
                                    reviewer_ids=[user.pk for user in form.cleaned_data["reviewers"]],
                                    expected_version=form.cleaned_data["expected_version"])
            except ValidationError as error:
                if getattr(error, "code", "") == "stale_access":
                    response_status, conflict = 409, True
                    event.refresh_from_db()
                    retained = request.POST.copy()
                    retained["expected_version"] = str(event.review_access_version)
                    form = ReviewersForm(retained, event=event)
                _add_validation(form, error)
            else:
                messages.success(request, "Accesos de revisión guardados.")
                return redirect("accounts:event_reviewers", event_id=event.pk)
    current = event.review_assignments.filter(
        reviewer__is_active=True, reviewer__portal_account__role=PortalAccount.Role.REVIEWER,
        reviewer_version=F("reviewer__portal_account__access_version"),
    ).select_related("reviewer")
    return render(request, "accounts/reviewers.html", {
        "event": event, "form": form, "conflict": conflict,
        "current_reviewers": [grant.reviewer for grant in current],
    }, status=response_status)
