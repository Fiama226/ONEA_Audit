from .base import *  # noqa: F403
from .base import SPECTACULAR_SETTINGS, env

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://onea:onea@localhost:5432/onea")}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECRET_KEY = "test-only-key"  # noqa: S105
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}

INSTALLED_APPS = [*INSTALLED_APPS, "tests.testapp"]  # noqa: F405
ROOT_URLCONF = "tests.testapp.root_urls"
