"""Human-only local guidance and reviewed phrase management."""

import json
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from .forms import (
    CommandPatternForm, InteractionDeleteForm, InteractionFilterForm, InteractionReviewForm,
)
from .interaction_memory import MemoryError, memory_summary, save_interaction
from .local_commands import envelope, guide as local_guide, human_organizer, save_pattern
from .models import CommandPattern, InteractionRecord


def _json(request):
    return "application/json" in request.headers.get("Accept", "")


def _patterns(actor):
    return CommandPattern.objects.filter(owner=actor).order_by("-reviewed_at", "id")[:200]


@never_cache
@login_required
@require_POST
def guide(request):
    started = time.perf_counter()
    try:
        actor = human_organizer(request.user)
    except PermissionDenied:
        return JsonResponse(envelope("refused", "Acceso no permitido."), status=403)
    if (
        len(request.POST.getlist("text")) != 1
        or len(request.POST.getlist("context")) > 1
        or request.POST.get("context", "") not in {"", "person_name", "theme"}
    ):
        return JsonResponse(
            envelope("refused", "Envía una sola frase y un contexto permitido."),
            status=400,
        )
    try:
        result = local_guide(actor, request.POST["text"], request.POST.get("context", ""))
    except (ValueError, RuntimeError, OSError):
        return JsonResponse(
            envelope(
                "refused", "El catálogo local no está disponible. Puedes navegar manualmente."
            ),
            status=503,
        )
    response = JsonResponse(result)
    response["X-Gica-Guide-Ms"] = f"{min(60000, (time.perf_counter() - started) * 1000):.3f}"
    return response


@never_cache
@login_required
@require_GET
def patterns(request):
    actor = human_organizer(request.user)
    return render(
        request,
        "assistant/patterns.html",
        {"patterns": _patterns(actor), "form": CommandPatternForm()},
    )


@never_cache
@login_required
@require_POST
def pattern_save(request):
    actor = human_organizer(request.user)
    form = CommandPatternForm(request.POST)
    if any(len(request.POST.getlist(field)) > 1 for field in ("phrase", "intent", "reviewed")):
        form.is_valid()
        form.add_error(None, "Envía una sola frase y una sola intención.")
    if form.is_valid():
        try:
            save_pattern(
                actor=actor,
                phrase=form.cleaned_data["phrase"],
                intent=form.cleaned_data["intent"],
                reviewed=form.cleaned_data["reviewed"],
            )
        except ValidationError as error:
            if hasattr(error, "error_dict"):
                for field, errors in error.error_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                form.add_error(None, "No se pudo guardar la frase. Revísala e inténtalo de nuevo.")
        except IntegrityError:
            form.add_error(None, "La lista cambió. Recarga antes de volver a guardar.")
        else:
            message = "Frase revisada guardada sólo para tu cuenta."
            if _json(request):
                return JsonResponse({"ok": True, "message": message})
            messages.success(request, message)
            return redirect("assistant:patterns")
    if _json(request):
        return JsonResponse(
            {"ok": False, "errors": {field: list(errors) for field, errors in form.errors.items()}},
            status=400,
        )
    return render(
        request,
        "assistant/patterns.html",
        {"patterns": _patterns(actor), "form": form},
        status=400,
    )


@never_cache
@login_required
@require_POST
def pattern_delete(request, pk):
    with transaction.atomic():
        actor = human_organizer(request.user, lock=True)
        pattern = get_object_or_404(CommandPattern, pk=pk, owner=actor)
        pattern.delete()
    message = "Frase eliminada de tu cuenta."
    if _json(request):
        return JsonResponse({"ok": True, "message": message})
    messages.success(request, message)
    return redirect("assistant:patterns")


def _strict_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return result


def _invalid_number(value):
    raise ValueError("Non-finite JSON number")


@never_cache
@login_required
@require_POST
def interaction_log(request):
    human_organizer(request.user)
    if request.content_type != "application/json":
        return JsonResponse(
            {"ok": False, "code": "format", "message": "Envía un registro JSON textual."},
            status=415,
        )
    if len(request.body) > 16384:
        return JsonResponse(
            {"ok": False, "code": "size", "message": "El registro supera el límite permitido."},
            status=413,
        )
    try:
        data = json.loads(
            request.body.decode("utf-8"), object_pairs_hook=_strict_object,
            parse_constant=_invalid_number,
        )
    except (ValueError, UnicodeError, RecursionError):
        return JsonResponse(
            {"ok": False, "code": "format", "message": "El registro JSON no es válido."},
            status=400,
        )
    try:
        record, created = save_interaction(actor=request.user, data=data)
    except MemoryError as error:
        return JsonResponse(
            {"ok": False, "code": error.code, "message": error.message}, status=error.status
        )
    except IntegrityError:
        return JsonResponse(
            {"ok": False, "code": "conflict", "message": "La memoria cambió. Revisa antes de repetir."},
            status=409,
        )
    return JsonResponse(
        {"ok": True, "id": str(record.pk), "created": created, "untrusted_client_log": True},
        status=201 if created else 200,
    )


_TIMING_LABELS = {
    "text_change_to_dispatch_ms": "Último cambio de texto → consulta",
    "speech_end_to_dispatch_ms": "Fin de voz → consulta",
    "final_to_dispatch_ms": "Texto final → consulta",
    "guide_roundtrip_ms": "Ida y vuelta de la guía local",
    "guide_server_ms": "Procesamiento de la guía en servidor",
    "response_to_tts_ms": "Respuesta → inicio de síntesis",
    "speech_end_to_tts_ms": "Fin de voz → inicio de síntesis",
    "tts_duration_ms": "Duración declarada de síntesis",
}


def _memory_context(request, actor, *, review_record=None, review_form=None):
    owned = InteractionRecord.objects.filter(owner=actor)
    records = owned.select_related("action")
    filter_form = InteractionFilterForm(request.GET)
    filters = {key: "" for key in ("q", "phase", "status", "review")}
    if filter_form.is_valid():
        filters.update(filter_form.cleaned_data)
        for field in ("phase", "status"):
            if filters[field]:
                records = records.filter(**{field: filters[field]})
        if filters["review"]:
            records = records.filter(review_status=filters["review"])
        if filters["q"]:
            records = records.filter(
                Q(original_text__icontains=filters["q"])
                | Q(normalized_text__icontains=filters["q"])
                | Q(reply__icontains=filters["q"])
                | Q(review_note__icontains=filters["q"])
            )
    else:
        records = records.none()
    if review_record is not None:
        # Keep an invalid review visible even when its original row was on another page.
        records = owned.select_related("action").filter(pk=review_record.pk)
    paginator = Paginator(records, 20)
    page = paginator.get_page(request.GET.get("page", 1))
    items = list(page.object_list)
    for record in items:
        record.review_form = (
            review_form if review_record is not None and record.pk == review_record.pk
            else InteractionReviewForm(prefix=f"review-{record.pk}", initial={
                "review_status": record.review_status if record.review_status != "unreviewed" else "good",
                "review_note": record.review_note, "suggested_intent": record.suggested_intent,
            })
        )
        record.timing_rows = [
            {"label": _TIMING_LABELS[key], "value": value}
            for key, value in record.timings.items() if key in _TIMING_LABELS
        ]
    return {
        "records": items, "page_obj": page, "paginator": paginator,
        "filter_form": filter_form, "filters": filters, "review_form": InteractionReviewForm(),
        "summary": memory_summary(owned), "capacity": 1000,
    }


@never_cache
@login_required
@require_GET
def memory(request):
    actor = human_organizer(request.user)
    return render(request, "assistant/memory.html", _memory_context(request, actor))


@never_cache
@login_required
@require_POST
def interaction_review(request, pk):
    with transaction.atomic():
        actor = human_organizer(request.user, lock=True)
        record = get_object_or_404(InteractionRecord, owner=actor, pk=pk)
        form = InteractionReviewForm(request.POST, prefix=f"review-{record.pk}")
        if any(len(request.POST.getlist(form.add_prefix(field))) > 1 for field in form.fields):
            form.is_valid()
            form.add_error(None, "Envía una sola revisión por campo.")
        if form.is_valid():
            record.review_status = form.cleaned_data["review_status"]
            record.review_note = form.cleaned_data["review_note"]
            record.suggested_intent = form.cleaned_data["suggested_intent"]
            record.reviewed_at = timezone.now()
            record.save(update_fields=[
                "review_status", "review_note", "suggested_intent", "reviewed_at",
            ])
            if _json(request):
                return JsonResponse({"ok": True, "message": "Revisión guardada sin activar patrones."})
            messages.success(request, "Revisión guardada. No se activó ningún patrón.")
            return redirect("assistant:memory")
    if _json(request):
        return JsonResponse({"ok": False, "errors": dict(form.errors)}, status=400)
    return render(
        request, "assistant/memory.html",
        _memory_context(request, actor, review_record=record, review_form=form), status=400,
    )


def _delete_confirmed(request):
    form = InteractionDeleteForm(request.POST)
    if len(request.POST.getlist("confirm")) != 1 or not form.is_valid():
        return JsonResponse(
            {"ok": False, "message": "Confirma explícitamente la eliminación."}, status=400
        )
    return None


@never_cache
@login_required
@require_POST
def interaction_delete(request, pk):
    with transaction.atomic():
        actor = human_organizer(request.user, lock=True)
        record = get_object_or_404(InteractionRecord, owner=actor, pk=pk)
        rejected = _delete_confirmed(request)
        if rejected is not None:
            return rejected
        record.delete()
    if _json(request):
        return JsonResponse({"ok": True, "message": "Registro eliminado."})
    messages.success(request, "Registro eliminado de tu memoria.")
    return redirect("assistant:memory")


@never_cache
@login_required
@require_POST
def interaction_clear(request):
    with transaction.atomic():
        actor = human_organizer(request.user, lock=True)
        rejected = _delete_confirmed(request)
        if rejected is not None:
            return rejected
        InteractionRecord.objects.filter(owner=actor).delete()
    if _json(request):
        return JsonResponse({"ok": True, "message": "Tu memoria se vació explícitamente."})
    messages.success(request, "Tu memoria se vació. Tus patrones revisados se conservan.")
    return redirect("assistant:memory")
