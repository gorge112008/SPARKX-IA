"""Bounded owner-private knowledge cache. External text never becomes authority.

Only exact normalized questions are reused. This module has no network, model,
job, conversation-log or command-pattern integrations.
"""

from datetime import timedelta
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .interaction_memory import redact_secrets
from .models import KnowledgeEntry

ENTRY_LIMIT = 200
QUESTION_LIMIT = 300
ANSWER_LIMIT = 1800
SOURCE_LIMIT = 3
MAX_TTL_HOURS = 168
_LANGUAGE_HOST = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]{2,12})?\.wikipedia\.org\Z")
_KEYWORD = re.compile(r"[a-z0-9]{2,40}")
_STOPWORDS = frozenset({
    "que", "es", "son", "el", "la", "los", "las", "un", "una", "de", "del", "en", "y",
    "por", "para", "con", "como", "cual", "cuales", "me", "puedes", "sobre", "explica",
})


def _human(actor, *, lock=False):
    # Local import keeps the memory store independent of the command parser.
    from .local_commands import human_organizer

    return human_organizer(actor, lock=lock)


def _text(value, *, limit, field):
    if (
        not isinstance(value, str) or not value or len(value) > limit
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        raise ValidationError({field: "Usa texto sin controles y dentro del límite permitido."})
    value = unicodedata.normalize("NFC", value).strip()
    if not value or len(value) > limit:
        raise ValidationError({field: "El texto no puede estar vacío ni superar su límite."})
    if redact_secrets(value) != value:
        raise ValidationError({field: "No se guardan credenciales en la memoria de conocimientos."})
    return value


def knowledge_key(question):
    """Accent/case/compatibility/space fold only; no fuzzy or semantic equivalence."""
    question = _text(question, limit=QUESTION_LIMIT, field="question")
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", question).casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    key = " ".join(folded.split())
    if not key or len(key) > QUESTION_LIMIT:
        raise ValidationError({"question": "La pregunta normalizada supera su límite."})
    return key


def validate_source_url(value):
    """A citation allowlist, not a general-purpose URL fetcher or SSRF boundary."""
    value = _text(value, limit=1000, field="sources")
    if any(char.isspace() for char in value) or "\\" in value:
        raise ValidationError({"sources": "La fuente no es un artículo HTTPS permitido."})
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (
            parts.scheme != "https" or not _LANGUAGE_HOST.fullmatch(host)
            or parts.netloc != host or parts.username is not None or parts.password is not None
            or parts.port is not None or parts.query or parts.fragment
            or not parts.path.startswith("/wiki/") or len(parts.path) <= len("/wiki/")
        ):
            raise ValueError
        path = unquote(parts.path, errors="strict")
        if (
            any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in path)
            or "\\" in path or any(piece in {".", ".."} for piece in path.split("/"))
            or "%" in path
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValidationError({"sources": "La fuente no es un artículo HTTPS permitido."}) from None
    canonical = "https://" + host + quote(unicodedata.normalize("NFC", path), safe="/:()!,;@-._~")
    if len(canonical) > 1000:
        raise ValidationError({"sources": "La URL de la fuente supera su límite."})
    return canonical


def validate_sources(sources):
    if not isinstance(sources, list) or not 1 <= len(sources) <= SOURCE_LIMIT:
        raise ValidationError({"sources": "Conserva entre una y tres fuentes permitidas."})
    result = []
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"title", "url"}:
            raise ValidationError({"sources": "Cada fuente debe tener sólo título y URL."})
        title = _text(source["title"], limit=200, field="sources")
        url = validate_source_url(source["url"])
        if url in seen:
            raise ValidationError({"sources": "No repitas la misma fuente."})
        seen.add(url)
        result.append({"title": title, "url": url})
    return result


def _ttl(ttl_hours):
    if type(ttl_hours) is not int or not 1 <= ttl_hours <= MAX_TTL_HOURS:
        raise ValidationError({"ttl_hours": "La vigencia debe ser de 1 a 168 horas enteras."})
    return timedelta(hours=ttl_hours)


def _keywords(key):
    return list(dict.fromkeys(word for word in _KEYWORD.findall(key) if word not in _STOPWORDS))[:12]


def lookup_knowledge(actor, question):
    owner = _human(actor)
    key = knowledge_key(question)
    entry = KnowledgeEntry.objects.filter(
        owner=owner, normalized_key=key,
        status__in=[KnowledgeEntry.Status.AUTO, KnowledgeEntry.Status.REVIEWED],
        expires_at__gt=timezone.now(),
    ).first()
    if entry is not None:
        # Fail closed even if a row was inserted outside the bounded service.
        _text(entry.answer, limit=ANSWER_LIMIT, field="answer")
        validate_sources(entry.sources)
    return entry


@transaction.atomic
def store_knowledge(actor, question, answer, sources, ttl_hours=24):
    owner = _human(actor, lock=True)
    question = _text(question, limit=QUESTION_LIMIT, field="question")
    key = knowledge_key(question)
    answer = _text(answer, limit=ANSWER_LIMIT, field="answer")
    sources = validate_sources(sources)
    lifetime = _ttl(ttl_hours)
    existing = KnowledgeEntry.objects.filter(owner=owner, normalized_key=key).first()
    if existing is not None:
        # Automatic refresh cannot undo manual decisions or silently change facts.
        if existing.status in {KnowledgeEntry.Status.REVIEWED, KnowledgeEntry.Status.DISABLED}:
            return existing
        if existing.answer != answer or existing.sources != sources:
            raise ValidationError({
                "answer": "Existe otra respuesta para esta pregunta. Revísala antes de sustituirla."
            })
        if existing.expires_at > timezone.now():
            return existing
    elif KnowledgeEntry.objects.filter(owner=owner).count() >= ENTRY_LIMIT:
        raise ValidationError({"question": "La memoria alcanzó sus 200 conocimientos. Elimina alguno."})
    now = timezone.now()
    entry = existing or KnowledgeEntry(owner=owner, normalized_key=key)
    entry.question, entry.answer, entry.sources = question, answer, sources
    entry.keywords = _keywords(key)
    entry.status = KnowledgeEntry.Status.AUTO
    entry.fetched_at, entry.expires_at, entry.reviewed_at = now, now + lifetime, None
    entry.full_clean()
    entry.save()
    return entry


def _owned_entry(owner, entry_id):
    try:
        key = uuid.UUID(str(entry_id))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError({"id": "El identificador del conocimiento no es válido."}) from None
    entry = KnowledgeEntry.objects.select_for_update().filter(owner=owner, pk=key).first()
    if entry is None:
        raise PermissionDenied("El conocimiento no está disponible para esta cuenta.")
    return entry


@transaction.atomic
def update_knowledge(actor, entry_id, *, answer=None, status=None, ttl_hours=24):
    """Explicit manual correction/review. No field can add actions or change owner."""
    owner = _human(actor, lock=True)
    if answer is None and status is None:
        raise ValidationError({"answer": "Indica una corrección o un estado de revisión."})
    if status is not None and status not in KnowledgeEntry.Status.values:
        raise ValidationError({"status": "El estado del conocimiento no es válido."})
    lifetime = _ttl(ttl_hours)
    entry = _owned_entry(owner, entry_id)
    if answer is not None:
        entry.answer = _text(answer, limit=ANSWER_LIMIT, field="answer")
        # A human-edited answer is reviewed rather than misattributed to the web.
        entry.status = KnowledgeEntry.Status.REVIEWED
        entry.reviewed_at = timezone.now()
    if status is not None:
        entry.status = status
        entry.reviewed_at = timezone.now() if status == KnowledgeEntry.Status.REVIEWED else None
    if entry.status == KnowledgeEntry.Status.REVIEWED:
        entry.expires_at = timezone.now() + lifetime
    entry.full_clean()
    entry.save()
    return entry


def review_knowledge(actor, entry_id, *, status="reviewed", ttl_hours=24):
    return update_knowledge(actor, entry_id, status=status, ttl_hours=ttl_hours)


def edit_knowledge(actor, entry_id, *, answer, ttl_hours=24):
    return update_knowledge(actor, entry_id, answer=answer, ttl_hours=ttl_hours)


@transaction.atomic
def delete_knowledge(actor, entry_id):
    owner = _human(actor, lock=True)
    entry = _owned_entry(owner, entry_id)
    entry.delete()
