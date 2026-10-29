"""Production settings are loaded in a clean subprocess with an explicit environment."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent

PROD_ENV = {
    "SECRET_KEY": "x" * 64,
    "DATABASE_URL": "postgres://u:p@db:5432/onea",
    "EMAIL_URL": "smtp://user:pw@smtp.onea.bf:587",
    "ALLOWED_HOSTS": "audit.onea.bf,.audit.onea.bf",
    "CORS_ALLOWED_ORIGINS": "https://audit.onea.bf",
    "CSRF_TRUSTED_ORIGINS": "https://audit.onea.bf",
    "OIDC_OP_BASE_URL": "https://sso.onea.bf/realms/onea",
    "KEYCLOAK_ADMIN_API_CLIENT_SECRET": "prod-sync-secret",
    "DOCUMENTS_ROOT": "/var/lib/onea/documents",
}

PROBE = """
import json
import sys
import django
django.setup()
from django.conf import settings
print(json.dumps({
    "hosts": settings.ALLOWED_HOSTS,
    "cors": settings.CORS_ALLOWED_ORIGINS,
    "csrf": settings.CSRF_TRUSTED_ORIGINS,
    "db_host": settings.DATABASES["default"]["HOST"],
    "email_host": settings.EMAIL_HOST,
    "email_ssl": getattr(settings, "EMAIL_USE_SSL", False),
    "email_tls": getattr(settings, "EMAIL_USE_TLS", False),
    "email_timeout": settings.EMAIL_TIMEOUT,
    "hsts": settings.SECURE_HSTS_SECONDS,
    "hsts_sub": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "session_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_secure": settings.CSRF_COOKIE_SECURE,
    "proxy_header": settings.SECURE_PROXY_SSL_HEADER,
    "admin": settings.DJANGO_ADMIN_ENABLED,
    "debug": settings.DEBUG,
    "documents_root": settings.DOCUMENTS_ROOT,
    "documents_backend": settings.STORAGES["documents"]["BACKEND"],
    "media_url": getattr(sys.modules[settings.SETTINGS_MODULE], "MEDIA_URL", ""),
}))
"""


def load_prod(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    clean = {
        k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME"}
    }
    clean.update(env)
    clean["ONEA_IGNORE_DOTENV"] = "true"
    clean["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        cwd=BACKEND_DIR,
        env=clean,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def probe(env: dict[str, str]) -> dict[str, object]:
    result = load_prod(env)
    assert result.returncode == 0, result.stderr
    data: dict[str, object] = json.loads(result.stdout.strip().splitlines()[-1])
    return data


def test_prod_settings_load_and_are_hardened() -> None:
    data = probe(PROD_ENV)
    assert data["hosts"] == ["audit.onea.bf", ".audit.onea.bf"]
    assert data["cors"] == ["https://audit.onea.bf"]
    assert data["csrf"] == ["https://audit.onea.bf"]
    assert data["db_host"] == "db"
    assert data["email_host"] == "smtp.onea.bf"
    assert data["hsts"] == 31536000
    assert data["hsts_sub"] is True
    assert data["ssl_redirect"] is True
    assert data["session_secure"] is True
    assert data["csrf_secure"] is True
    assert data["proxy_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert data["admin"] is False
    assert data["debug"] is False


@pytest.mark.parametrize(
    ("url", "ssl", "tls"),
    [
        ("smtps://u:p@smtp.onea.bf:465", True, False),
        ("smtp+ssl://u:p@smtp.onea.bf:465", True, False),
        ("smtp+tls://u:p@smtp.onea.bf:587", False, True),
        ("smtp://smtp.onea.bf:25", False, False),
    ],
)
def test_prod_email_transport_security_and_timeout(url: str, ssl: bool, tls: bool) -> None:
    data = probe({**PROD_ENV, "EMAIL_URL": url})
    assert data["email_ssl"] is ssl
    assert data["email_tls"] is tls
    assert data["email_timeout"] == 10


def test_prod_refuses_http_oidc_base_url() -> None:
    result = load_prod({**PROD_ENV, "OIDC_OP_BASE_URL": "http://sso.onea.bf/realms/onea"})
    assert result.returncode != 0
    assert "https" in result.stderr


def test_prod_refuses_disabled_oidc_ssl_verification() -> None:
    result = load_prod({**PROD_ENV, "OIDC_VERIFY_SSL": "false"})
    assert result.returncode != 0
    assert "OIDC_VERIFY_SSL" in result.stderr


def test_prod_admin_can_be_enabled_explicitly() -> None:
    assert probe({**PROD_ENV, "DJANGO_ADMIN_ENABLED": "true"})["admin"] is True


@pytest.mark.parametrize(
    "missing",
    [
        "SECRET_KEY",
        "DATABASE_URL",
        "EMAIL_URL",
        "ALLOWED_HOSTS",
        "CORS_ALLOWED_ORIGINS",
        "CSRF_TRUSTED_ORIGINS",
        "OIDC_OP_BASE_URL",
    ],
)
def test_prod_settings_refuse_to_start_without_required_variable(missing: str) -> None:
    env = {k: v for k, v in PROD_ENV.items() if k != missing}
    result = load_prod(env)
    assert result.returncode != 0
    assert missing in result.stderr


@pytest.mark.parametrize(
    "flag", ["SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"]
)
def test_prod_security_flags_cannot_be_weakened_by_env(flag: str) -> None:
    data = probe({**PROD_ENV, flag: "false"})
    assert data["session_secure"] is True
    assert data["csrf_secure"] is True
    assert data["ssl_redirect"] is True


@pytest.mark.parametrize("root", ["", "relatif/documents", "/app/documents", "/app"])
def test_prod_exige_documents_root_absolu_hors_depot(root: str) -> None:
    env = {k: v for k, v in PROD_ENV.items() if k != "DOCUMENTS_ROOT"}
    if root:
        env["DOCUMENTS_ROOT"] = root
    result = load_prod(env)
    assert result.returncode != 0
    assert "DOCUMENTS_ROOT" in result.stderr


def test_prod_refuse_documents_root_dans_le_depot() -> None:
    result = load_prod({**PROD_ENV, "DOCUMENTS_ROOT": str(BACKEND_DIR / "media")})
    assert result.returncode != 0
    assert "DOCUMENTS_ROOT" in result.stderr


def test_prod_documents_filesystem_par_defaut() -> None:
    data = probe(PROD_ENV)
    assert data["documents_root"] == "/var/lib/onea/documents"
    assert data["documents_backend"] == "apps.documents.stockage.StockageEcritureUnique"
    assert not data["media_url"]


def test_prod_s3_exige_ses_quatre_variables() -> None:
    s3 = {
        "DOCUMENTS_STORAGE": "s3",
        "DOCUMENTS_S3_ENDPOINT_URL": "https://s3.onea.bf",
        "DOCUMENTS_S3_ACCESS_KEY": "k",
        "DOCUMENTS_S3_SECRET_KEY": "s",
        "DOCUMENTS_S3_BUCKET": "b",
    }
    env = {k: v for k, v in PROD_ENV.items() if k != "DOCUMENTS_ROOT"}
    data = probe({**env, **s3})
    assert data["documents_backend"] == "storages.backends.s3.S3Storage"
    for missing in s3:
        if missing == "DOCUMENTS_STORAGE":
            continue
        result = load_prod({**env, **{k: v for k, v in s3.items() if k != missing}})
        assert result.returncode != 0
        assert missing in result.stderr
