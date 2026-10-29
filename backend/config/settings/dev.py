from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, SPECTACULAR_SETTINGS, env

DEBUG = True
DOCUMENTS_CREER_DOSSIER = True  # create the local documents folder at startup
OIDC_ALLOWED_AZP = [*OIDC_ALLOWED_AZP, "onea-dev-cli"]  # noqa: F405 (dev-only curl client)
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}
