"""Bounded human UI API. It enqueues work; HTTP requests never run a model."""
import json
import uuid

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.jobs.models import Job
from apps.events.models import Event
from apps.planning.models import PlanCandidate
from .compact_contract import present_questions
from .compact_planning import ALLOWED_MODELS, OPENAI_MODELS, enqueue_compact, cancel_compact, compact_preview
from .compact_archive import archive_compact
from .demo_pilot import PILOT_EVENT_ID
from .local_commands import human_organizer
from .models import CompactPlanRequest
from .pilot_workflow import SESSION_KEY, _json_pairs, _invalid_json_constant


def _reply(data, status=200):
    response = JsonResponse(data, status=status)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _scope(request, run_id):
    actor = human_organizer(request.user)
    run = request.session.get(SESSION_KEY)
    if (not isinstance(run, dict) or run.get("owner") != actor.pk or run.get("expires", 0) < timezone.now().timestamp()
            or str(uuid.UUID(str(run_id))) != run.get("id")):
        raise ValidationError("Inicia de nuevo el recorrido.", code="compact_stale")
    return actor, run


def _presentation(record):
    job = record.job
    from apps.ai_management.models import AIUsage
    snapshot = AIUsage.objects.filter(job=job).values_list("snapshot", flat=True).first() or {}
    model = snapshot.get("model")
    response = {"job_id": str(job.pk), "run_id": str(record.run_id), "event_id": str(job.event_id),
        "status": job.status, "poll_url": reverse("assistant:pilot_ai") + f"?job_id={job.pk}&run_id={record.run_id}",
        "max_poll_seconds": 180, "usage": job.result.get("usage") or None}
    if model in ALLOWED_MODELS:
        response.update(model=model, provider="opencode")
    elif model in OPENAI_MODELS and snapshot.get("provider") == "openai":
        response.update(model=model, provider="openai")
    response["review_only"] = record.review_only
    if job.status == Job.Status.SUCCEEDED:
        response["status"] = job.result.get("compact_state", "failed")
        if response["status"] == "questions":
            response["questions"] = present_questions(record.response["questions"])
        elif response["status"] == "proposal":
            candidate = PlanCandidate.objects.filter(pk=job.result.get("candidate_id"), event_id=job.event_id,
                created_by_id=job.actor_id).first()
            if candidate is None:
                response.update(status="failed", error="La propuesta ya no está disponible.")
            elif candidate.base_revision != job.event.revision or candidate.base_plan_id != job.event.active_plan_id:
                response.update(status="stale", error="La ficha o el plan cambiaron. Revisa la propuesta guardada.")
            else:
                response.update(candidate_id=str(candidate.pk), candidate_url=reverse("events:detail", args=[job.event_id]) + "#candidate",
                    approve_url=reverse("events:approve", args=[job.event_id, candidate.pk]),
                    communications=job.result.get("communications", []), validation=candidate.validation)
    if job.error:
        response["error"] = job.error
    if job.result.get("diagnostic") == {"phase": "contract", "code": "compact_invalid"}:
        response["code"] = "compact_invalid"
    if job.status in ("queued", "running", "succeeded") and (job.base_revision != job.event.revision or job.base_plan_id != job.event.active_plan_id):
        response.update(status="stale", error="La ficha o el plan cambiaron. La respuesta anterior no se aplicará.")
    return response


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def pilot_ai(request):
    try:
        if request.method == "GET":
            if set(request.GET) != {"job_id", "run_id"}:
                raise ValidationError("Revisa la consulta de estado.")
            actor, run = _scope(request, request.GET["run_id"])
            record = CompactPlanRequest.objects.select_related("job__event").filter(job_id=uuid.UUID(request.GET["job_id"]),
                run_id=run["id"], job__actor=actor, job__event__owner=actor, job__event_id=PILOT_EVENT_ID).first()
            return _reply(_presentation(record)) if record else _reply({"error": "Solicitud no disponible."}, 404)
        if request.content_type != "application/json" or len(request.body) > 12000:
            raise ValidationError("Se requiere JSON acotado.")
        data = json.loads(request.body, object_pairs_hook=_json_pairs, parse_constant=_invalid_json_constant)
        if type(data) is not dict or data.get("operation") not in {"start", "answers", "retry", "cancel", "preview", "archive"}:
            raise ValidationError("La operación no está permitida.")
        operation = data["operation"]
        expected = {"operation", "run_id", "event_id", "expected_revision", "request_key"}
        if operation == "answers":
            expected |= {"parent_job_id", "answers"}
        elif operation == "retry":
            expected.add("failed_job_id")
        elif operation == "start" and "review_only" in data:
            expected.add("review_only")
        elif operation == "preview":
            expected = {"operation", "run_id", "event_id", "expected_revision"}
            if "parent_job_id" in data or "answers" in data:
                expected |= {"parent_job_id", "answers"}
            if "failed_job_id" in data:
                expected.add("failed_job_id")
        elif operation == "archive":
            expected = {"operation", "run_id", "event_id", "job_id"}
        elif operation == "cancel":
            expected = {"operation", "run_id", "event_id", "job_id" if "job_id" in data else "request_key"}
        if operation in {"start", "preview"} and "provider" in data:
            expected.add("provider")
        if operation in {"start", "preview"} and "change_request" in data:
            if data["change_request"] != "more_case_time" or not isinstance(data["change_request"], str):
                raise ValidationError("Elige el cambio acotado de ampliar el caso práctico.", code="compact_change_invalid")
            expected.add("change_request")
        if set(data) != expected or str(uuid.UUID(str(data["event_id"]))) != str(PILOT_EVENT_ID):
            raise ValidationError("Los campos no corresponden al recorrido autorizado.")
        actor, run = _scope(request, data["run_id"])
        if operation == "preview":
            return _reply(compact_preview(actor=actor, event_id=PILOT_EVENT_ID, run_id=run["id"], expected_revision=data["expected_revision"],
                parent_job_id=uuid.UUID(str(data["parent_job_id"])) if "parent_job_id" in data else None,
                answers=data.get("answers"), provider_name=data.get("provider"),
                failed_job_id=uuid.UUID(str(data["failed_job_id"])) if "failed_job_id" in data else None,
                change_request=data.get("change_request")))
        if operation == "archive":
            return _reply(archive_compact(actor=actor, event_id=PILOT_EVENT_ID, run_id=run["id"], job_id=uuid.UUID(str(data["job_id"]))))
        if operation == "cancel":
            key = uuid.UUID(str(data["request_key"])) if "request_key" in data else None
            record = cancel_compact(actor=actor, event_id=PILOT_EVENT_ID, run_id=run["id"], request_key=key,
                job_id=uuid.UUID(str(data["job_id"])) if "job_id" in data else None)
            if record is None:
                if key is not None:
                    return _reply({"status": "cancelled", "job_id": None, "request_key": str(key),
                        "run_id": run["id"], "event_id": str(PILOT_EVENT_ID)})
                return _reply({"status": "not_found", "error": "Solicitud no disponible."}, 404)
            return _reply(_presentation(record))
        job = enqueue_compact(actor=actor, event_id=PILOT_EVENT_ID, run_id=run["id"],
            expected_revision=data["expected_revision"], request_key=data["request_key"],
            parent_job_id=uuid.UUID(str(data["parent_job_id"])) if operation == "answers" else None,
            answers=data.get("answers"), review_only=data.get("review_only", False), provider_name=data.get("provider"),
            failed_job_id=uuid.UUID(str(data["failed_job_id"])) if operation == "retry" else None,
            change_request=data.get("change_request"))
        record = CompactPlanRequest.objects.select_related("job__event").get(job=job)
        return _reply(_presentation(record), 202)
    except PermissionDenied:
        return _reply({"error": "Se requiere una cuenta humana organizadora vigente."}, 403)
    except Event.DoesNotExist:
        return _reply({"error": "Evento no disponible."}, 404)
    except (ValidationError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        messages = " ".join(error.messages) if isinstance(error, ValidationError) else "La solicitud no tiene un formato válido."
        code = getattr(error, "code", "compact_invalid")
        return _reply({"error": messages, "code": code}, 409 if code in {"compact_stale", "free_gateway_cooldown"} else 400)
