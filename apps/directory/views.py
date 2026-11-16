"""Owner-scoped directory screens; all writes go through application services."""

import uuid
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.access import can_organize
from apps.events.models import Event

from .forms import DirectoryFilterForm, EventPersonForm, OrganizationForm, PersonForm
from .queries import event_people, organizations_for, people_for, search_people
from .normalization import search_key
from .services import assign_person, upsert_organization, upsert_person


def _organizer(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_organize(request.user):
            raise PermissionDenied("El directorio está disponible para quienes organizan sus propios eventos.")
        return view(request, *args, **kwargs)
    return wrapped


def _owned_reference(queryset, raw):
    """A valid foreign identifier is always a 404, including in form inputs."""
    if not raw:
        return None
    try:
        identifier = uuid.UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None  # The form reports a malformed identifier.
    return get_object_or_404(queryset, pk=identifier)


def _form_errors(form, error):
    aliases = {"organization_id": "organization", "person_id": "person"}
    if hasattr(error, "message_dict"):
        for name, issues in error.message_dict.items():
            field = aliases.get(name, name)
            form.add_error(field if field in form.fields else None, issues)
    else:
        form.add_error(None, error)


def _stale(error):
    return getattr(error, "code", None) == "stale_directory"


def _pagination_query(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


@login_required
@_organizer
@require_GET
def index(request):
    tab = request.GET.get("tab", "people")
    if tab not in {"people", "organizations"}:
        tab = "people"
    _owned_reference(organizations_for(request.user), request.GET.get("organization"))
    form = DirectoryFilterForm(request.GET, actor=request.user)
    valid = form.is_valid()
    values = form.cleaned_data if valid else {}
    if tab == "organizations":
        form.fields["q"].widget.attrs["placeholder"] = "Nombre de empresa u organización"
        records = organizations_for(request.user)
        if not values.get("include_inactive", False):
            records = records.filter(is_active=True)
        for term in search_key(values.get("q", "")).split():
            records = records.filter(Q(name_key__contains=term) | Q(alias_keys__contains=term))
        records = records.order_by("name_key", "pk")
    else:
        records = search_people(
            request.user, query=values.get("q", ""), category=values.get("category", ""),
            organization_id=values["organization"].pk if values.get("organization") else "",
            include_inactive=values.get("include_inactive", False),
        ).select_related("organization").order_by("name_key", "pk")
    if not valid:
        records = records.none()
    page = Paginator(records, 20).get_page(request.GET.get("page"))
    return render(request, "directory/index.html", {
        "filter_form": form, "tab": tab, "records_page": page,
        "pagination_query": _pagination_query(request),
    }, status=200 if valid else 400)


def _organization_form(request, instance=None):
    form = OrganizationForm(request.POST if request.method == "POST" else None, instance=instance)
    conflict = False
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            upsert_organization(
                actor=request.user, object_id=instance.pk if instance else None,
                name=form.cleaned_data["name"], is_active=form.cleaned_data["is_active"],
                aliases=form.cleaned_data["aliases"],
                is_synthetic=form.cleaned_data["is_synthetic"],
                expected_version=form.cleaned_data.get("expected_version"),
            )
        except ValidationError as error:
            if _stale(error) and instance is not None:
                instance = get_object_or_404(organizations_for(request.user), pk=instance.pk)
                retained = request.POST.copy()
                retained["expected_version"] = str(instance.version)
                form = OrganizationForm(retained, instance=instance)
                conflict, response_status = True, 409
            _form_errors(form, error)
        else:
            messages.success(request, "Organización guardada.")
            return redirect(reverse("directory:index") + "?tab=organizations")
    return render(request, "directory/form.html", {"form": form, "record": instance,
                  "kind": "organization", "editing": instance is not None, "conflict": conflict}, status=response_status)


@login_required
@_organizer
@require_http_methods(["GET", "POST"])
def organization_create(request):
    return _organization_form(request)


@login_required
@_organizer
@require_http_methods(["GET", "POST"])
def organization_edit(request, organization_id):
    return _organization_form(request, get_object_or_404(organizations_for(request.user), pk=organization_id))


def _person_form(request, instance=None):
    if request.method == "POST":
        _owned_reference(organizations_for(request.user), request.POST.get("organization"))
    form = PersonForm(request.POST if request.method == "POST" else None, actor=request.user, instance=instance)
    conflict = False
    response_status = 200
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            upsert_person(
                actor=request.user, object_id=instance.pk if instance else None,
                full_name=values["full_name"], category=values["category"], email=values["email"],
                aliases=values["aliases"],
                expertise=values["expertise"], organization_id=values["organization"].pk if values["organization"] else None,
                is_active=values["is_active"], is_synthetic=values["is_synthetic"],
                expected_version=values.get("expected_version"),
            )
        except ValidationError as error:
            if _stale(error) and instance is not None:
                instance = get_object_or_404(people_for(request.user).select_related("organization"), pk=instance.pk)
                retained = request.POST.copy()
                retained["expected_version"] = str(instance.version)
                form = PersonForm(retained, actor=request.user, instance=instance)
                conflict, response_status = True, 409
            _form_errors(form, error)
        else:
            messages.success(request, "Persona guardada.")
            return redirect("directory:index")
    return render(request, "directory/form.html", {"form": form, "record": instance,
                  "kind": "person", "editing": instance is not None, "conflict": conflict}, status=response_status)


@login_required
@_organizer
@require_http_methods(["GET", "POST"])
def person_create(request):
    return _person_form(request)


@login_required
@_organizer
@require_http_methods(["GET", "POST"])
def person_edit(request, person_id):
    return _person_form(request, get_object_or_404(people_for(request.user).select_related("organization"), pk=person_id))


@login_required
@_organizer
@require_http_methods(["GET", "POST"])
def roster(request, event_id):
    event = get_object_or_404(Event.objects.filter(owner=request.user, archived_at__isnull=True), pk=event_id)
    assignments = event_people(request.user, event_id)
    # Reuse this request's scoped selector. Services recheck writes separately;
    # constructing a form for each row must not repeat authorization queries.
    authorized_people = people_for(request.user)
    selected_person = None
    selected_assignment = None
    bound_form = None
    response_status = 200
    conflict = False
    if request.method == "POST":
        selected_person = _owned_reference(authorized_people, request.POST.get("person"))
        if selected_person is not None:
            selected_assignment = assignments.filter(person=selected_person, role=request.POST.get("role", "")).first()
        bound_form = EventPersonForm(
            request.POST, actor=request.user, assignment=selected_assignment, people_queryset=authorized_people,
            auto_id="roster-" + str(selected_assignment.pk) + "-%s" if selected_assignment else "id_%s")
        if bound_form.is_valid():
            try:
                assign_person(actor=request.user, event_id=event.pk,
                              person_id=bound_form.cleaned_data["person"].pk,
                              role=bound_form.cleaned_data["role"], status=bound_form.cleaned_data["status"],
                              expected_version=bound_form.cleaned_data["expected_version"])
            except ValidationError as error:
                if _stale(error):
                    selected_assignment = event_people(request.user, event_id).filter(
                        person=selected_person, role=bound_form.cleaned_data["role"]).first()
                    retained = request.POST.copy()
                    retained["expected_version"] = str(selected_assignment.version if selected_assignment else 0)
                    bound_form = EventPersonForm(
                        retained, actor=request.user, assignment=selected_assignment, people_queryset=authorized_people,
                        auto_id="roster-" + str(selected_assignment.pk) + "-%s" if selected_assignment else "id_%s")
                    conflict, response_status = True, 409
                _form_errors(bound_form, error)
            else:
                messages.success(request, "Participación guardada.")
                return redirect("directory:roster", event_id=event.pk)
    rows = []
    for assignment in event_people(request.user, event_id):
        is_bound = bound_form is not None and selected_assignment is not None and assignment.pk == selected_assignment.pk
        form = bound_form if is_bound else EventPersonForm(
            actor=request.user, assignment=assignment, people_queryset=authorized_people, auto_id="roster-" + str(assignment.pk) + "-%s")
        rows.append({"assignment": assignment, "form": form, "conflict": conflict and is_bound})
    new_form = bound_form if bound_form is not None and selected_assignment is None else EventPersonForm(actor=request.user, people_queryset=authorized_people)
    return render(request, "directory/roster.html", {"event": event, "rows": rows, "form": new_form,
                  "conflict": conflict, "conflict_assignment": selected_assignment}, status=response_status)
