"""Public reference questions, bounded retrieval and owner-private reuse.

Nothing returned here is passed to an action interpreter, a model or a prompt.
Only a question explicitly framed as a public information request can leave
the server. An unclear command remains a local clarification.
"""

from datetime import timedelta
import hashlib
import re
import unicodedata
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .interaction_memory import redact_secrets
from .knowledge_memory import knowledge_key, lookup_knowledge, store_knowledge
from .local_commands import human_organizer
from .models import KnowledgeEntry, PublicLookupAttempt
from .public_knowledge import PublicKnowledgeError, lookup_public_knowledge

DAILY_LOOKUP_LIMIT = 20
COOLDOWN_SECONDS = 5
_QUESTION = re.compile(
    r"^(?:que (?:es|son|significa)|quien(?:es)? (?:es|son|fue|fueron)|"
    r"como funciona(?:n)?|para que sirve(?:n)?|explicame(?: que es)?|hablame (?:de|del))\s+(.+)$"
)
_SEARCH = re.compile(
    r"^(?:busca|buscar|consulta|consultar|investiga|investigar)\s+"
    r"(?:en (?:internet|la web|wikipedia)|internet|wikipedia)\s+"
    r"(?:(?:informacion )?(?:sobre|acerca de)\s+)?(.+)$"
)
_PRIVATE = re.compile(
    r"(?:https?://|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:sk-|AIza)[\w-]{8,}|"
    r"\b(?:contrase(?:n|ñ)a|password|api key|clave api|mi cuenta|mis? eventos?|"
    r"mis? participantes?|mis? contactos?|mi agenda|nuestro evento|dni|telefono|celular)\b|"
    r"\+?\d[\d ()-]{7,}\d)", re.IGNORECASE,
)


def public_topic(text, context=""):
    """Conservative framing, not a classifier that invents a user's intent."""
    if context or not isinstance(text, str) or not 1 <= len(text) <= 300:
        return None
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in text):
        return None
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = " ".join(folded.split()).strip(" ¿?¡!.,")
    folded = re.sub(r"^(?:hola[, ]+)?(?:gica|jica|yika|yica|llica|chica)[,: ]+", "", folded)
    folded = re.sub(r"^(?:hola[, ]+|por favor[, ]+)", "", folded)
    folded = re.sub(r"[, ]+por favor$", "", folded)
    folded = re.sub(r"^(?:(?:me )?(?:puedes|podrias) (?:decirme|explicarme|contarme)|dime|explicame|me explicas) (?=que |quien|como |para que )", "", folded)
    match = _SEARCH.fullmatch(folded) or _QUESTION.fullmatch(folded)
    if match is None:
        return None
    topic = match[1].strip(" ¿?¡!.,")
    if len(topic) < 3 or len(topic) > 180 or not re.search(r"[a-z]", topic):
        return None
    if _PRIVATE.search(folded) or redact_secrets(text) != text or any(c in text for c in "<>`{}\\"):
        raise ValidationError("Consulta un tema público sin datos privados, claves ni enlaces.")
    return topic


def _reply(status, reply, **extra):
    return {"handled": True, "status": status, "reply": reply, "tokens": 0, **extra}


def entry_result(entry, origin):
    # Text is displayed literally. This short excerpt may be spoken with capture paused.
    brief = entry.answer[:100].rsplit(" ", 1)[0] if len(entry.answer) > 100 else entry.answer
    if len(entry.answer) > 100:
        brief += "…"
    attribution = "En tu memoria revisada: " if entry.status == "reviewed" else "Referencia de Wikipedia: "
    return _reply(
        "found", attribution + brief,
        answer=entry.answer, sources=entry.sources, entry_id=str(entry.pk), origin=origin,
        review_status=entry.status, expires_at=entry.expires_at.isoformat(),
    )


def _past_result(attempt, owner, topic):
    if attempt.status == "succeeded" and attempt.entry_id:
        entry = lookup_knowledge(owner, topic)
        if entry is not None and entry.pk == attempt.entry_id:
            return entry_result(entry, "memory")
    if attempt.status == "pending":
        return _reply("pending", "Esa consulta ya está en curso. No enviaré otra solicitud.")
    return _reply("unavailable", "Esa consulta terminó sin una respuesta reutilizable. No se ha repetido.")


def answer_public_question(actor, text, request_id, *, context="", allow_network=True):
    owner = human_organizer(actor)
    topic = public_topic(text, context)
    if topic is None:
        return {"handled": False}
    try:
        request_id = uuid.UUID(str(request_id))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError("La consulta necesita un identificador válido.") from None
    fingerprint = hashlib.sha256(knowledge_key(topic).encode("utf-8")).hexdigest()
    # Reserve before HTTP; never hold a database transaction open over the network.
    with transaction.atomic():
        owner = human_organizer(owner, lock=True)
        now = timezone.now()
        attempts = PublicLookupAttempt.objects.filter(owner=owner)
        attempts.filter(finished_at__lt=now - timedelta(days=7)).delete()
        prior = attempts.filter(request_id=request_id).first()
        if prior is not None:
            if prior.query_hash != fingerprint:
                raise ValidationError("El identificador ya pertenece a otra consulta.")
            return _past_result(prior, owner, topic)
        entry = lookup_knowledge(owner, topic)
        if entry is not None:
            PublicLookupAttempt.objects.create(
                owner=owner, request_id=request_id, query_hash=fingerprint,
                status="succeeded", entry=entry, finished_at=timezone.now(),
                network_requested=False,
            )
            return entry_result(entry, "memory")
        stored = KnowledgeEntry.objects.filter(owner=owner, normalized_key=knowledge_key(topic)).first()
        if stored is not None and stored.status in {"disabled", "reviewed"}:
            return _reply("review_needed", "Ese conocimiento está desactivado o su revisión caducó. Puedes revisarlo en Conocimientos de Gica.")
        if not allow_network:
            return _reply("offline", "No tengo una respuesta vigente en tu memoria. Activa Consultar Wikipedia para buscar ese tema público.")
        # A crashed request is never replayed. A new human turn can create a new attempt.
        attempts.filter(status="pending", created_at__lt=now - timedelta(seconds=30)).update(
            status="failed", finished_at=now,
        )
        if attempts.filter(status="pending").exists():
            return _reply("pending", "Ya hay una consulta pública en curso. Espera su resultado.")
        midnight = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        if attempts.filter(network_requested=True, created_at__gte=midnight).count() >= DAILY_LOOKUP_LIMIT:
            return _reply("limited", "Alcanzaste las 20 consultas públicas de hoy. Tu memoria guardada sigue disponible.")
        if attempts.filter(network_requested=True, created_at__gt=now - timedelta(seconds=COOLDOWN_SECONDS)).exists():
            return _reply("limited", "Espera cinco segundos entre consultas públicas. No se envió otra solicitud.")
        attempt = PublicLookupAttempt.objects.create(owner=owner, request_id=request_id, query_hash=fingerprint)
    found, result = None, None
    try:
        found = lookup_public_knowledge(topic)
    except PublicKnowledgeError as error:
        code = "not_found" if error.code in {"not_found", "no_results"} else "unavailable"
        result = _reply(code, "No encontré una referencia adecuada en Wikipedia. Puedes reformular el tema o consultar otras fuentes." if code == "not_found" else "Wikipedia no está disponible ahora. Puedes volver a consultar cuando lo necesites; no haré reintentos automáticos.")
    with transaction.atomic():
        # Authority, live attempt and cache are revalidated together after I/O.
        owner = human_organizer(owner, lock=True)
        current = PublicLookupAttempt.objects.select_for_update().get(pk=attempt.pk, owner=owner)
        if current.status != "pending":
            return _reply("unavailable", "La consulta ya no está vigente. No se enviará otra solicitud.")
        if found is not None:
            try:
                entry = store_knowledge(owner, topic, found["answer"], found["sources"])
                usable = lookup_knowledge(owner, topic)
                if usable is not None and usable.pk == entry.pk:
                    result = entry_result(usable, "wikipedia")
                else:
                    result = _reply("review_needed", "Ese conocimiento ya no está activo. Puedes revisarlo en tu biblioteca.")
            except ValidationError:
                result = _reply("review_needed", "La memoria está llena o la referencia cambió. Revisa Conocimientos de Gica antes de sustituirla.")
        current.status = "succeeded" if result and result["status"] == "found" else "not_found" if result and result["status"] == "not_found" else "failed"
        current.entry_id = result.get("entry_id") if result and result["status"] == "found" else None
        current.finished_at = timezone.now()
        current.save(update_fields=["status", "entry", "finished_at"])
    return result or _reply("unavailable", "No pude comprobar una respuesta. No se ejecutó ninguna acción.")
