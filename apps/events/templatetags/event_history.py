"""Presentation of already-authorized event records; no writes or extra permissions."""
from django import template

register = template.Library()


@register.simple_tag
def primary_event_speaker(event):
    link = event.directory_people.select_related("person").filter(role="speaker", status__in=["planned", "confirmed"]).first()
    return link.person if link else None


@register.simple_tag
def event_plan_history(event):
    rows = []
    for plan in event.plan_revisions.order_by("-version")[:20]:
        sessions = plan.payload.get("sessions", [])
        rows.append({"version": plan.version, "approved_at": plan.approved_at,
                     "speaker": sessions[0].get("speaker", "Por confirmar") if sessions else "Por confirmar",
                     "start": sessions[0].get("start", "") if sessions else ""})
    return rows


@register.simple_tag
def event_proposal_history(event):
    rows = []
    for candidate in event.candidates.select_related("approved_revision").order_by("-created_at")[:10]:
        approved = getattr(candidate, "approved_revision", None)
        rows.append({"status": candidate.get_status_display(), "created_at": candidate.created_at,
                     "version": approved.version if approved else None, "summary": candidate.payload.get("summary", ""),
                     "base_revision": candidate.base_revision})
    return rows


@register.simple_tag
def event_communications(event):
    """Unsent drafts from the last validated compact proposal for this event."""
    from apps.assistant.models import CompactPlanRequest
    record = CompactPlanRequest.objects.filter(job__event_id=event.pk, job__actor_id=event.owner_id,
        job__status="succeeded", response__state="proposal", review_only=False).order_by("-created_at").first()
    if record is None:
        return []
    return record.response.get("communications", [])


@register.simple_tag(takes_context=True)
def event_compact_retry(context, event):
    """Only an eligible identifier; the API rechecks actor, revision and budgets."""
    from apps.assistant.compact_planning import retry_source
    actor = getattr(context.get("request"), "user", None)
    if actor is None or not actor.is_authenticated or actor.pk != event.owner_id:
        return ""
    source = retry_source(event=event, actor=actor)
    return str(source.job_id) if source else ""
