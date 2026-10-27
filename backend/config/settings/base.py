from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# .env lives at the repository root (shared with docker compose)
ENV_FILE = BASE_DIR.parent / ".env"
if ENV_FILE.exists():
    environ.Env.read_env(str(ENV_FILE))

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")  # noqa: S105
DEBUG = False
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "auditlog",
    "apps.core",
    "apps.users",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://onea:onea@localhost:5432/onea"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL: str = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

CORS_ALLOWED_ORIGINS: list[str] = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"]
)

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.core.handlers.api_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.users.authentication.SessionAuthentication401"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ONEA Audit API",
    "DESCRIPTION": "Plateforme de digitalisation de l'audit interne ONEA",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

# --- Templates: project-level templates (email/*) ---
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]

# --- Celery (namespace CELERY; broker/backend are set from REDIS_URL above) ---
CELERY_TIMEZONE = "Africa/Ouagadougou"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {
    "heartbeat": {
        "task": "core.tasks.heartbeat",
        "schedule": crontab(hour=6, minute=0),
    },
}

# --- Email: EMAIL_URL = smtp://mailpit:1025 in compose, smtp://localhost:1025 on host ---
_email = env.email_url("EMAIL_URL", default="smtp://mailpit:1025")
EMAIL_BACKEND = _email["EMAIL_BACKEND"]
EMAIL_HOST = _email.get("EMAIL_HOST", "")
EMAIL_PORT = _email.get("EMAIL_PORT", 25)
EMAIL_HOST_USER = _email.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = _email.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _email.get("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = "audit-interne@onea.bf"

# --- Keycloak / OIDC bearer authentication (Task 5) ---
OIDC_OP_BASE_URL: str = env("OIDC_OP_BASE_URL", default="http://localhost:8080/realms/onea").rstrip(
    "/"
)
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{OIDC_OP_BASE_URL}/protocol/openid-connect/auth"
OIDC_OP_TOKEN_ENDPOINT = f"{OIDC_OP_BASE_URL}/protocol/openid-connect/token"
OIDC_OP_USER_ENDPOINT = f"{OIDC_OP_BASE_URL}/protocol/openid-connect/userinfo"
OIDC_OP_JWKS_ENDPOINT = f"{OIDC_OP_BASE_URL}/protocol/openid-connect/certs"
OIDC_RP_CLIENT_ID: str = env("OIDC_RP_CLIENT_ID", default="onea-backend")
OIDC_RP_CLIENT_SECRET: str = env("OIDC_RP_CLIENT_SECRET", default="")  # required in prod
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
OIDC_VERIFY_SSL: bool = env.bool("OIDC_VERIFY_SSL", default=True)
OIDC_TIMEOUT = 5  # seconds; Keycloak calls must never hang a request worker
AUTHENTICATION_BACKENDS = [
    "apps.users.oidc.OneaOIDCBackend",
    "django.contrib.auth.backends.ModelBackend",
]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.OIDCBearerAuthentication",
        "apps.users.authentication.SessionAuthentication401",
    ],
}
