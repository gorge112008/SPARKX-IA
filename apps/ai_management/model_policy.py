"""Explicit per-request consent, bound to the reviewed model and event snapshot.

Tokens contain identifiers and a policy fingerprint, never event text or secrets.
Profile configuration alone never grants consent to remote retention/training.
"""
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone

from tools.opencode.catalog import MODEL_POLICIES, policy_fingerprint

SALT = "sparkx.free-model-policy.v1"
MAX_AGE_SECONDS = 3600


def policy_for(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("provider") != "opencode":
        return None
    return MODEL_POLICIES.get(snapshot.get("model"))


def _binding(snapshot, *, event, actor, kind, request_key):
    return {"model": snapshot["model"], "policy": policy_fingerprint(snapshot["model"]),
            "profile": snapshot["profile_id"], "version": snapshot["profile_version"],
            "actor": actor.pk, "event": str(event.pk), "revision": event.revision,
            "kind": kind, "request_key": str(request_key)}


def request_policy_context(snapshot, *, event, actor, kind, request_key):
    policy = policy_for(snapshot)
    if policy is None or not policy["requires_policy_consent"]:
        return None
    return {"name": policy["name"], "privacy": policy["privacy"],
            "quota_note": policy["quota_note"], "url": policy["policy_url"],
            "token": signing.dumps(_binding(snapshot, event=event, actor=actor,
                kind=kind, request_key=request_key), salt=SALT, compress=True)}


def bind_request_consent(snapshot, *, token, event, actor, kind, request_key):
    """Fail before creating a Job/reservation if this exact request lacks consent."""
    policy = policy_for(snapshot)
    if policy is None or not policy["requires_policy_consent"]:
        return dict(snapshot)
    expected = _binding(snapshot, event=event, actor=actor, kind=kind, request_key=request_key)
    try:
        if type(token) is not str or len(token) > 4096:
            raise ValueError
        observed = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
        if observed != expected:
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError(
            "Revisa y acepta las condiciones del modelo para esta solicitud. "
            "Si cambió el perfil o pasó una hora, recarga la página.", code="model_policy_required") from None
    return {**snapshot, "model_policy_consent": {"token": token,
        "model": snapshot["model"], "fingerprint": expected["policy"],
        "acknowledged_at": timezone.now().isoformat()}}


def validate_job_consent(snapshot, *, event, actor, kind, request_key):
    receipt = snapshot.get("model_policy_consent")
    bound = bind_request_consent(snapshot, token=receipt.get("token") if type(receipt) is dict else None,
        event=event, actor=actor, kind=kind, request_key=request_key)
    policy = policy_for(snapshot)
    if policy and policy["requires_policy_consent"] and (
        type(receipt) is not dict or receipt.get("model") != snapshot["model"]
        or receipt.get("fingerprint") != bound["model_policy_consent"]["fingerprint"]
    ):
        raise ValidationError("La aceptación de privacidad ya no coincide con el modelo.", code="model_policy_required")

