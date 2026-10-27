"""Production settings.

Everything security- or deployment-relevant is REQUIRED from the environment: there are
no localhost/mailpit fallbacks. A missing variable raises ImproperlyConfigured at startup.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, env

DEBUG = False
SECRET_KEY = env("SECRET_KEY")  # required in production, no default
DATABASES = {"default": env.db("DATABASE_URL")}  # required
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # required
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")  # required
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")  # required

_email = env.email_url("EMAIL_URL")  # required (no mailpit default)
EMAIL_BACKEND = _email["EMAIL_BACKEND"]
EMAIL_HOST = _email.get("EMAIL_HOST", "")
EMAIL_PORT = _email.get("EMAIL_PORT", 25)
EMAIL_HOST_USER = _email.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = _email.get("EMAIL_HOST_PASSWORD", "")
# django-environ maps smtps:// to STARTTLS; on a smtps:// URL (implicit TLS, usually port
# 465) Django needs EMAIL_USE_SSL instead. The two are mutually exclusive.
EMAIL_USE_SSL = _email.get("EMAIL_USE_SSL", False) or env("EMAIL_URL").startswith("smtps://")
EMAIL_USE_TLS = _email.get("EMAIL_USE_TLS", False) and not EMAIL_USE_SSL
EMAIL_TIMEOUT = 10  # seconds; a dead relay must not hang a worker

if not env("OIDC_OP_BASE_URL").startswith("https://"):  # required in production, no default
    raise ImproperlyConfigured("OIDC_OP_BASE_URL must be an https:// URL in production")
if not env.bool("OIDC_VERIFY_SSL", default=True):
    raise ImproperlyConfigured("OIDC_VERIFY_SSL must not be disabled in production")

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
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
