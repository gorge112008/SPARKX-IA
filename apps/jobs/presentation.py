"""Owner-scoped operational presentation for Gica-1."""

from django.core.exceptions import ObjectDoesNotExist

from apps.ai_management.models import AIAccount
from apps.ai_management.pilot import OPENAI_PILOT_LIMIT_USD, openai_pilot_summary
from .models import Job
from .trace import trace_rows


def romeo_context(*, event, actor):
    latest = event.jobs.select_related("ai_usage").order_by("-created_at", "-id").first()
    usage = None
    if latest:
        try:
            usage = latest.ai_usage
        except ObjectDoesNotExist:
            pass
    account = AIAccount.objects.filter(owner=actor).select_related("active_profile").first()
    model = usage.snapshot.get("model") if usage else (
        account.active_profile.model if account and account.active_profile else None)
    return {
        "route": usage.snapshot.get("agent_route") if usage else None,
        "job": latest, "usage": usage, "model": model, "rows": trace_rows(latest),
        "working": bool(latest and latest.status in {Job.Status.QUEUED, Job.Status.RUNNING}),
        "budget": openai_pilot_summary() if actor.is_superuser else None,
        "limit": OPENAI_PILOT_LIMIT_USD,
    }
