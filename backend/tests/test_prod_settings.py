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
    "CSRF_TRUSTED_ORIGINS": "https://audit.onea.bf",
    "SESSION_COOKIE_SECURE": "true",
    "DOCUMENTS_ROOT": "/var/lib/onea/documents",
    "MEILI_MASTER_KEY": "prod-meili-key",
    "PLATEFORME_URL": "https://audit.onea.bf",
    "TRUSTED_PROXY_CIDRS": "172.30.10.2",
}

PROBE = """
import json
import sys
import django
django.setup()
from django.conf import settings
print(json.dumps({
    "hosts": settings.ALLOWED_HOSTS,
    "cors": [n for n in [*settings.INSTALLED_APPS, *settings.MIDDLEWARE] if "cors" in n.lower()],
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
    "session_name": settings.SESSION_COOKIE_NAME,
    "csrf_name": settings.CSRF_COOKIE_NAME,
    "session_httponly": settings.SESSION_COOKIE_HTTPONLY,
    "csrf_httponly": settings.CSRF_COOKIE_HTTPONLY,
    "samesite": settings.SESSION_COOKIE_SAMESITE,
    "session_age": settings.SESSION_COOKIE_AGE,
    "cache": settings.CACHES["default"],
    "auth": settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
    "admin": settings.DJANGO_ADMIN_ENABLED,
    "debug": settings.DEBUG,
    "documents_root": settings.DOCUMENTS_ROOT,
    "documents_backend": settings.STORAGES["documents"]["BACKEND"],
    "media_url": getattr(sys.modules[settings.SETTINGS_MODULE], "MEDIA_URL", ""),
    "proxies": settings.TRUSTED_PROXY_CIDRS,
}))
"""


def load_prod(env: dict[str, str], code: str = PROBE) -> subprocess.CompletedProcess[str]:
    clean = {
        k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME"}
    }
    clean.update(env)
    clean["ONEA_IGNORE_DOTENV"] = "true"
    clean["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
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
    assert data["cors"] == []  # same origin: no CORS app nor middleware
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


def test_prod_cookies_are_host_prefixed_secure_httponly() -> None:
    data = probe(PROD_ENV)
    assert data["session_name"] == "__Host-onea-session"
    assert data["csrf_name"] == "__Host-onea-csrf"
    assert data["session_secure"] is True and data["csrf_secure"] is True
    assert data["session_httponly"] is True and data["csrf_httponly"] is True
    assert data["samesite"] == "Lax"
    assert data["session_age"] == 8 * 3600


def test_prod_auth_is_session_first_and_cache_is_redis() -> None:
    data = probe({**PROD_ENV, "REDIS_URL": "redis://:pw@redis:6379/0"})
    assert data["auth"] == ["apps.users.authentication.SessionAuthentication401"]
    cache = data["cache"]
    assert isinstance(cache, dict)
    assert cache["BACKEND"] == "django.core.cache.backends.redis.RedisCache"
    assert cache["LOCATION"] == "redis://:pw@redis:6379/1"


def test_prod_ignores_a_stale_cors_variable() -> None:
    assert probe({**PROD_ENV, "CORS_ALLOWED_ORIGINS": "https://malveillant.example"})["cors"] == []


def test_prod_cache_url_overrides_redis_url() -> None:
    data = probe({**PROD_ENV, "CACHE_URL": "redis://cache:6379/5"})
    cache = data["cache"]
    assert isinstance(cache, dict)
    assert cache["LOCATION"] == "redis://cache:6379/5"


def test_prod_cors_preflight_from_foreign_origin_has_no_allow_origin() -> None:
    code = (
        "import django\ndjango.setup()\nfrom django.test import Client\n"
        "r = Client().options('/api/v1/me/', HTTP_ORIGIN='https://malveillant.example',"
        " HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET', HTTP_HOST='audit.onea.bf', secure=True)\n"
        "print('ACAO', r.headers.get('Access-Control-Allow-Origin'))\n"
    )
    stale = {**PROD_ENV, "CORS_ALLOWED_ORIGINS": "https://malveillant.example"}
    result = load_prod(stale, code=code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "ACAO None"


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


@pytest.mark.parametrize("url", ["consolemail://", "filemail:///tmp/courriels", "memorymail://"])
def test_prod_refuse_un_backend_qui_ecrit_les_courriels_hors_smtp(url: str) -> None:
    """AUTH-07 : un backend console, fichier ou mémoire écrirait les codes et les mots de
    passe temporaires dans les journaux ou sur le disque."""
    result = load_prod({**PROD_ENV, "EMAIL_URL": url})
    assert result.returncode != 0
    assert "EMAIL_URL" in result.stderr


@pytest.mark.parametrize(
    ("variable", "valeur"),
    [
        ("AUTH_REINITIALISATION_ECHECS_MAX", "0"),
        ("AUTH_REINITIALISATION_ECHECS_MAX", "abc"),
        ("AUTH_CODES_CONNEXION_MAX", "-1"),
        ("THROTTLE_RATE_ECHECS_TOUS", "beaucoup"),
        ("THROTTLE_RATE_ECHECS_TOUS", "0/15min"),
    ],
)
def test_prod_refuse_un_reglage_d_authentification_invalide(variable: str, valeur: str) -> None:
    """N5 : un plafond nul, négatif ou illisible empêche le démarrage."""
    result = load_prod({**PROD_ENV, variable: valeur})
    assert result.returncode != 0
    assert variable in result.stderr


def test_prod_dummymail_avec_un_hote_reste_sans_envoi() -> None:
    """N9 : un hôte dans dummymail:// ne fait pas croire à un envoi réel."""
    code = (
        PROBE + "\nfrom apps.users.auth_services import envoi_courriel_actif\n"
        "print(envoi_courriel_actif())"
    )
    result = load_prod({**PROD_ENV, "EMAIL_URL": "dummymail://relais.onea.bf"}, code=code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False"


def test_prod_accepte_dummymail_pour_fonctionner_sans_courriel() -> None:
    """Sans relais SMTP : rien n'est envoyé, les mots de passe sont affichés à l'opérateur."""
    code = (
        PROBE + "\nfrom apps.users.auth_services import envoi_courriel_actif\n"
        "print(envoi_courriel_actif())"
    )
    result = load_prod({**PROD_ENV, "EMAIL_URL": "dummymail://"}, code=code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False"


@pytest.mark.parametrize(
    "url",
    [
        "http://audit.onea.bf",
        "ftp://audit.onea.bf",
        "https://",
        "https://u:p@audit.onea.bf",
        "audit.onea.bf",
    ],
)
def test_prod_refuse_plateforme_url_non_https(url: str) -> None:
    result = load_prod({**PROD_ENV, "PLATEFORME_URL": url})
    assert result.returncode != 0
    assert "PLATEFORME_URL" in result.stderr


def test_prod_plateforme_url_sans_barre_finale() -> None:
    code = PROBE + "\nfrom django.conf import settings as s; print(s.PLATEFORME_URL)"
    result = load_prod({**PROD_ENV, "PLATEFORME_URL": "https://audit.onea.bf/"}, code=code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "https://audit.onea.bf"


def test_prod_admin_can_be_enabled_explicitly() -> None:
    assert probe({**PROD_ENV, "DJANGO_ADMIN_ENABLED": "true"})["admin"] is True


@pytest.mark.parametrize(
    "missing",
    [
        "SECRET_KEY",
        "DATABASE_URL",
        "EMAIL_URL",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
        "SESSION_COOKIE_SECURE",
        "PLATEFORME_URL",
        "TRUSTED_PROXY_CIDRS",
    ],
)
def test_prod_settings_refuse_to_start_without_required_variable(missing: str) -> None:
    env = {k: v for k, v in PROD_ENV.items() if k != missing}
    result = load_prod(env)
    assert result.returncode != 0
    assert missing in result.stderr


@pytest.mark.parametrize("flag", ["CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"])
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


def test_prod_antivirus_clamav_echec_ferme_par_defaut() -> None:
    code = PROBE.replace(
        '"debug": settings.DEBUG,',
        '"debug": settings.DEBUG, "av": settings.ANTIVIRUS_MOTEUR,'
        ' "av_ferme": settings.ANTIVIRUS_ECHEC_FERME,'
        ' "av_taille": settings.ANTIVIRUS_TAILLE_MAX_OCTETS,',
    )
    result = load_prod(PROD_ENV, code)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["av"] == "clamav"
    assert data["av_ferme"] is True
    assert data["av_taille"] == 50 * 1024 * 1024


def test_prod_refuse_antivirus_aucun_sans_accord_explicite() -> None:
    result = load_prod({**PROD_ENV, "ANTIVIRUS_MOTEUR": "aucun"})
    assert result.returncode != 0
    assert "ANTIVIRUS_MOTEUR" in result.stderr
    assert probe({**PROD_ENV, "ANTIVIRUS_MOTEUR": "aucun", "ANTIVIRUS_AUTORISER_AUCUN": "true"})


@pytest.mark.parametrize("valeur", ["false", "0", ""])
def test_prod_refuse_session_cookie_secure_desactive(valeur: str) -> None:
    result = load_prod({**PROD_ENV, "SESSION_COOKIE_SECURE": valeur})
    assert result.returncode != 0
    assert "SESSION_COOKIE_SECURE" in result.stderr


def test_prod_lit_les_mandataires_de_confiance() -> None:
    assert probe(PROD_ENV)["proxies"] == ["172.30.10.2"]
    assert probe({**PROD_ENV, "TRUSTED_PROXY_CIDRS": "172.30.10.2, 10.0.0.0/8"})["proxies"] == [
        "172.30.10.2",
        "10.0.0.0/8",
    ]


@pytest.mark.parametrize("valeur", ["", " ", ",", "nginx", "172.30.10.2,pas-une-adresse"])
def test_prod_refuse_des_mandataires_de_confiance_vides_ou_invalides(valeur: str) -> None:
    """Empty, every per-address auth limit would become ONE counter for the whole
    organisation (30 failures from anyone = 429 for everybody): refuse to start (M6)."""
    result = load_prod({**PROD_ENV, "TRUSTED_PROXY_CIDRS": valeur})
    assert result.returncode != 0
    assert "TRUSTED_PROXY_CIDRS" in result.stderr
