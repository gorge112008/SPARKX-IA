"""Personal preparation and safe local observations, without remote side effects."""
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .catalog import GROUPS, ITEMS
from .access import checklist_available_to
from .forms import ProgressForm
from .models import ChecklistProgress
from .services import StaleProgress, update_progress


def _enabled_owner(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not getattr(settings, "SPARKX_CHECKLIST_ENABLED", False):
            raise Http404
        if not checklist_available_to(request.user):
            raise PermissionDenied("Este checklist temporal es privado para Jorge.")
        return view(request, *args, **kwargs)
    return wrapped


def _context(request, *, bound_key=None, bound_form=None, error="", active_group=None, local_checks=None, last_checked=None):
    group_keys = {group.key for group in GROUPS}
    selected = active_group or request.GET.get("section", "")
    if selected not in group_keys:
        selected = GROUPS[0].key
    rows = {row.item_key: row for row in ChecklistProgress.objects.filter(owner=request.user)}
    groups, counts = [], {value: 0 for value in ChecklistProgress.Status.values}
    needs_review = 0
    for group in GROUPS:
        items = []
        for item in group.items:
            row = rows.get(item.key)
            status = row.status if row else ChecklistProgress.Status.NOT_STARTED
            version = row.version if row else 0
            counts[status] += 1
            saved_checks = row.confirmed_checks if row and isinstance(row.confirmed_checks, list) else []
            required = {check.key for check in item.confirmations}
            completion_valid = status == ChecklistProgress.Status.COMPLETED and required.issubset(saved_checks)
            review = status == ChecklistProgress.Status.COMPLETED and not completion_valid
            needs_review += review
            form = bound_form if item.key == bound_key else ProgressForm(
                item=item, initial={"status": status, "expected_version": version, "confirmations": saved_checks},
                auto_id="id_" + item.key + "_%s",
            )
            items.append({
                "key": item.key, "title": item.title, "description": item.description,
                "optional": item.optional, "condition": item.condition,
                "steps": item.steps, "confirmations": item.confirmations, "links": item.links,
                "confirmed_checks": form["confirmations"].value() or [],
                "completion_valid": completion_valid, "needs_review": review,
                "local_check": (local_checks or {}).get(item.key, {
                    "status": "info", "message": "Este punto requiere tu revisión personal. Usa la guía y confirma lo que hayas comprobado.",
                    "scope": "No consulta tus cuentas ni verifica acciones externas.", "checked_at": None,
                }),
                "status": status, "status_label": ChecklistProgress.Status(status).label,
                "version": version, "updated_at": row.updated_at if row else None,
                "form": form, "update_url": reverse("project_checklist:update", kwargs={"item_key": item.key}),
                "anchor": "item-" + item.key,
            })
        group_na = sum(item["status"] == ChecklistProgress.Status.NOT_APPLICABLE for item in items)
        group_completed = sum(item["completion_valid"] for item in items)
        groups.append({"key": group.key, "title": group.title, "description": group.description, "items": items,
                       "completed": group_completed, "applicable": len(items) - group_na, "not_applicable": group_na})
    total = len(ITEMS)
    applicable = total - counts[ChecklistProgress.Status.NOT_APPLICABLE]
    completed = counts[ChecklistProgress.Status.COMPLETED] - needs_review
    return {
        "page_title": "Checklist del proyecto", "checklist_groups": groups, "active_group": selected,
        "checklist_error": error, "status_choices": ChecklistProgress.Status.choices,
        "checklist_check_url": reverse("project_checklist:check"), "last_checked": last_checked,
        "stats": {"total": total, "applicable": applicable, "completed": completed,
                  "in_progress": counts[ChecklistProgress.Status.IN_PROGRESS],
                  "not_applicable": counts[ChecklistProgress.Status.NOT_APPLICABLE],
                  "needs_review": needs_review,
                  "percent": completed * 100 // applicable if applicable else 0},
    }


@login_required
@_enabled_owner
@require_GET
def index(request):
    return render(request, "project_checklist/index.html", _context(request))


@login_required
@_enabled_owner
@require_POST
def update(request, item_key):
    item = ITEMS.get(item_key)
    if item is None:
        raise Http404
    group_key = next(group.key for group in GROUPS if item in group.items)
    form = ProgressForm(request.POST, item=item, auto_id="id_" + item.key + "_%s")
    if not form.is_valid():
        return render(request, "project_checklist/index.html", _context(request, bound_key=item_key, bound_form=form, active_group=group_key), status=400)
    try:
        _, changed = update_progress(owner=request.user, item_key=item_key, **form.cleaned_data)
    except StaleProgress:
        return render(request, "project_checklist/index.html", _context(
            request, active_group=group_key, error="Este punto cambió en otra pestaña. Se muestran los datos actuales; revisa el estado antes de guardar de nuevo.",
        ), status=409)
    messages.success(request, "Estado guardado." if changed else "El punto ya tiene ese estado; no se creó otro cambio.")
    return redirect(reverse("project_checklist:index") + "?section=" + group_key + "#item-" + item_key)


@login_required
@_enabled_owner
@require_POST
def check(request):
    # Explicit read-only observation: no provider calls, job, account creation or
    # automatic completion. Do not persist keys, balances or arbitrary evidence.
    if set(request.POST) - {"csrfmiddlewaretoken"}:
        return render(request, "project_checklist/index.html", _context(
            request, error="La comprobación no admite datos adicionales ni credenciales.",
        ), status=400)
    from .checks import collect_local_checks
    captured_at = timezone.now()
    observations = collect_local_checks(owner=request.user, at=captured_at)
    return render(request, "project_checklist/index.html", _context(
        request, local_checks=observations, last_checked=captured_at,
    ))
