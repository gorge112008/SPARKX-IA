"""Read-only verification of the explicitly allowed free OpenCode models.

Importing this module does not make requests.  Verification fetches only the
public model catalogue; it neither reads credentials nor invokes inference.
The provider's privacy declaration is a documented claim, not an independent
audit or a guarantee that its terms will remain unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from types import MappingProxyType
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


CATALOG_URL = "https://opencode.ai/inference/openai/v1/models"
INFERENCE_BASE_URL = "https://opencode.ai/inference/openai/v1"
POLICY_URL = "https://opencode.ai/docs/console/models/"
PRIVACY_POLICY_URL = "https://opencode.ai/legal/privacy-policy"
MAX_CATALOG_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_MODEL = "glm-5.3-flash-free"
POLICY_REVIEWED_ON = "2026-11-15"

_DECLARATION_NOTE = (
    " Esta es una declaración del proveedor; no constituye una auditoría "
    "independiente. Aunque se ejecute en tu equipo, el contexto se envía a un "
    "proveedor remoto. No envíes secretos ni datos personales o confidenciales."
)
_TEMPORARY_QUOTA_NOTE = (
    "Gratuito por tiempo limitado. La documentación revisada no publica una "
    "cuota fija de solicitudes o tokens por minuto ni garantiza disponibilidad."
)


def _model_policy(name, *, privacy, training_use, retention_note,
                  synthetic_only=False, requires_policy_consent=False,
                  quota_note=_TEMPORARY_QUOTA_NOTE,
                  hosting_note="OpenCode declara alojamiento en Estados Unidos y la Unión Europea; no verificado de forma independiente.",
                  availability_note="La oferta es temporal y puede dejar de estar disponible."):
    return MappingProxyType({
        "name": name,
        "privacy": privacy + _DECLARATION_NOTE,
        "synthetic_only": synthetic_only,
        "requires_policy_consent": requires_policy_consent,
        "training_use": training_use,
        "retention_note": retention_note,
        "quota_note": quota_note,
        "hosting_note": hosting_note,
        "availability_note": availability_note,
        "policy_url": POLICY_URL,
        "policy_reviewed_on": POLICY_REVIEWED_ON,
    })


# A deliberately curated catalogue, not dynamic discovery. The ten additional
# candidates require explicit per-task acknowledgement and synthetic demo data.
# They must never inherit the original candidates' zero-retention declaration.
MODEL_POLICIES = MappingProxyType({
    "glm-5.3-flash-free": _model_policy(
        "GLM-5.3-Flash Free",
        privacy="OpenCode declara que el proveedor de GLM-5.3-Flash Free no conserva estos datos ni los utiliza para entrenar modelos.",
        training_use="not_used_declared",
        retention_note="Según OpenCode, el proveedor no conserva estos datos.",
    ),
    "deepseek-v4.1-flash-free": _model_policy(
        "DeepSeek V4.1 Flash Free",
        privacy="OpenCode declara que el proveedor de DeepSeek V4.1 Flash Free no conserva estos datos ni los utiliza para entrenar modelos.",
        training_use="not_used_declared",
        retention_note="Según OpenCode, el proveedor no conserva estos datos.",
    ),
    "minimax-m3.1-flash-free": _model_policy(
        "MiniMax M3.1 Flash Free",
        privacy="OpenCode declara que el proveedor de MiniMax M3.1 Flash Free no conserva estos datos ni los utiliza para entrenar modelos.",
        training_use="not_used_declared",
        retention_note="Según OpenCode, el proveedor no conserva estos datos.",
    ),
    "longcat-2.5-free": _model_policy(
        "LongCat 2.5 Free",
        privacy="OpenCode declara que el proveedor de LongCat 2.5 Free no conserva estos datos ni los utiliza para entrenar modelos. Se aloja en China.",
        training_use="not_used_declared",
        retention_note="Según OpenCode, el proveedor no conserva estos datos.",
        synthetic_only=True,
        requires_policy_consent=True,
        quota_note=(
            "OpenCode publica un límite de 100 solicitudes al día. Este catálogo "
            "no aplica ni mide la cuota del proveedor; las solicitudes auxiliares "
            "también podrían contar. La oferta es temporal."
        ),
        hosting_note="Se aloja en China según OpenCode; debes aceptar esta condición expresamente.",
    ),
    "beam-free": _model_policy(
        "Beam Free",
        privacy="OpenCode declara que los datos de Beam Free no se usan para entrenar modelos y se conservan durante 30 días por seguridad.",
        training_use="not_used_declared",
        retention_note="Según OpenCode, los datos se conservan 30 días por seguridad; no se eliminan de inmediato.",
        synthetic_only=True,
        requires_policy_consent=True,
        availability_note="El proveedor excluye algunos países y regiones; consulta la política enlazada antes de usarlo.",
    ),
    "mimo-v2.6-flash-free": _model_policy(
        "MiMo-V2.6-Flash Free",
        privacy="OpenCode indica que los datos recopilados por MiMo-V2.6-Flash Free podrían utilizarse para mejorar el modelo.",
        training_use="model_improvement_possible",
        retention_note="La política revisada no indica cuánto tiempo se conservan los datos ni garantiza que no se guarden para este modelo.",
        synthetic_only=True,
        requires_policy_consent=True,
    ),
    "nemotron-3.5-lightning-free": _model_policy(
        "Nemotron 3.5 Lightning Free",
        privacy=(
            "Solo para pruebas de NVIDIA: el uso se registra por seguridad y para "
            "mejorar sus productos y servicios. No se deben enviar datos personales "
            "ni confidenciales."
        ),
        training_use="security_and_product_improvement_logging",
        retention_note="La política revisada no indica un plazo fijo de conservación ni garantiza que no se guarden datos de estas pruebas.",
        synthetic_only=True,
        requires_policy_consent=True,
        availability_note="Se aplican las condiciones de prueba de la API de NVIDIA; no se garantiza un servicio para producción.",
    ),
    "big-pickle": _model_policy(
        "Big Pickle",
        privacy="OpenCode indica que los datos de Big Pickle podrían utilizarse para mejorar el modelo; no publica un plazo fijo de conservación para esta oferta.",
        training_use="model_improvement_possible",
        retention_note="La política revisada no publica un plazo fijo de conservación ni garantiza que no se guarden estos datos.",
        synthetic_only=True,
        requires_policy_consent=True,
    ),
    "iceman-free": _model_policy(
        "Iceman Free",
        privacy="OpenCode declara que el proveedor de Iceman Free conserva datos y los utiliza para mejorar el modelo; no publica un plazo fijo de conservación.",
        training_use="model_improvement_declared",
        retention_note="Se conservan datos para mejorar el modelo según OpenCode; la política revisada no publica un plazo fijo de conservación.",
        synthetic_only=True,
        requires_policy_consent=True,
    ),
    "inkling-2-small-free": _model_policy(
        "Inkling 2 Small Free",
        privacy="OpenCode indica que el proveedor de Inkling 2 Small Free conserva datos y podría utilizarlos para entrenamiento y monitorización. Hay restricciones de acceso por región.",
        training_use="training_and_monitoring_possible",
        retention_note="La política revisada indica conservación y posible entrenamiento o monitorización; no publica un plazo fijo de conservación.",
        synthetic_only=True,
        requires_policy_consent=True,
        availability_note="El proveedor excluye algunos países y regiones; consulta las condiciones enlazadas antes de usarlo.",
    ),
    "flint-40b-free": _model_policy(
        "Flint 40B Free",
        privacy="OpenCode indica que el proveedor de Flint 40B Free conserva los datos durante 30 días y podría utilizarlos para mejorar el modelo.",
        training_use="model_improvement_possible",
        retention_note="Según OpenCode, los datos se conservan 30 días; no se eliminan de inmediato.",
        synthetic_only=True,
        requires_policy_consent=True,
    ),
    "nemotron-3-ultra-free": _model_policy(
        "Nemotron 3 Ultra Free",
        privacy=(
            "Solo para pruebas de NVIDIA: el uso se registra por seguridad y para "
            "mejorar sus productos y servicios. No se deben enviar datos personales "
            "ni confidenciales."
        ),
        training_use="security_and_product_improvement_logging",
        retention_note="La política revisada no indica un plazo fijo de conservación ni garantiza que no se guarden datos de estas pruebas.",
        synthetic_only=True,
        requires_policy_consent=True,
        availability_note="Se aplican las condiciones de prueba de la API de NVIDIA; no se garantiza un servicio para producción.",
    ),
    "nemotron-3.5-super-vl-free": _model_policy(
        "Nemotron 3.5 Super VL Free",
        privacy=(
            "Solo para pruebas de NVIDIA: el uso se registra por seguridad y para "
            "mejorar sus productos y servicios. No se deben enviar datos personales "
            "ni confidenciales."
        ),
        training_use="security_and_product_improvement_logging",
        retention_note="La política revisada no indica un plazo fijo de conservación ni garantiza que no se guarden datos de estas pruebas.",
        synthetic_only=True,
        requires_policy_consent=True,
        availability_note="Se aplican las condiciones de prueba de la API de NVIDIA; no se garantiza un servicio para producción.",
    ),
})
ALLOWED_MODELS = MappingProxyType({
    model_id: policy["name"] for model_id, policy in MODEL_POLICIES.items()
})


class CatalogVerificationError(RuntimeError):
    """The catalogue could not establish that the chosen model is free."""


def policy_fingerprint(model_id):
    """Version the full locally reviewed policy and exact model identifier.

    This digest is a consent binding, not consent itself or a remote privacy
    audit. Any reviewed field change, including the review date, changes it.
    """
    if type(model_id) is not str or model_id not in MODEL_POLICIES:
        raise CatalogVerificationError("El modelo no está en la lista gratuita permitida.")
    canonical = json.dumps({"id": model_id, "policy": dict(MODEL_POLICIES[model_id])},
                           ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Non-finite JSON number")


def _zero_price(value) -> bool:
    # Checking exact types excludes bool (a subclass of int). Exact zero also
    # rejects negative, infinite and NaN prices without coercing strings.
    return type(value) in (int, float) and value == 0


def _verify_cost_tree(value):
    """Reject nonzero or unknown scalar price components, including new ones."""
    if isinstance(value, dict):
        for child in value.values():
            _verify_cost_tree(child)
    elif not _zero_price(value):
        raise CatalogVerificationError(
            "El catálogo contiene un precio no gratuito o no verificable."
        )


def _verify_api_tree(value):
    if not isinstance(value, dict):
        raise CatalogVerificationError("Los metadatos de conexión no son válidos.")
    for key, child in value.items():
        if key == "base_url" and child != INFERENCE_BASE_URL:
            raise CatalogVerificationError("El catálogo indica otro destino de conexión.")
        if isinstance(child, dict):
            _verify_api_tree(child)
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    _verify_api_tree(item)


def _positive_limit(value) -> bool:
    return type(value) is int and value > 0


def verify_free_model(model_id=DEFAULT_MODEL, *, synthetic_demo=False,
                      accept_model_policy=False, opener=None):
    """Fetch and validate current prices for one explicitly allowed model.

    ``opener`` is an optional test seam: a callable accepting a ``Request`` and
    ``timeout=15`` and returning a context-managed binary HTTP response. It must
    enforce the same no-redirect rule. Production uses its own no-redirect
    opener, with the fixed HTTPS URL and no authorization headers.

    Raises ``CatalogVerificationError`` for unavailable, malformed, ambiguous
    or nonzero prices. There is no fallback, retry, authentication or inference.
    Cache writes may be absent (unsupported); all present price components must
    be numeric zero. The returned cache-write value is then ``None``, not zero.
    Models marked ``synthetic_only`` require both ``synthetic_demo=True`` and
    ``accept_model_policy=True``. These are exact booleans, not truthy strings;
    callers must obtain explicit acknowledgement for the selected model/task.
    """
    if type(model_id) is not str or model_id not in ALLOWED_MODELS:
        raise CatalogVerificationError("El modelo no está en la lista gratuita permitida.")
    if type(synthetic_demo) is not bool or type(accept_model_policy) is not bool:
        raise CatalogVerificationError("La confirmación de uso y privacidad debe ser explícita.")
    policy = MODEL_POLICIES[model_id]
    if policy["synthetic_only"] and synthetic_demo is not True:
        raise CatalogVerificationError("Este modelo solo admite tareas de demostración con datos sintéticos.")
    if policy["requires_policy_consent"] and accept_model_policy is not True:
        raise CatalogVerificationError("Debes aceptar expresamente las condiciones del modelo seleccionado.")

    request = Request(
        CATALOG_URL,
        headers={
            "User-Agent": "Mozilla/5.0 ArquiGica-Free-Catalog/1.0",
            "Accept": "application/json",
        },
        method="GET",
    )
    open_request = opener or build_opener(_NoRedirect()).open
    try:
        with open_request(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            get_url = getattr(response, "geturl", None)
            if callable(get_url) and get_url() != CATALOG_URL:
                raise CatalogVerificationError("No se permiten redirecciones del catálogo.")
            status = getattr(response, "status", 200)
            if status != 200:
                raise CatalogVerificationError("El catálogo no respondió correctamente.")
            raw = response.read(MAX_CATALOG_BYTES + 1)
        if not isinstance(raw, bytes) or len(raw) > MAX_CATALOG_BYTES:
            raise CatalogVerificationError("El catálogo supera el tamaño permitido.")
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except CatalogVerificationError:
        raise
    except (HTTPError, URLError, OSError, ValueError, TypeError, RecursionError):
        # Do not include response bodies, headers or transport details in errors.
        raise CatalogVerificationError(
            "No se pudo comprobar el catálogo gratuito; la ejecución se detiene."
        ) from None

    if not isinstance(document, dict) or not isinstance(document.get("data"), list):
        raise CatalogVerificationError("El formato del catálogo no es válido.")
    entries = document["data"]
    if any(not isinstance(entry, dict) for entry in entries):
        raise CatalogVerificationError("El formato de los modelos no es válido.")
    matches = [entry for entry in entries if entry.get("id") == model_id]
    if len(matches) != 1:
        raise CatalogVerificationError("El modelo gratuito no está disponible de forma inequívoca.")
    model = matches[0]
    if "type" in model and model["type"] != "chat":
        raise CatalogVerificationError("El modelo no ofrece el tipo de conversación permitido.")
    if "status" in model and model["status"] not in ("active", "available", "preview"):
        raise CatalogVerificationError("El modelo gratuito ya no está disponible.")

    try:
        cost = model["cost"]
        if not isinstance(cost, dict):
            raise TypeError
        text = cost["text"]
        input_cost = text["input"]
        output_cost = text["output"]
        cache = input_cost["cache"]
        prices = {
            "input": input_cost["price"],
            "output": output_cost["price"],
            "cache_read": cache["read"],
            "cache_write": cache.get("write"),
        }
        required_prices = (prices["input"], prices["output"], prices["cache_read"])
        if not all(_zero_price(price) for price in required_prices):
            raise CatalogVerificationError("No se han verificado todos los precios gratuitos.")
        _verify_cost_tree(cost)
        if "api" in model:
            _verify_api_tree(model["api"])
        limits = model["limit"]
        context_limit, output_limit = limits["context"], limits["output"]
        if not _positive_limit(context_limit) or not _positive_limit(output_limit):
            raise CatalogVerificationError("Los límites del modelo no son válidos.")
    except CatalogVerificationError:
        raise
    except (KeyError, TypeError, AttributeError, RecursionError):
        raise CatalogVerificationError("Faltan precios o límites verificables en el catálogo.") from None

    return {
        "id": model_id,
        "context_limit": context_limit,
        "output_limit": output_limit,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "source": CATALOG_URL,
        "prices": prices,
        "policy_source": POLICY_URL,
        "privacy_policy_source": PRIVACY_POLICY_URL,
        "privacy": policy["privacy"],
        "synthetic_only": policy["synthetic_only"],
        "requires_policy_consent": policy["requires_policy_consent"],
        "quota_note": policy["quota_note"],
        "policy_url": policy["policy_url"],
        "model_policy": dict(policy),
        "policy_fingerprint": policy_fingerprint(model_id),
    }
