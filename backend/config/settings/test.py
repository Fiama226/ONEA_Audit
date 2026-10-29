import tempfile
from pathlib import Path

from .base import *  # noqa: F403
from .base import SPECTACULAR_SETTINGS, env

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://onea:onea@localhost:5432/onea")}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECRET_KEY = "test-only-key"  # noqa: S105
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}
OIDC_ALLOWED_AZP = ["onea-frontend", "onea-dev-cli"]
KEYCLOAK_ADMIN_API_CLIENT_SECRET = ""  # tests inject a fake client or set it explicitly
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

STOCKAGE_PREUVES = {
    "BACKEND": "tests.accomplissement.fakes.StockageDisqueTemporaire",
    "OPTIONS": {"RACINE": str(Path(tempfile.gettempdir()) / "onea-tests-preuves")},
}

INSTALLED_APPS = [*INSTALLED_APPS, "tests.testapp"]  # noqa: F405
ROOT_URLCONF = "tests.testapp.root_urls"
