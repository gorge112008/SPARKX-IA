"""Bounded, read-only Wikipedia lookup. This is not a general web search or an LLM.

Only an explicitly selected public topic may reach this adapter. Caller permissions,
consent, quotas, cache and review belong to the application service. Remote extracts
are untrusted quoted data: this module neither follows links nor executes actions.
"""

from __future__ import annotations

import json
import queue
import re
import socket
import threading
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


_ENDPOINT = "https://es.wikipedia.org/w/api.php"
_PROVIDER = "wikipedia"
_SOCKET_TIMEOUT = 4.0
_TOTAL_TIMEOUT = 8.0
_MAX_BYTES = 128 * 1024
_MAX_HITS = 3
_MAX_ANSWER = 1600
_USER_AGENT = "ArquiGica-Gica/0.1 (local educational event-planning prototype; Python urllib)"
# A deadline may expire while the OS is resolving DNS. Daemon threads cannot be
# killed safely; at most two can remain in flight, and neither may retry.
_WORKER_SLOTS = threading.BoundedSemaphore(2)
_URL_OR_DOMAIN = re.compile(r"(?:\bwww\.|\b[a-z0-9-]+\.(?:[a-z]{2,63})(?:\b|/))", re.I)
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class PublicKnowledgeError(Exception):
    """Stable safe error; never includes the response body, headers or query."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _invalid_query():
    return PublicKnowledgeError("invalid_query", "Indica un tema público de hasta 180 caracteres, sin enlaces ni direcciones.")


def _normalize_query(value: str) -> str:
    if type(value) is not str or not value or len(value) > 180:
        raise _invalid_query()
    value = unicodedata.normalize("NFC", value)
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise _invalid_query()
    if any(not (char.isalnum() or unicodedata.category(char).startswith("M") or char in " ¿?¡!.,;()'’\"-") for char in value):
        raise _invalid_query()
    value = " ".join(value.split())
    if not value or len(value) > 180 or _URL_OR_DOMAIN.search(value) or _IPV4.search(value):
        raise _invalid_query()
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublicKnowledgeError("redirect_refused", "La fuente intentó redirigir la consulta; no se siguió el enlace.")


def _request_url(query: str) -> str:
    return _ENDPOINT + "?" + urlencode({
        "action": "query", "format": "json", "formatversion": "2", "utf8": "1",
        "generator": "search", "gsrsearch": query, "gsrnamespace": "0",
        "gsrlimit": str(_MAX_HITS), "gsrwhat": "text", "gsrprop": "",
        "prop": "extracts|info", "inprop": "url", "exintro": "1",
        "explaintext": "1", "exchars": "1200", "exlimit": str(_MAX_HITS),
        "maxlag": "5",
    })


def _fetch(url: str, deadline: float) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PublicKnowledgeError("timeout", "La consulta tardó demasiado. Puedes intentarlo más adelante.")
    request = Request(url, headers={
        "User-Agent": _USER_AGENT, "Accept": "application/json", "Accept-Encoding": "identity",
    }, method="GET")
    # Do not inherit proxy settings or accept any HTTP redirect to another origin.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=min(_SOCKET_TIMEOUT, remaining)) as response:
        if response.geturl() != url:
            raise PublicKnowledgeError("redirect_refused", "La fuente cambió de dirección; no se aceptó la respuesta.")
        if response.status != 200:
            raise PublicKnowledgeError("unavailable", "La fuente no está disponible en este momento.")
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json" or response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise PublicKnowledgeError("invalid_response", "La fuente devolvió un formato no admitido.")
        size = response.headers.get("Content-Length")
        if size is not None and (not size.isdigit() or int(size) > _MAX_BYTES):
            raise PublicKnowledgeError("response_too_large", "La respuesta de la fuente excede el límite permitido.")
        body = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise PublicKnowledgeError("timeout", "La consulta tardó demasiado. Puedes intentarlo más adelante.")
            # read1 returns after at most one underlying buffered read. Slow bodies
            # still cannot delay the caller beyond the outer wall-clock deadline.
            chunk = response.read1(min(8192, _MAX_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > _MAX_BYTES:
                raise PublicKnowledgeError("response_too_large", "La respuesta de la fuente excede el límite permitido.")
        return bytes(body)


def _safe_text(value, maximum: int, *, paragraphs: bool = False) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió contenido no válido.")
    if paragraphs:
        # TextExtracts plaintext can retain citation/layout zero-width spaces.
        # Normalize this observed separator only; bidi controls and every other
        # format/control character remain forbidden, including in article titles.
        value = value.replace("\u200b", " ")
    for char in value:
        if (unicodedata.category(char).startswith("C") and not (paragraphs and char in "\t\n\r")) or char in "<>":
            raise PublicKnowledgeError("invalid_response", "La fuente devolvió contenido no válido.")
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized:
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió contenido no válido.")
    return normalized


def _source_url(value, title: str) -> str:
    if type(value) is not str or len(value) > 2048 or any(ord(char) < 33 for char in value):
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió un enlace no válido.")
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.netloc != "es.wikipedia.org" or parsed.query or parsed.fragment:
            raise ValueError
        # Require well-formed percent escapes and exactly the article we received.
        if re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
            raise ValueError
        path = unicodedata.normalize("NFC", unquote(parsed.path, errors="strict"))
        expected = "/wiki/" + title.replace(" ", "_")
        if path != expected or re.search(r"%[0-9a-fA-F]{2}", path) or any(char in path for char in "<>\\\r\n\x00"):
            raise ValueError
    except (ValueError, UnicodeError):
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió un enlace no válido.") from None
    # Canonical fixed-origin output never incorporates remote URL authority.
    return "https://es.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="")


def _decode(body: bytes, query: str) -> dict:
    if type(body) is not bytes or len(body) > _MAX_BYTES:
        raise PublicKnowledgeError("response_too_large", "La respuesta de la fuente excede el límite permitido.")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió una respuesta no válida.") from None
    if type(data) is not dict:
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió una respuesta no válida.")
    if "error" in data:
        raise PublicKnowledgeError("unavailable", "La fuente no pudo atender esta consulta.")
    if "query" not in data and data.get("batchcomplete") is True:
        raise PublicKnowledgeError("no_results", "No encontré una explicación en Wikipedia en español para ese tema.")
    result = data.get("query")
    pages = result.get("pages") if type(result) is dict else None
    if type(pages) is not list or len(pages) > _MAX_HITS:
        raise PublicKnowledgeError("invalid_response", "La fuente devolvió una respuesta no válida.")
    candidates, page_ids, indexes = [], set(), set()
    for page in pages:
        if type(page) is not dict:
            raise PublicKnowledgeError("invalid_response", "La fuente devolvió un artículo no válido.")
        page_id, rank = page.get("pageid"), page.get("index")
        if (type(page_id) is not int or page_id <= 0 or page_id in page_ids
                or type(rank) is not int or not 1 <= rank <= _MAX_HITS or rank in indexes
                or type(page.get("ns")) is not int or page["ns"] != 0
                or "missing" in page or "invalid" in page):
            raise PublicKnowledgeError("invalid_response", "La fuente devolvió un artículo no válido.")
        page_ids.add(page_id)
        indexes.add(rank)
        title = _safe_text(page.get("title"), 200)
        url = _source_url(page.get("fullurl"), title)
        extract = page.get("extract", "")
        if extract == "":
            continue
        extract = _safe_text(extract, 2400, paragraphs=True)
        if extract:
            candidates.append((rank, title, url, extract))
    if not candidates:
        raise PublicKnowledgeError("no_results", "No encontré una explicación en Wikipedia en español para ese tema.")
    _, title, url, extract = min(candidates)
    answer = f"Wikipedia — {title}: {extract}"
    if len(answer) > _MAX_ANSWER:
        answer = answer[:_MAX_ANSWER - 1].rstrip() + "…"
    return {"answer": answer, "sources": [{"title": title, "url": url}], "provider": _PROVIDER, "query": query}


def lookup_public_knowledge(query: str) -> dict:
    """Return one attributed extract, or a stable error, in at most eight seconds.

    No retries, credentials, paid services, HTTP redirects, URL fetching, persistent
    writes, LLM inference or unbounded threads. The one request discloses the public
    topic and the server IP to Wikimedia. Callers must not pass private text here.
    """
    query = _normalize_query(query)
    if not _WORKER_SLOTS.acquire(blocking=False):
        raise PublicKnowledgeError("busy", "Hay consultas en curso. Inténtalo en unos segundos.")
    deadline = time.monotonic() + _TOTAL_TIMEOUT
    results = queue.Queue(maxsize=1)

    def run():
        try:
            results.put((True, _decode(_fetch(_request_url(query), deadline), query)))
        except PublicKnowledgeError as exc:
            results.put((False, exc))
        except HTTPError as exc:
            code = "rate_limited" if exc.code == 429 else "unavailable"
            exc.close()
            results.put((False, PublicKnowledgeError(code, "La fuente no está disponible en este momento.")))
        except (TimeoutError, socket.timeout):
            results.put((False, PublicKnowledgeError("timeout", "La consulta tardó demasiado. Puedes intentarlo más adelante.")))
        except (URLError, OSError, ValueError, RecursionError):
            results.put((False, PublicKnowledgeError("unavailable", "No pude conectar con la fuente en este momento.")))
        finally:
            _WORKER_SLOTS.release()

    try:
        threading.Thread(target=run, name="gica-wikipedia", daemon=True).start()
    except RuntimeError:
        _WORKER_SLOTS.release()
        raise PublicKnowledgeError("unavailable", "No pude iniciar la consulta en este momento.") from None
    try:
        ok, result = results.get(timeout=max(0.0, deadline - time.monotonic()))
    except queue.Empty:
        raise PublicKnowledgeError("timeout", "La consulta tardó demasiado. Puedes intentarlo más adelante.") from None
    if not ok:
        raise result
    return result
