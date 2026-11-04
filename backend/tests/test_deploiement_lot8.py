"""Câblage du lot 8 (suivi, relances, recherche) dans le déploiement et les réglages."""

import re
from pathlib import Path

from django.conf import settings

RACINE = Path(__file__).resolve().parents[2]
COMPOSE_PROD = (RACINE / "docker" / "compose.prod.yml").read_text(encoding="utf-8")
NGINX = RACINE / "docker" / "nginx"


def _service(nom: str) -> str:
    """Bloc texte d'un service de `compose.prod.yml` (jusqu'au service suivant)."""
    motif = r"\n  " + re.escape(nom) + r":\n(.*?)(?=\n  [a-z][\w-]*:\n|\Z)"
    trouve = re.search(motif, COMPOSE_PROD, re.S)
    assert trouve, nom
    return trouve.group(0)


def test_nginx_n_expose_pas_meilisearch() -> None:
    for fichier in NGINX.rglob("*.conf*"):
        texte = fichier.read_text(encoding="utf-8").lower()
        assert "7700" not in texte, fichier
        assert "meilisearch" not in texte, fichier


def test_frontend_sans_acces_direct_au_moteur() -> None:
    for fichier in (RACINE / "frontend" / "src").rglob("*"):
        if fichier.suffix not in {".ts", ".tsx"}:
            continue
        texte = fichier.read_text(encoding="utf-8")
        assert "MEILI" not in texte and "7700" not in texte, fichier


def test_planification_du_suivi_et_de_la_recherche() -> None:
    planning = settings.CELERY_BEAT_SCHEDULE
    assert {"suivi-relances", "suivi-reconciliation", "recherche-reconciliation"} <= set(planning)
    relances = planning["suivi-relances"]["schedule"]
    assert relances.hour == {7} and relances.minute == {0}


def test_migrate_configure_l_index_de_recherche() -> None:
    migrate = _service("migrate")
    assert "python manage.py configurer_recherche" in migrate


def test_environnement_prod_porte_les_liens_et_les_relances() -> None:
    assert "PLATEFORME_URL: https://${PUBLIC_HOST" in COMPOSE_PROD
    assert "RELANCES_ACTIVES:" in COMPOSE_PROD


def test_plateforme_url_https_exigee_en_production() -> None:
    texte = (RACINE / "backend" / "config" / "settings" / "prod.py").read_text(encoding="utf-8")
    assert "PLATEFORME_URL must be an https:// URL in production" in texte


# --- Task 10 : plus de Keycloak dans la pile, même origine ---
INFRA_SANS_KEYCLOAK = [
    "docker/compose.yml",
    "docker/compose.dev.yml",
    "docker/compose.prod.yml",
    "docker/nginx/prod.conf",
    "docker/nginx/dev.conf",
    ".env.example",
    ".env.prod.example",
    ".env.recette.example",
    "Makefile",
]


def test_aucun_fichier_d_infrastructure_ne_mentionne_keycloak() -> None:
    for relatif in INFRA_SANS_KEYCLOAK:
        texte = (RACINE / relatif).read_text(encoding="utf-8").lower()
        assert "keycloak" not in texte, relatif
    for dossier in ("scripts", "docker"):
        for fichier in (RACINE / dossier).rglob("*"):
            if fichier.is_file():
                assert "keycloak" not in fichier.read_text(encoding="utf-8").lower(), fichier
    assert not (RACINE / "docker" / "keycloak").exists()


def test_env_example_sans_variable_keycloak_ni_sso() -> None:
    for modele in (".env.example", ".env.prod.example", ".env.recette.example"):
        lignes = (RACINE / modele).read_text(encoding="utf-8").splitlines()
        cles = [ligne.split("=", 1)[0] for ligne in lignes if "=" in ligne and ligne[0] != "#"]
        assert not [c for c in cles if c.startswith(("KEYCLOAK_", "SSO_", "OIDC_"))], modele


def test_nginx_prod_une_seule_origine_sans_proxy_sso() -> None:
    texte = (NGINX / "prod.conf").read_text(encoding="utf-8")
    assert "SSO_HOST" not in texte and "/realms/" not in texte
    assert "location /api/" in texte and "proxy_pass http://frontend" in texte


def test_prod_exige_session_cookie_secure_et_origines_csrf_dans_compose() -> None:
    assert "SESSION_COOKIE_SECURE:" in COMPOSE_PROD
    assert "CSRF_TRUSTED_ORIGINS: https://${PUBLIC_HOST" in COMPOSE_PROD


def test_vite_proxifie_l_api_pour_une_origine_unique_en_dev() -> None:
    texte = (RACINE / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert "proxy" in texte and '"/api"' in texte


def test_bundle_ca_interne_lu_par_ssl_et_requests() -> None:
    # smtplib (relais SMTP) lit SSL_CERT_FILE, requests lit REQUESTS_CA_BUNDLE (CA_BUNDLE_PATH).
    assert "SSL_CERT_FILE: ${CA_BUNDLE_PATH:-/etc/ssl/certs/ca-certificates.crt}" in COMPOSE_PROD
    assert "REQUESTS_CA_BUNDLE: ${CA_BUNDLE_PATH:-}" in COMPOSE_PROD
