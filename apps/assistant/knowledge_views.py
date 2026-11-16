"""Human-only public references and automatic memory with later review."""

import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .knowledge_memory import delete_knowledge, update_knowledge
from .knowledge_service import answer_public_question
from .local_commands import human_organizer
from .models import KnowledgeEntry, LearnedAlias, PublicLookupAttempt


class QuestionForm(forms.Form):
    text = forms.CharField(label="Pregunta sobre un tema público", max_length=300)
    request_id = forms.UUIDField(widget=forms.HiddenInput)


class KnowledgeEditForm(forms.Form):
    answer = forms.CharField(label="Respuesta corregida", max_length=1800, widget=forms.Textarea)


def _context(request, actor, **extra):
    query = request.GET.get("q", "").strip()[:120]
    entries = KnowledgeEntry.objects.filter(owner=actor)
    aliases = LearnedAlias.objects.filter(owner=actor)
    if query:
        entries = entries.filter(Q(question__icontains=query) | Q(answer__icontains=query))
        aliases = aliases.filter(alias__icontains=query)
    page = Paginator(entries, 12).get_page(request.GET.get("page", 1))
    for entry in page:
        entry.expired = entry.expires_at <= timezone.now()
    return {
        "entries": page, "page_obj": page, "aliases": aliases[:100], "q": query,
        "knowledge_count": KnowledgeEntry.objects.filter(owner=actor).count(),
        "alias_count": LearnedAlias.objects.filter(owner=actor).count(),
        "question_form": QuestionForm(initial={"request_id": uuid.uuid4()}), **extra,
    }


@never_cache
@login_required
@require_GET
def knowledge(request):
    actor = human_organizer(request.user)
    return render(request, "assistant/knowledge.html", _context(request, actor))


@never_cache
@login_required
@require_POST
def query(request):
    actor = human_organizer(request.user)
    allowed = {"text", "request_id", "context", "allow_network", "csrfmiddlewaretoken"}
    if (
        set(request.POST) - allowed
        or any(len(request.POST.getlist(key)) > 1 for key in allowed)
        or request.POST.get("context", "") not in {"", "person_name", "theme"}
        or request.POST.get("allow_network", "off") not in {"on", "off"}
    ):
        return JsonResponse({"handled": True, "status": "invalid", "reply": "Envía una sola pregunta y las opciones permitidas."}, status=400)
    form = QuestionForm(request.POST)
    result = None
    if form.is_valid():
        try:
            result = answer_public_question(
                actor, form.cleaned_data["text"], form.cleaned_data["request_id"],
                context=request.POST.get("context", ""),
                allow_network=request.POST.get("allow_network") == "on",
            )
        except ValidationError as error:
            form.add_error("text", error.messages)
    json_mode = "application/json" in request.headers.get("Accept", "")
    if form.errors:
        if json_mode:
            return JsonResponse({"handled": True, "status": "invalid", "reply": " ".join(form.errors.get("text", ["Revisa la pregunta y su identificador."]))[:280]}, status=400)
        return render(request, "assistant/knowledge.html", _context(request, actor, question_form=form), status=400)
    if json_mode:
        return JsonResponse(result)
    if not result["handled"]:
        result = {"handled": True, "status": "not_found", "reply": "Prueba con «qué es mantenimiento predictivo» o «busca en Wikipedia mantenimiento». Las órdenes se dan en el panel de Gica."}
    return render(request, "assistant/knowledge.html", _context(request, actor, result=result))


@never_cache
@login_required
@require_POST
def knowledge_change(request, pk):
    actor = human_organizer(request.user)
    get_object_or_404(KnowledgeEntry, owner=actor, pk=pk)
    if any(len(request.POST.getlist(key)) > 1 for key in request.POST):
        return JsonResponse({"ok": False, "message": "Envía una sola operación."}, status=400)
    operation = request.POST.get("operation")
    try:
        if operation == "delete":
            delete_knowledge(actor, pk)
        elif operation in {"review", "disable", "activate"}:
            update_knowledge(actor, pk, status={"review": "reviewed", "disable": "disabled", "activate": "reviewed"}[operation])
        elif operation == "edit":
            form = KnowledgeEditForm(request.POST)
            if not form.is_valid():
                raise ValidationError("La respuesta debe tener entre 1 y 1800 caracteres.")
            update_knowledge(actor, pk, answer=form.cleaned_data["answer"])
        else:
            raise ValidationError("Elige una operación permitida.")
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, "Memoria actualizada. Los permisos y planes se conservan.")
    return redirect("assistant:knowledge")


@never_cache
@login_required
@require_POST
def alias_change(request, pk):
    with transaction.atomic():
        actor = human_organizer(request.user, lock=True)
        alias = get_object_or_404(LearnedAlias, owner=actor, pk=pk)
        operation = request.POST.get("operation")
        if len(request.POST.getlist("operation")) != 1 or operation not in {"review", "disable", "delete"}:
            return JsonResponse({"ok": False, "message": "Elige una sola operación permitida."}, status=400)
        if operation == "delete":
            alias.delete()
        else:
            alias.status = "reviewed" if operation == "review" else "disabled"
            alias.reviewed_at = timezone.now() if operation == "review" else None
            alias.full_clean()
            alias.save(update_fields=["status", "reviewed_at", "updated_at"])
    messages.success(request, "Asociación actualizada sólo para tu cuenta.")
    return redirect("assistant:knowledge")


@never_cache
@login_required
@require_POST
def clear_lookup_history(request):
    """Explicitly clear finished deduplication records; never touch live attempts."""
    with transaction.atomic():
        actor = human_organizer(request.user, lock=True)
        if request.POST.getlist("confirm") != ["on"]:
            return JsonResponse({"ok": False, "message": "Confirma la limpieza del historial."}, status=400)
        # Today's records also enforce the daily allowance and must remain.
        midnight = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        PublicLookupAttempt.objects.filter(owner=actor, finished_at__isnull=False, created_at__lt=midnight).delete()
    messages.success(request, "Historial anterior limpiado. Se conservan las consultas de hoy y los conocimientos.")
    return redirect("assistant:knowledge")
