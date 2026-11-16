"""Reviewed model presets. Prices are USD per million tokens, not an invoice.

Free tier availability belongs to the provider account, never to a model name.
Only administrators choose a preset; secrets and endpoints are not user input.
"""
from datetime import date
from decimal import Decimal
from tools.opencode.catalog import MODEL_POLICIES, policy_fingerprint

VERIFIED_ON = date(2026, 11, 9)


def _opencode_demo(name, model):
    policy = MODEL_POLICIES[model]
    return {
        "name": "Demostración gratuita · " + name, "provider": "opencode", "model": model,
        "mode": "free", "input_rate": "0", "cached_rate": "0", "output_rate": "0",
        "verified_on": date(2026, 11, 15),
        "source_url": "https://opencode.ai/docs/console/models/",
        "setup_url": "https://opencode.ai/docs/console/models/", "key_setting": "FREE_DEMO_ENABLED",
        "description": "Puente local instalado, proveedor remoto temporal. Solo eventos ficticios; hasta 2048 tokens de salida. Verifica precio cero antes de cada llamada; sin alternativa de pago ni reintentos automáticos.",
        "privacy": policy["privacy"] + " Solo eventos ficticios; el marcado no detecta datos personales.",
        "privacy_url": "https://opencode.ai/docs/console/models/",
        "requires_policy_consent": policy["requires_policy_consent"],
        "model_policy_version": policy_fingerprint(model),
    }


CATALOG = {
    "opencode_demo": _opencode_demo("GLM Flash", "glm-5.3-flash-free"),
    "opencode_deepseek": _opencode_demo("DeepSeek Flash", "deepseek-v4.1-flash-free"),
    "opencode_minimax": _opencode_demo("MiniMax Flash", "minimax-m3.1-flash-free"),
    **{preset: _opencode_demo(MODEL_POLICIES[model]["name"], model) for preset, model in {
        "opencode_longcat": "longcat-2.5-free", "opencode_beam": "beam-free",
        "opencode_mimo": "mimo-v2.6-flash-free", "opencode_nemotron": "nemotron-3.5-lightning-free",
        "opencode_pickle": "big-pickle", "opencode_iceman": "iceman-free",
        "opencode_inkling": "inkling-2-small-free", "opencode_flint": "flint-40b-free",
        "opencode_nemotron_vl": "nemotron-3.5-super-vl-free",
    }.items()},
    "groq_free": {
        "name": "Groq · cupo gratuito", "provider": "groq", "model": "openai/gpt-oss-20b",
        "mode": "free", "input_rate": "0", "cached_rate": "0", "output_rate": "0",
        "source_url": "https://console.groq.com/docs/rate-limits",
        "setup_url": "https://console.groq.com/keys", "key_setting": "GROQ_API_KEY",
        "description": "Requiere cuenta Free y cupo disponible; no cambia automáticamente a pago.",
        "privacy": "Revisa la política de tu cuenta antes de enviar información del evento.",
        "privacy_url": "https://console.groq.com/docs/your-data",
    },
    "gemini_free": {
        "name": "Gemini · cupo gratuito", "provider": "gemini", "model": "gemini-3.5-flash-lite",
        "mode": "free", "input_rate": "0", "cached_rate": "0", "output_rate": "0",
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
        "setup_url": "https://aistudio.google.com/api-keys", "key_setting": "GEMINI_API_KEY",
        "description": "Cuota y elegibilidad por proyecto. Comprueba que la cuenta usa el nivel gratuito.",
        "privacy": "En el nivel gratuito, Google puede usar contenido para mejorar sus servicios. Evita datos confidenciales o personales.",
        "privacy_url": "https://ai.google.dev/gemini-api/terms",
    },
    "openai_luna": {
        "name": "OpenAI · GPT-6 Luna", "provider": "openai", "model": "gpt-6-luna",
        "mode": "paid", "input_rate": "0.10", "cached_rate": "0.01", "output_rate": "0.50",
        "source_url": "https://developers.openai.com/api/docs/pricing",
        "setup_url": "https://platform.openai.com/api-keys", "key_setting": "OPENAI_API_KEY",
        "description": "Tarifa Standard, con caché desactivada en esta integración. Los créditos se comprueban en la organización API.",
        "privacy": "La suscripción y los créditos no se leen desde ArquiGica; los límites del proveedor siguen siendo necesarios.",
        "privacy_url": "https://developers.openai.com/api/docs/guides/your-data",
    },
    "openai_54_mini": {
        "name": "OpenAI · GPT-5.4 mini", "provider": "openai", "model": "gpt-5.4-mini",
        "mode": "paid", "input_rate": "0.75", "cached_rate": "0.075", "output_rate": "4.50",
        "verified_on": date(2026, 11, 12),
        "source_url": "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
        "setup_url": "https://platform.openai.com/api-keys", "key_setting": "OPENAI_API_KEY",
        "description": "Tarifa Standard con caché automática. La oferta por compartir datos requiere elegibilidad y activación del proyecto en OpenAI; ArquiGica no las verifica y el exceso puede consumir saldo.",
        "privacy": "Si activas compartir entradas y respuestas, OpenAI puede usarlas para mejorar modelos. Usa datos ficticios en el proyecto de pruebas y comprueba sus controles de datos.",
        "privacy_url": "https://developers.openai.com/api/docs/guides/your-data",
    },
    "groq_paid": {
        "name": "Groq · de pago", "provider": "groq", "model": "openai/gpt-oss-20b",
        "mode": "paid", "input_rate": "0.075", "cached_rate": "0.0375", "output_rate": "0.30",
        "source_url": "https://console.groq.com/docs/models",
        "setup_url": "https://console.groq.com/keys", "key_setting": "GROQ_API_KEY",
        "description": "Mismo contrato de respuesta estructurada, con tarifa y presupuesto explícitos.",
        "privacy": "Revisa las condiciones y límites de gasto de la organización.",
        "privacy_url": "https://console.groq.com/docs/your-data",
    },
    "gemini_paid": {
        "name": "Gemini · de pago", "provider": "gemini", "model": "gemini-3.5-flash-lite",
        "mode": "paid", "input_rate": "0.30", "cached_rate": "0.03", "output_rate": "2.50",
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
        "setup_url": "https://aistudio.google.com/api-keys", "key_setting": "GEMINI_API_KEY",
        "description": "Salida incluye tokens de razonamiento. No se usa caché explícita con almacenamiento.",
        "privacy": "Consulta las condiciones del servicio pagado y la configuración de tu proyecto.",
        "privacy_url": "https://ai.google.dev/gemini-api/terms",
    },
    "ollama_local": {
        "name": "Ollama · ejecución local", "provider": "ollama", "model": "qwen3:4b-instruct-2507-q4_K_M",
        "mode": "local", "input_rate": "0", "cached_rate": "0", "output_rate": "0",
        "source_url": "https://docs.ollama.com/capabilities/structured-outputs",
        "setup_url": "https://docs.ollama.com/quickstart", "key_setting": "OLLAMA_ENABLED",
        "description": "Sin tarifa API local; necesita servicio y modelo instalados por separado. Hardware y energía no están incluidos.",
        "privacy": "Sólo loopback 127.0.0.1:11434 y modelo local; no se permiten direcciones arbitrarias ni modelos cloud.",
        "privacy_url": "https://docs.ollama.com/faq",
    },
}

OPENCODE_DEMO_MODELS = frozenset(item["model"] for item in CATALOG.values()
                                if item["provider"] == "opencode" and item["mode"] == "free")


def catalog_choices():
    return [(key, value["name"]) for key, value in CATALOG.items()]


def catalog_entry(key):
    item = dict(CATALOG[key])
    item["code"] = key
    item["verified_on"] = item.get("verified_on", VERIFIED_ON)
    item["cache_policy"] = cache_policy_for(item["provider"], item["model"])
    for name in ("input_rate", "cached_rate", "output_rate"):
        item[name] = Decimal(item[name])
    return item


def cache_policy_for(provider, model):
    """Only the reviewed Mini path uses OpenAI's automatic prompt caching.

    Luna keeps its existing explicit/no-breakpoints contract. Unknown OpenAI
    models retain that conservative policy until their integration is reviewed.
    """
    return "disabled" if provider == "openai" and model != "gpt-5.4-mini" else "provider"


def preset_for(profile):
    for key, item in CATALOG.items():
        if (item["provider"], item["model"], item["mode"]) == (profile.provider, profile.model, profile.mode):
            return key
    return ""
