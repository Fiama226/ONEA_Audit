"""Production settings.

Everything security- or deployment-relevant is REQUIRED from the environment: there are
no localhost/mailpit fallbacks. A missing variable raises ImproperlyConfigured at startup.
"""

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from config.documents_settings import S3_VARIABLES, configuration_stockage, valider_documents_root

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, base_de_donnees, env, env_secret

DEBUG = False
SECRET_KEY = env_secret("SECRET_KEY")  # required in production, no default (SECRET_KEY_FILE first)
DATABASES = {"default": base_de_donnees("DATABASE_URL")}  # required (DATABASE_PASSWORD_FILE first)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # required
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")  # required

_email = env.email_url("EMAIL_URL")  # required (no mailpit default)
EMAIL_BACKEND = _email["EMAIL_BACKEND"]
EMAIL_HOST = _email.get("EMAIL_HOST", "")
EMAIL_PORT = _email.get("EMAIL_PORT", 25)
EMAIL_HOST_USER = _email.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_secret("EMAIL_PASSWORD", default="") or _email.get(
    "EMAIL_HOST_PASSWORD", ""
)
# django-environ maps smtps:// to STARTTLS; on a smtps:// URL (implicit TLS, usually port
# 465) Django needs EMAIL_USE_SSL instead. The two are mutually exclusive.
EMAIL_USE_SSL = _email.get("EMAIL_USE_SSL", False) or env("EMAIL_URL").startswith("smtps://")
EMAIL_USE_TLS = _email.get("EMAIL_USE_TLS", False) and not EMAIL_USE_SSL
EMAIL_TIMEOUT = 10  # seconds; a dead relay must not hang a worker

_plateforme = urlsplit(PLATEFORME_URL)  # noqa: F405
if _plateforme.scheme != "https" or not _plateforme.hostname or _plateforme.username:
    raise ImproperlyConfigured("PLATEFORME_URL must be an https:// URL in production")

# --- Documents storage: explicit, absolute, outside the code (D2). ---
if DOCUMENTS_STORAGE == "filesystem":  # noqa: F405
    _root = env("DOCUMENTS_ROOT")  # required in production, no dev default
    valider_documents_root(_root, repo_root=str(BASE_DIR.parent), code_dir=str(BASE_DIR))  # noqa: F405
    DOCUMENTS_ROOT = _root
else:
    for _name in S3_VARIABLES:
        env(_name)  # each one required for s3
STORAGES = {
    **STORAGES,  # noqa: F405
    "documents": configuration_stockage({**os.environ, "DOCUMENTS_ROOT": DOCUMENTS_ROOT}),  # noqa: F405
}

# --- SEC-04 : analyse antivirus ClamAV obligatoire (échec fermé par défaut). ---
ANTIVIRUS_MOTEUR = env("ANTIVIRUS_MOTEUR", default="clamav")
if ANTIVIRUS_MOTEUR == "aucun" and not env.bool("ANTIVIRUS_AUTORISER_AUCUN", default=False):
    raise ImproperlyConfigured(
        "ANTIVIRUS_MOTEUR=aucun is refused in production (set ANTIVIRUS_AUTORISER_AUCUN=true "
        "to accept the absence of malware scanning explicitly)"
    )

if not RECHERCHE["CLE"]:  # noqa: F405
    raise ImproperlyConfigured("MEILI_MASTER_KEY must be set in production")

# --- Bloc T17 : aucun secret de modèle (CHANGE_ME*) ni valeur de développement en production. ---
_SECRETS_A_CONTROLER = {
    "SECRET_KEY": SECRET_KEY,
    "mot de passe de la base (DATABASE_URL / DATABASE_PASSWORD_FILE)": DATABASES["default"].get(
        "PASSWORD", ""
    ),
    "mot de passe Redis (REDIS_URL / REDIS_PASSWORD_FILE)": urlsplit(REDIS_URL).password or "",  # noqa: F405
    "mot de passe SMTP (EMAIL_URL / EMAIL_PASSWORD_FILE)": EMAIL_HOST_PASSWORD or "",
    "MEILI_MASTER_KEY": RECHERCHE["CLE"],  # noqa: F405
    "METRICS_TOKEN": METRICS_TOKEN,  # noqa: F405
    **{f"SECRET_KEY_FALLBACKS[{i}]": v for i, v in enumerate(SECRET_KEY_FALLBACKS)},  # noqa: F405
}
for _nom, _valeur in _SECRETS_A_CONTROLER.items():
    if _valeur.upper().startswith("CHANGE_ME") or _valeur == "insecure-dev-key-change-me":
        raise ImproperlyConfigured(f"{_nom} est encore une valeur de modèle ou de développement")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must not be empty in production")
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# /admin/ is off unless DJANGO_ADMIN_ENABLED=true.
DJANGO_ADMIN_ENABLED = env.bool("DJANGO_ADMIN_ENABLED", default=False)

# Security headers (CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy, HSTS at the
# edge) are owned by nginx (docker/nginx/prod.conf). Django keeps only the SECURE_* settings
# that are needed for correctness (redirect, proxy header, cookies, HSTS for direct access).
# TLS terminates at nginx. SECURE_PROXY_SSL_HEADER trusts X-Forwarded-Proto, which is only
# safe because docker/nginx/prod.conf OVERWRITES that header on every proxied request and
# the web container publishes no host port. Never expose gunicorn directly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Same origin behind nginx: the session cookie MUST be Secure. The variable is required and
# cannot be turned off (a misconfigured deployment fails at start-up instead of leaking cookies).
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE")  # required
if not SESSION_COOKIE_SECURE:
    raise ImproperlyConfigured("SESSION_COOKIE_SECURE must be true in production")
CSRF_COOKIE_SECURE = True
# `__Host-` prefix: Secure, Path=/, no Domain; only valid over HTTPS, hence production only.
SESSION_COOKIE_NAME = "__Host-onea-session"
CSRF_COOKIE_NAME = "__Host-onea-csrf"
# The SPA reads the token from GET /api/v1/auth/csrf/ (body), admin forms from the page:
# no script needs to read the cookie.
CSRF_COOKIE_HTTPONLY = True

# --- T13: JSON logs in production (no personal data), metrics token from the environment ---
LOGGING = {  # noqa: F405
    **LOGGING,  # noqa: F405
    "formatters": {"json": {"()": "apps.core.journalisation.FormateurJson"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
            "filters": ["masquage"],
        },
    },
}
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
