"""Private client-declared text records. No interpretation, training or execution."""

import hashlib
import json
import math
import re
import unicodedata
import uuid

from django.db import transaction

from apps.jobs.command_language import ACTION_IDS
from apps.jobs.models import UIAction

from .local_commands import human_organizer
from .models import InteractionRecord

RECORD_LIMIT = 1000
TIMING_KEYS = frozenset({
    "speech_end_to_dispatch_ms", "final_to_dispatch_ms", "guide_roundtrip_ms",
    "guide_server_ms", "response_to_tts_ms", "speech_end_to_tts_ms", "tts_duration_ms",
    "text_change_to_dispatch_ms",
})
PAYLOAD_FIELDS = frozenset({
    "request_id", "session_id", "sequence", "source", "phase", "original_text",
    "normalized_text", "reply", "draft", "status", "intent", "action_id", "outcome",
    "timings", "timing_basis", "consent_version",
})
_SECRET = re.compile(
    r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{8,}"
    r"|\bgsk_[A-Za-z0-9_-]{12,}"
    r"|\bAIza[A-Za-z0-9_-]{20,}"
    r"|\bBearer[ \t]+[A-Za-z0-9._~+/-]{12,}=*",
    re.IGNORECASE,
)


class MemoryError(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message


def redact_secrets(text):
    """Recognizable key/token formats only; this is not universal DLP."""
    return _SECRET.sub("[CREDENCIAL OCULTA]", text)


def _invalid():
    raise MemoryError("invalid", "El registro no cumple el formato textual permitido.")


def _text(value, limit):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        _invalid()
    return value


def _uuid(value):
    if not isinstance(value, str):
        _invalid()
    try:
        return str(uuid.UUID(value))
    except ValueError:
        _invalid()


def validate_payload(data):
    if not isinstance(data, dict) or set(data) != PAYLOAD_FIELDS:
        _invalid()
    if data["consent_version"] != "3":
        raise MemoryError("consent", "Acepta el aviso vigente antes de registrar interacciones.")
    if type(data["sequence"]) is not int or not 1 <= data["sequence"] <= 10000:
        _invalid()
    text_fields = {"original_text": 300, "normalized_text": 300, "reply": 500, "draft": 300}
    payload = {key: _text(data[key], limit) for key, limit in text_fields.items()}
    choices = {
        "source": InteractionRecord.Source.values,
        "phase": InteractionRecord.Phase.values,
        "status": InteractionRecord.Status.values,
        "intent": ACTION_IDS | {""},
        "outcome": InteractionRecord.Outcome.values,
        "timing_basis": InteractionRecord.TimingBasis.values,
    }
    for key, allowed in choices.items():
        if not isinstance(data[key], str) or data[key] not in allowed:
            _invalid()
        payload[key] = data[key]
    if not isinstance(data["action_id"], str):
        _invalid()
    payload.update({
        "request_id": _uuid(data["request_id"]),
        "session_id": _uuid(data["session_id"]),
        "sequence": data["sequence"],
        "action_id": _uuid(data["action_id"]) if data["action_id"] else "",
        "consent_version": "3",
    })
    timings = data["timings"]
    if not isinstance(timings, dict) or not set(timings).issubset(TIMING_KEYS):
        _invalid()
    payload["timings"] = {}
    for key, value in timings.items():
        if type(value) not in {int, float} or not 0 <= value <= 120000 or not math.isfinite(value):
            _invalid()
        payload["timings"][key] = float(value)
    return payload


def save_interaction(*, actor, data):
    payload = validate_payload(data)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with transaction.atomic():
        owner = human_organizer(actor, lock=True)
        existing = InteractionRecord.objects.filter(
            owner=owner, request_id=payload["request_id"]
        ).first()
        if existing is not None:
            if existing.payload_hash != fingerprint:
                raise MemoryError(
                    "conflict", "Ese identificador ya pertenece a otro registro.", status=409
                )
            return existing, False
        if InteractionRecord.objects.filter(owner=owner).count() >= RECORD_LIMIT:
            raise MemoryError(
                "capacity",
                "La memoria está llena. Exporta o elimina registros; este turno no se guardó.",
                status=409,
            )
        action_id = payload.pop("action_id")
        action = None
        if action_id:
            action = UIAction.objects.filter(pk=action_id, actor=owner).first()
            if action is None:
                raise MemoryError("action", "El recibo de acción no pertenece a esta cuenta.")
        for field, limit in {"original_text": 300, "normalized_text": 300, "reply": 500, "draft": 300}.items():
            payload[field] = redact_secrets(payload[field])[:limit]
        payload["consent_version"] = 3
        record = InteractionRecord.objects.create(
            owner=owner, action=action, payload_hash=fingerprint, **payload
        )
        return record, True


def memory_summary(records):
    return {
        "total": records.count(),
        "unreviewed": records.filter(review_status=InteractionRecord.Review.UNREVIEWED).count(),
        "unknown": records.filter(status__in=["unknown", "clarify", "refused"]).count(),
        "limit": RECORD_LIMIT,
    }


def export_record(record):
    action = record.action
    server_action = None
    if action is not None and action.actor_id == record.owner_id:
        server_action = {
            "id": str(action.pk), "action": action.action, "state": action.state,
            "note": "Recibo del servidor; completed sigue siendo una declaración del cliente.",
        }
    return {
        "id": str(record.pk), "request_id": str(record.request_id),
        "session_id": str(record.session_id), "sequence": record.sequence,
        "source": record.source, "phase": record.phase,
        "original_text": redact_secrets(record.original_text),
        "normalized_text": redact_secrets(record.normalized_text),
        "reply": redact_secrets(record.reply), "draft": redact_secrets(record.draft),
        "status": record.status, "intent": record.intent, "outcome": record.outcome,
        "timings": record.timings, "timing_basis": record.timing_basis,
        "consent_version": record.consent_version, "received_at": record.received_at.isoformat(),
        "review_status": record.review_status, "review_note": redact_secrets(record.review_note),
        "suggested_intent": record.suggested_intent,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "server_action": server_action,
    }
