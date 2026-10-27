from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, env

DEBUG = False
SECRET_KEY = env("SECRET_KEY")  # required in production, no default
if not env("OIDC_OP_BASE_URL").startswith("https://"):  # required in production, no default
    raise ImproperlyConfigured("OIDC_OP_BASE_URL must be an https:// URL in production")
if not env.bool("OIDC_VERIFY_SSL", default=True):
    raise ImproperlyConfigured("OIDC_VERIFY_SSL must not be disabled in production")
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
