"""Thin, owner-scoped HTTP endpoints; AI work is always queued."""

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.ai_management.models import AIAccount
from apps.accounts.access import get_role, visible_events
from apps.assistant.models import Message
from apps.assistant.local_queries import local_directory_reply
from apps.jobs.models import Job
from apps.jobs.services import cancel as cancel_job
from apps.jobs.services import enqueue
from apps.planning.domain import plan_impact, validate_plan
from apps.planning.models import PlanCandidate, PlanRevision
from apps.planning.progress_ui import task_tracking_context
from apps.planning.task_progress import update_task_progress
from apps.planning.services import approve_candidate, reject_candidate
from .calendar import build_calendar_context
from .demo import DEMO_EVENT_ID, get_demo_context
from .forms import AIRequestForm, ChatForm, EventEditForm, EventForm, InterviewForm, TaskStatusForm
from .interview import QUESTIONS, QUESTION_BY_KEY, build_interview_context
from .journey_demo import JOURNEY_EVENT_ID, get_journey_demo_context
from .models import Event
from .services import create_event, update_event, update_interview

DEFAULT_PLAN_PROMPT = "Prepara una propuesta inicial con el contexto de este evento."


def _event(request, event_id, *, lock=False):
    queryset = Event.objects.filter(owner=request.user, archived_at__isnull=True)
    if lock:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("active_plan")
    return get_object_or_404(queryset, pk=event_id)


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _chat_history(event):
    return list(Message.objects.filter(event=event).order_by("-created_at", "-id")[:50])[::-1]


def _error_response(request, event, error):
    text = " ".join(error.messages)
    if _htmx(request):
        # HTMX swaps successful responses. Errors remain visible and escaped;
        # input fields and idempotency keys are retained for a safe retry.
        return HttpResponse(format_html('<div class="notice notice-error" role="alert">{}</div>', text))
    messages.error(request, text)
    return redirect("events:detail", event_id=event.pk)


def _form_error(form):
    return ValidationError([message for errors in form.errors.as_data().values() for error in errors for message in error.messages])


def _model_policy_markup(request, event, prefix, key):
    from apps.ai_management.model_policy import request_policy_context
    account = AIAccount.objects.filter(owner=request.user).select_related("active_profile").first()
    policy = None
    if account:
        try:
            from apps.ai_management.agent_access import agent_preview_snapshot
            snapshot = agent_preview_snapshot(account, kind=Job.Kind.PLAN if prefix == "generate" else Job.Kind.CHAT)
            policy = request_policy_context(None if snapshot.get("agent_route") in {"fallback_budget", "free_pool", "free_pool_budget"} else snapshot, event=event,
                actor=request.user, kind=Job.Kind.PLAN if prefix == "generate" else Job.Kind.CHAT,
                request_key=key)
        except ValidationError:
            pass
    return render_to_string("events/_model_policy.html", {
        "policy_prefix": prefix, "model_policy": policy, "policy_oob": True,
    }, request=request)


def _job_response(request, event, current_job, *, rotate=None, include_chat=False):
    if not _htmx(request):
        return redirect("events:detail", event_id=event.pk)
    markup = render_to_string("events/_job.html", {"event": event, "job": current_job}, request=request)
    from apps.jobs.presentation import romeo_context
    markup += render_to_string("events/_romeo_monitor.html", {
        "event": event, "romeo": romeo_context(event=event, actor=request.user), "romeo_oob": True,
    }, request=request)
    if include_chat:
        history = render_to_string("events/_chat_messages.html", {"chat_messages": _chat_history(event)}, request=request)
        markup += history.replace('<div id="chat-messages"', '<div hx-swap-oob="outerHTML" id="chat-messages"', 1)
    if rotate:
        key = uuid.uuid4()
        markup += str(format_html('<input type="hidden" id="{}-request-key" name="idempotency_key" value="{}" hx-swap-oob="outerHTML">', rotate, key))
        markup += _model_policy_markup(request, event, rotate, key)
    return HttpResponse(markup)


@login_required
@require_GET
def index(request):
    from django.core.paginator import Paginator
    from .catalog import filter_query, find_events

    context = {
        "demo_event_id": DEMO_EVENT_ID,
        "journey_demo_event": Event.objects.filter(pk=JOURNEY_EVENT_ID, owner=request.user).first()
        if (getattr(request, "portal_role", None) or get_role(request.user)) in {"admin", "organizer"} else None,
    }
    try:
        catalog = find_events(actor=request.user, params=request.GET)
    except ValueError as error:
        return render(request, "events/index.html", {**context, "catalog_error": str(error)}, status=400)
    page = Paginator(catalog["entries"], 20).get_page(request.GET.get("page"))
    context.update({
        "catalog": catalog, "event_entries": page.object_list,
        "events": [entry["event"] for entry in page.object_list],
        "event_page": page,
        "previous_url": "?" + filter_query(catalog["filter_values"], page=page.previous_page_number()) if page.has_previous() else None,
        "next_url": "?" + filter_query(catalog["filter_values"], page=page.next_page_number()) if page.has_next() else None,
    })
    return render(request, "events/index.html", context)


@login_required
@require_GET
def calendar_view(request):
    from .catalog import find_events

    try:
        catalog = find_events(actor=request.user, params=request.GET)
        context = build_calendar_context(entries=catalog["entries"], params=request.GET)
    except ValueError as error:
        return render(request, "events/calendar.html", {"calendar_error": str(error)}, status=400)
    return render(request, "events/calendar.html", {"calendar": context, "catalog": catalog})


@login_required
@require_http_methods(["GET", "POST"])
def create(request):
    form = EventForm(request.POST if request.method == "POST" else None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            event = create_event(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            if hasattr(error, "message_dict"):
                for field, issues in error.message_dict.items():
                    form.add_error(field if field in form.fields else None, issues)
            else:
                form.add_error(None, error)
        else:
            return redirect("events:detail", event_id=event.pk)
    return render(request, "events/form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def edit(request, event_id):
    event = _event(request, event_id)
    form = EventEditForm(request.POST if request.method == "POST" else None, instance=event, actor=request.user)
    conflict = False
    status = 200
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            current = _event(request, event_id, lock=True)
            if form.cleaned_data["expected_revision"] != current.revision:
                # Nothing is written. Show the latest snapshot alongside the
                # retained input; a second explicit save uses that shown base.
                conflict = True
                status = 409
                event = current
                retained = request.POST.copy()
                retained["expected_revision"] = str(current.revision)
                form = EventEditForm(retained, instance=current, actor=request.user)
                form.add_error(None, "La ficha o el plan cambió mientras editabas. No guardamos tus cambios. Compara la ficha actual con tus campos antes de volver a guardar.")
            else:
                values = {key: value for key, value in form.cleaned_data.items() if key != "expected_revision"}
                try:
                    event = update_event(event_id=current.pk, actor=request.user, **values)
                except ValidationError as error:
                    if hasattr(error, "message_dict"):
                        for field, issues in error.message_dict.items():
                            form.add_error(field if field in form.fields else None, issues)
                    else:
                        form.add_error(None, error)
                else:
                    messages.success(request, "Ficha guardada. El plan aprobado se conserva; prepara una nueva propuesta si necesita cambios.")
                    return redirect("events:detail", event_id=event.pk)
    return render(request, "events/form.html", {"form": form, "event": event, "editing": True, "conflict": conflict}, status=status)


def _interview_context(event, *, question=None, form=None, conflict=False, summary_mode=False):
    interview = build_interview_context(event.interview_answers)
    url = reverse("events:interview", kwargs={"event_id": event.pk})
    navigation = []
    for entry in interview["entries"]:
        entry["edit_url"] = url + "?question=" + entry["key"]
        entry["source_label"] = {
            "missing": "Todavía no revisado.",
            "organizer_declaration": "Dato declarado por ti; no verificado externamente.",
            "organizer_reference_to_brief": "Referencia indicada por ti a la descripción guardada.",
        }[entry["source"]]
        navigation.append({
            "key": entry["key"], "label": entry["label"], "url": entry["edit_url"],
            "status": entry["status"], "is_current": question is not None and question.key == entry["key"],
        })
    saved = next((entry for entry in interview["entries"] if question and entry["key"] == question.key), None)
    if saved is not None:
        saved = {**saved, "revision": event.revision}
    return {
        "event": event, "demo": get_demo_context(event), "interview": interview,
        "question_nav": navigation, "question": question, "form": form,
        "summary_mode": summary_mode, "conflict": conflict, "saved_answer": saved,
    }


@login_required
@require_http_methods(["GET", "POST"])
def interview(request, event_id):
    event = _event(request, event_id)
    summary = build_interview_context(event.interview_answers)
    key = request.POST.get("question_key") if request.method == "POST" else request.GET.get("question")
    if key is not None and key not in QUESTION_BY_KEY:
        return HttpResponseBadRequest("La pregunta no es válida.")
    summary_mode = request.method == "GET" and request.GET.get("view") == "summary"
    if request.method == "GET" and key is None and summary["next_question"] is None:
        summary_mode = True
    if summary_mode:
        return render(request, "events/interview.html", _interview_context(event, summary_mode=True))
    question = QUESTION_BY_KEY.get(key or summary["next_question"] or QUESTIONS[0].key)
    form = InterviewForm(request.POST if request.method == "POST" else None, instance=event, question=question)
    conflict = False
    response_status = 200
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action", "save")
        if action not in {"save", "summary"}:
            form.add_error(None, "La acción no es válida.")
        else:
            with transaction.atomic():
                current = _event(request, event_id, lock=True)
                if form.cleaned_data["expected_revision"] != current.revision:
                    conflict = True
                    response_status = 409
                    event = current
                    retained = request.POST.copy()
                    retained["expected_revision"] = str(current.revision)
                    form = InterviewForm(retained, instance=current, question=question)
                    form.add_error(None, "La ficha o el plan cambió. No guardamos tu respuesta. Compara los datos actuales con tus campos antes de volver a guardar.")
                else:
                    try:
                        event = update_interview(
                            event_id=current.pk, actor=request.user,
                            expected_revision=form.cleaned_data["expected_revision"], question_key=question.key,
                            status=form.cleaned_data["status"], value=form.cleaned_data["value"],
                        )
                    except ValidationError as error:
                        form.add_error(None, error)
                    else:
                        messages.success(request, "Respuesta guardada. La agenda y el avance de tareas se conservan.")
                        destination = reverse("events:interview", kwargs={"event_id": event.pk})
                        next_key = build_interview_context(event.interview_answers)["next_question"]
                        if action == "summary" or next_key is None:
                            destination += "?view=summary"
                        else:
                            destination += "?question=" + next_key
                        return redirect(destination)
    return render(request, "events/interview.html", _interview_context(
        event, question=question, form=form, conflict=conflict,
    ), status=response_status)


def _detail_context(request, event, *, tracking=None):
    from apps.ai_management.model_policy import request_policy_context
    generate_key, chat_key = str(uuid.uuid4()), str(uuid.uuid4())
    snapshot = chat_snapshot = None
    requested_task = request.GET.get("task", "")
    if not 1 <= len(requested_task) <= 64:
        requested_task = None
    if tracking is None:
        tracking = task_tracking_context(event, open_task_id=requested_task)
    account = AIAccount.objects.filter(owner=request.user).select_related("active_profile").first()
    ai_configured = chat_configured = False
    if account is not None:
        try:
            from apps.ai_management.agent_access import agent_preview_snapshot
            snapshot = agent_preview_snapshot(account)
            from apps.assistant import provider
            ai_configured = provider.profile_ready(snapshot)
        except ValidationError:
            pass
        try:
            chat_snapshot = agent_preview_snapshot(account, kind=Job.Kind.CHAT)
            from apps.assistant import provider
            chat_configured = provider.profile_ready(chat_snapshot)
        except ValidationError:
            pass
    candidates = event.candidates.order_by("-created_at", "-id")
    candidate = candidates.filter(status=PlanCandidate.Status.PENDING).first()
    impact = None
    if candidate and not candidate.validation and not validate_plan(candidate.payload):
        impact = plan_impact(event.active_plan.payload if event.active_plan_id else None, candidate.payload)
    from apps.jobs.presentation import romeo_context
    return {
        "romeo": romeo_context(event=event, actor=request.user),
        "event": event, "demo": get_demo_context(event),
        "plan": event.active_plan.payload if event.active_plan_id else None,
        "journey_demo": get_journey_demo_context(event),
        "candidate": candidate, "candidates": candidates[:10],
        "jobs": event.jobs.order_by("-created_at", "-id")[:5],
        "chat_messages": _chat_history(event),
        "ai_configured": ai_configured,
        "chat_configured": chat_configured,
        "chat_model_name": chat_snapshot["name"] if chat_snapshot else None,
        "impact": impact, "generate_key": generate_key, "chat_key": chat_key,
        "generate_model_policy": request_policy_context(None if snapshot and snapshot.get("agent_route") in {"fallback_budget", "free_pool", "free_pool_budget"} else snapshot, event=event,
            actor=request.user, kind=Job.Kind.PLAN, request_key=generate_key),
        "chat_model_policy": request_policy_context(None if chat_snapshot and chat_snapshot.get("agent_route") in {"fallback_budget", "free_pool", "free_pool_budget"} else chat_snapshot, event=event,
            actor=request.user, kind=Job.Kind.CHAT, request_key=chat_key),
        "ai_model_name": snapshot["name"] if snapshot else None,
        "ai_model_isolated": bool(snapshot and snapshot["provider"] in {"opencode", "openai"}),
        "task_tracking": tracking,
        "active_panel": "preparation" if tracking and any(
            row["id"].strip() == requested_task for row in tracking["rows"]
        ) else None,
        "interview": build_interview_context(event.interview_answers),
    }


@login_required
@require_GET
def detail(request, event_id):
    if (getattr(request, "portal_role", None) or get_role(request.user)) == "reviewer":
        event = get_object_or_404(visible_events(request.user).select_related("active_plan"), pk=event_id)
        tracking = task_tracking_context(event)
        return render(request, "events/review.html", {"event": event, "task_tracking": tracking})
    event = _event(request, event_id)
    return render(request, "events/detail.html", _detail_context(request, event))


def _task_redirect(event):
    return redirect(reverse("events:detail", kwargs={"event_id": event.pk}) + "#preparation")


@login_required
@require_POST
def task_progress(request, event_id):
    event = _event(request, event_id)
    identifier = request.POST.get("task_id", "").strip()
    try:
        plan_id = uuid.UUID(request.POST.get("expected_plan", ""))
    except (ValueError, TypeError, AttributeError):
        return HttpResponse("Falta la referencia del plan. Recarga el evento.", status=400)
    if not identifier or len(identifier) > 64:
        return HttpResponse("La referencia de la tarea no es válida.", status=400)
    plan = get_object_or_404(PlanRevision, event=event, pk=plan_id)
    if not any(isinstance(task, dict) and str(task.get("id", "")).strip() == identifier
               for task in plan.payload.get("tasks", [])):
        raise Http404
    form = TaskStatusForm(request.POST)
    result = "error"
    feedback = "Revisa los campos indicados."
    bound = form
    stale_plan = False
    if form.is_valid():
        try:
            update_task_progress(
                event=event, actor=request.user, plan_id=form.cleaned_data["expected_plan"],
                task_id=form.cleaned_data["task_id"], status=form.cleaned_data["status"],
                expected_version=form.cleaned_data["expected_version"],
                request_key=form.cleaned_data["request_key"], note=form.cleaned_data["note"],
            )
        except ValidationError as error:
            code = getattr(error, "code", "")
            feedback = " ".join(error.messages)
            if code in {"stale_task", "stale_task_plan"}:
                result = "conflict"
                bound = None
                stale_plan = code == "stale_task_plan"
            else:
                form.add_error("note" if code == "note_required" else None, error)
        else:
            result = "saved"
            feedback = "Estado guardado."
            bound = None
    event = _event(request, event_id)
    stale_plan = stale_plan or event.active_plan_id != plan.pk
    tracking = task_tracking_context(
        event, plan=plan, task_id=identifier, form=bound, feedback=feedback, result=result,
        note_hint=form.cleaned_data.get("note", "") if result == "conflict" else "",
    )
    task = next(row for row in tracking["rows"] if row["id"].strip() == identifier)
    if not _htmx(request):
        if result == "saved":
            messages.success(request, feedback)
            if task["tracking"]["next_task"]:
                return redirect(task["tracking"]["next_task"]["url"])
            return _task_redirect(event)
        if stale_plan:
            messages.error(request, feedback)
            return _task_redirect(event)
    if not _htmx(request):
        context = _detail_context(request, event, tracking=tracking)
        context["active_panel"] = "preparation"
        return render(request, "events/detail.html", context, status=400)
    markup = render_to_string("events/_preparation_row.html", {
        "event": event, "task": task, "position": task["position"],
    }, request=request)
    if not stale_plan:
        markup += render_to_string("events/_task_progress_summary.html", {
            "task_tracking": tracking, "oob": True,
        }, request=request)
    return HttpResponse(markup)


@login_required
@require_POST
def generate(request, event_id):
    event = _event(request, event_id)
    form = AIRequestForm(request.POST)
    if not form.is_valid():
        return _error_response(request, event, _form_error(form))
    try:
        with transaction.atomic():
            current = _event(request, event_id, lock=True)
            expected = form.cleaned_data.get("expected_revision")
            if expected is not None and expected != current.revision:
                raise ValidationError("Los datos del evento cambiaron. Recarga la página antes de solicitar una propuesta.")
            current_job = enqueue(event=current, actor=request.user, kind=Job.Kind.PLAN,
                prompt=form.cleaned_data["brief"] or DEFAULT_PLAN_PROMPT,
                idempotency_key=str(form.cleaned_data["idempotency_key"]),
                model_policy_token=form.cleaned_data["model_policy_token"] if form.cleaned_data["accept_model_policy"] else None)
    except ValidationError as error:
        return _error_response(request, event, error)
    return _job_response(request, event, current_job, rotate="generate")


@login_required
@require_POST
def chat(request, event_id):
    event = _event(request, event_id)
    form = ChatForm(request.POST)
    if not form.is_valid():
        return _error_response(request, event, _form_error(form))
    try:
        local_reply = local_directory_reply(event=event, actor=request.user,
            prompt=form.cleaned_data["message"], request_key=form.cleaned_data["idempotency_key"])
        if local_reply is not None:
            if not _htmx(request):
                return redirect(reverse("events:detail", kwargs={"event_id": event.pk}) + "#agent-panel")
            history = render_to_string("events/_chat_messages.html", {"chat_messages": _chat_history(event)}, request=request)
            markup = str(format_html('<div class="notice" role="status" data-romeo-local-completed>Consulta local completada, sin llamadas a un modelo de IA.</div>'))
            markup += history.replace('<div id="chat-messages"', '<div hx-swap-oob="outerHTML" id="chat-messages"', 1)
            key = uuid.uuid4()
            markup += str(format_html('<input type="hidden" id="chat-request-key" name="idempotency_key" value="{}" hx-swap-oob="outerHTML">', key))
            markup += _model_policy_markup(request, event, "chat", key)
            return HttpResponse(markup)
        with transaction.atomic():
            current_job = enqueue(event=event, actor=request.user, kind=Job.Kind.CHAT,
                prompt=form.cleaned_data["message"], idempotency_key=str(form.cleaned_data["idempotency_key"]),
                model_policy_token=form.cleaned_data["model_policy_token"] if form.cleaned_data["accept_model_policy"] else None)
            Message.objects.get_or_create(event=event, role="user", request_key=str(current_job.pk), defaults={"content": form.cleaned_data["message"]})
    except ValidationError as error:
        return _error_response(request, event, error)
    return _job_response(request, event, current_job, rotate="chat", include_chat=True)


def _check_displayed_snapshot(request, candidate):
    try:
        revision = int(request.POST.get("expected_revision", ""))
        raw_plan = request.POST.get("expected_plan", "")
        expected_plan = uuid.UUID(raw_plan) if raw_plan else None
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Falta la referencia de la propuesta mostrada. Recarga y revísala nuevamente.") from exc
    if revision != candidate.base_revision or expected_plan != candidate.base_plan_id:
        raise ValidationError("La referencia mostrada no coincide con esta propuesta. Recarga y revísala nuevamente.")


@login_required
@require_POST
def approve(request, event_id, candidate_id):
    event = _event(request, event_id)
    candidate = get_object_or_404(PlanCandidate, event=event, pk=candidate_id)
    try:
        _check_displayed_snapshot(request, candidate)
        approve_candidate(candidate_id=candidate.pk, actor=request.user)
    except ValidationError as error:
        return _error_response(request, event, error)
    messages.success(request, "La propuesta quedó aprobada. Puedes consultar el plan vigente.")
    if event.pk == JOURNEY_EVENT_ID and request.POST.get("return_to_demo") == "1":
        return redirect("events:journey_demo", event_id=event.pk)
    return redirect("events:detail", event_id=event.pk)


@login_required
@require_POST
def reject(request, event_id, candidate_id):
    event = _event(request, event_id)
    candidate = get_object_or_404(PlanCandidate, event=event, pk=candidate_id)
    try:
        reject_candidate(candidate_id=candidate.pk, actor=request.user)
    except ValidationError as error:
        return _error_response(request, event, error)
    messages.success(request, "La propuesta se descartó. El plan vigente se conserva.")
    if event.pk == JOURNEY_EVENT_ID and request.POST.get("return_to_demo") == "1":
        return redirect("events:journey_demo", event_id=event.pk)
    return redirect("events:detail", event_id=event.pk)


@login_required
@require_GET
def job(request, event_id, job_id):
    event = _event(request, event_id)
    current_job = get_object_or_404(Job, event=event, pk=job_id)
    if _htmx(request):
        return _job_response(request, event, current_job, include_chat=current_job.kind == Job.Kind.CHAT and current_job.status == Job.Status.SUCCEEDED)
    return render(request, "events/_job.html", {"event": event, "job": current_job})


@login_required
@require_POST
def cancel(request, event_id, job_id):
    event = _event(request, event_id)
    current_job = get_object_or_404(Job, event=event, pk=job_id)
    try:
        current_job = cancel_job(job_id=current_job.pk, actor=request.user)
    except ValidationError as error:
        if _htmx(request):
            # A worker may finish after the displayed Cancel button was rendered.
            # Keep the fresh job and its result action instead of replacing the
            # entire widget with an error-only fragment.
            current_job.refresh_from_db()
            response = _job_response(request, event, current_job)
            response.write(format_html('<div class="notice notice-error" role="alert">{}</div>', " ".join(error.messages)))
            return response
        return _error_response(request, event, error)
    return _job_response(request, event, current_job)
