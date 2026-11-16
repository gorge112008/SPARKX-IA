"""Environment settings. SQLite supports single-process local development only."""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY is required outside development")
    SECRET_KEY = "development-only-do-not-deploy-sparkx-local"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",") if h.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "apps.events", "apps.planning", "apps.assistant", "apps.jobs",
    "apps.ai_management",
    "apps.project_checklist",
    "apps.accounts",
    "apps.directory",
    "apps.registration",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.PortalAccessMiddleware",
    "config.middleware.PrivateResponsesMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "config.context_processors.project_tools",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    db = urlparse(database_url)
    if db.scheme not in ("postgres", "postgresql"):
        raise RuntimeError("DATABASE_URL must use PostgreSQL")
    query = parse_qs(db.query, keep_blank_values=True)
    if set(query) - {"sslmode"} or any(len(v) != 1 for v in query.values()):
        raise RuntimeError("DATABASE_URL contains unsupported query options")
    database_options = {"connect_timeout": 5}
    if "sslmode" in query:
        sslmode = query["sslmode"][0]
        if sslmode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise RuntimeError("DATABASE_URL contains an invalid sslmode")
        database_options["sslmode"] = sslmode
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(db.path.lstrip("/")), "USER": unquote(db.username or ""),
        "PASSWORD": unquote(db.password or ""), "HOST": db.hostname or "localhost",
        "PORT": db.port or 5432, "CONN_MAX_AGE": 0, "OPTIONS": database_options,
    }}
else:
    if not DEBUG and os.environ.get("SPARKX_ALLOW_SQLITE", "0") != "1":
        raise RuntimeError("Production requires DATABASE_URL (PostgreSQL)")
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "var" / "db.sqlite3",
        "OPTIONS": {"timeout": 15},
    }}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 16}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "var" / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailOrUsernameBackend",
    # Keep get_user() compatibility for existing sessions. The first backend
    # raises PermissionDenied on failed/ambiguous authentication, preventing fallback.
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_MAX_ATTEMPTS = 5
LOGIN_IP_MAX_ATTEMPTS = 50
LOGIN_WINDOW_SECONDS = 300
LOGIN_REDIRECT_URL = "events:index"
LOGOUT_REDIRECT_URL = "login"
# The temporary personal checklist has been retired from the product.
SPARKX_CHECKLIST_ENABLED = False
SPARKX_CHECKLIST_OWNER_USERNAME = os.environ.get("SPARKX_CHECKLIST_OWNER_USERNAME", "adminjorge")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
if os.environ.get("DJANGO_TRUST_PROXY", "0") == "1":
    # Enable only behind a proxy that strips incoming X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536
FILE_UPLOAD_MAX_MEMORY_SIZE = 65536
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OLLAMA_ENABLED = os.environ.get("OLLAMA_ENABLED", "0") == "1"
AI_MAX_OUTPUT_TOKENS = int(os.environ.get("AI_MAX_OUTPUT_TOKENS", "2500"))
AI_DAILY_JOB_LIMIT = int(os.environ.get("AI_DAILY_JOB_LIMIT", "20"))
AI_MAX_PENDING_PER_EVENT = int(os.environ.get("AI_MAX_PENDING_PER_EVENT", "3"))
AI_HTTP_TIMEOUT_SECONDS = 45
JOB_LEASE_SECONDS = 120
FREE_DEMO_ENABLED = DEBUG and os.environ.get("SPARKX_FREE_DEMO_ENABLED", "1") == "1"
JOB_MAX_ATTEMPTS = 2
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
