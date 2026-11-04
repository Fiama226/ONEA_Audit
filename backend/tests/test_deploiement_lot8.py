"""Câblage du lot 8 (suivi, relances, recherche) dans le déploiement et les réglages."""

import re
from pathlib import Path
from typing import Any, cast

import yaml
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


# Seule exception : backup.sh purge les anciennes sauvegardes `keycloak-<h>.dump` (revue finale I3).
PURGE_ANCIENNES_SAUVEGARDES = RACINE / "scripts" / "backup.sh"


def test_aucun_fichier_d_infrastructure_ne_mentionne_keycloak() -> None:
    for relatif in INFRA_SANS_KEYCLOAK:
        texte = (RACINE / relatif).read_text(encoding="utf-8").lower()
        assert "keycloak" not in texte, relatif
    for dossier in ("scripts", "docker"):
        for fichier in (RACINE / dossier).rglob("*"):
            if not fichier.is_file():
                continue
            texte = fichier.read_text(encoding="utf-8").lower()
            if fichier == PURGE_ANCIENNES_SAUVEGARDES:
                lignes = [ligne.strip() for ligne in texte.splitlines() if "keycloak" in ligne]
                assert lignes, fichier
                assert all(ligne.startswith("#") or "keycloak-" in ligne for ligne in lignes)
                continue
            assert "keycloak" not in texte, fichier
    assert not (RACINE / "docker" / "keycloak").exists()


def test_backup_purge_les_anciennes_sauvegardes_keycloak_avec_leur_jeu() -> None:
    texte = PURGE_ANCIENNES_SAUVEGARDES.read_text(encoding="utf-8")
    assert 'for old in "$DEST"/keycloak-*.dump; do' in texte
    assert '[ -f "$DEST/manifeste-$h.sha256" ] || rm -f "$old"' in texte


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


# --- AUTH-01 : les courriels d'authentification atteignent le relais SMTP par le worker ---


def _reseaux(services: dict[str, Any], nom: str) -> set[str]:
    reseaux = services[nom]["networks"]
    return set(reseaux if isinstance(reseaux, list) else reseaux.keys())


def test_courriels_d_authentification_ont_un_chemin_vers_le_relais_smtp() -> None:
    """`web` n'a aucune sortie réseau (choix délibéré) : il confie chaque courriel
    d'authentification au worker par le broker, et seul le worker atteint le relais."""
    compose = yaml.safe_load(COMPOSE_PROD)
    services, reseaux = compose["services"], compose["networks"]
    # Le worker atteint le relais : réseau `mail-out` (non interne) et mot de passe SMTP.
    assert "mail-out" in _reseaux(services, "worker")
    assert not (reseaux["mail-out"] or {}).get("internal", False)
    assert "email_password" in services["worker"]["secrets"]
    fichier = services["worker"]["environment"]["EMAIL_PASSWORD_FILE"]
    assert fichier == "/run/secrets/email_password"  # noqa: S105 - a path, not a secret
    # web atteint le worker par le broker (redis) : réseau `backend` commun aux trois.
    commun = _reseaux(services, "web") & _reseaux(services, "worker") & _reseaux(services, "redis")
    assert "backend" in commun
    assert (
        services["web"]["environment"]["REDIS_URL"]
        == services["worker"]["environment"]["REDIS_URL"]
    )
    # web lui-même reste sans route sortante et sans mot de passe SMTP.
    assert all((reseaux[n] or {}).get("internal") for n in _reseaux(services, "web"))
    assert "email_password" not in services["web"]["secrets"]
    # Les tâches d'envoi passent par la file `auth` (N2) : le worker la sert aussi.
    commande = services["worker"]["command"]
    assert "worker" in commande and commande[commande.index("-Q") + 1] == "celery,auth"


def test_le_code_web_n_envoie_aucun_courriel_d_authentification_lui_meme() -> None:
    """Les modules exécutés dans `web` mettent en file ; seul le worker appelle `courriels`."""
    users = RACINE / "backend" / "apps" / "users"
    for module in ("auth_views.py", "services.py", "provisioning.py", "account_views.py"):
        texte = (users / module).read_text(encoding="utf-8")
        assert "from .courriels import" not in texte, module
        assert "send_mail" not in texte, module
    from apps.users import tasks

    noms = {t.name for t in (tasks.envoyer_code_connexion, tasks.envoyer_mot_de_passe_temporaire)}
    assert noms == {"users.envoyer_code_connexion", "users.envoyer_mot_de_passe_temporaire"}


# --- N2 / N5 : file dédiée aux courriels d'authentification, réglages transmis ---


def _option(commande: list[str], nom: str) -> str:
    return commande[commande.index(nom) + 1]


def test_un_worker_dedie_sert_la_file_auth_sans_attendre_les_documents() -> None:
    """Un PDF peut occuper le worker principal 8 min : le code de connexion (valable 10 min)
    et les mots de passe en attente (1 h) passent par un worker qui ne sert que `auth`."""
    compose = yaml.safe_load(COMPOSE_PROD)
    services, reseaux = compose["services"], compose["networks"]
    dedie = services["worker-auth"]
    commande = dedie["command"]
    assert commande[:4] == ["celery", "-A", "config", "worker"]
    assert _option(commande, "-Q") == "auth"
    assert _option(commande, "-O") == "fair"
    assert _option(commande, "--prefetch-multiplier") == "1"
    assert _option(commande, "--concurrency") == "1"
    assert _reseaux(services, "worker-auth") == {"backend", "mail-out"}
    assert not (reseaux["mail-out"] or {}).get("internal", False)
    # La clé SECRET_KEY déchiffre les mots de passe en attente ; le secret SMTP pour le relais.
    assert {"secret_key", "secret_key_fallbacks", "email_password"} <= set(dedie["secrets"])
    assert dedie["environment"]["EMAIL_PASSWORD_FILE"] == "/run/secrets/email_password"  # noqa: S105
    assert dedie["environment"]["REDIS_URL"] == services["web"]["environment"]["REDIS_URL"]
    assert "healthcheck" in dedie
    # Le worker principal sert aussi `auth` (secours), en distribution équitable.
    principal = services["worker"]["command"]
    assert _option(principal, "-O") == "fair"
    assert _option(principal, "--prefetch-multiplier") == "1"


def test_le_worker_de_dev_sert_aussi_la_file_auth() -> None:
    dev = yaml.safe_load((RACINE / "docker" / "compose.dev.yml").read_text(encoding="utf-8"))
    commande = dev["services"]["worker"]["command"]
    assert _option(commande, "-Q") == "celery,auth"


def test_routes_celery_des_courriels_d_authentification() -> None:
    routes = settings.CELERY_TASK_ROUTES
    assert {routes[n]["queue"] for n in routes if n.startswith("users.envoyer_")} == {"auth"}


REGLAGES_AUTH = (
    "AUTH_REINITIALISATION_ECHECS_MAX",
    "AUTH_CODES_CONNEXION_MAX",
)


def test_reglages_d_authentification_transmis_et_documentes() -> None:
    compose = yaml.safe_load(COMPOSE_PROD)
    env = compose["x-backend-env"]
    modele = (RACINE / ".env.prod.example").read_text(encoding="utf-8")
    for nom in REGLAGES_AUTH:
        assert nom in env, nom
        assert nom in modele, nom
    taux = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    for portee in taux:
        variable = f"THROTTLE_RATE_{portee.upper()}"
        if portee in {
            "connexion",
            "connexion_code",
            "mot_de_passe_oublie",
            "mot_de_passe_oublie_ip",
            "reinitialisation",
            "changement_mot_de_passe",
            "echecs_connexion",
            "echecs_reinitialisation",
            "echecs_tous",
        }:
            assert variable in modele, variable


# --- D4 : les scripts d'exploitation connaissent worker-auth ---


def _workers_celery() -> list[str]:
    services = yaml.safe_load(COMPOSE_PROD)["services"]
    return [
        nom
        for nom, service in services.items()
        if isinstance(service.get("command"), list)
        and service["command"][:4] == ["celery", "-A", "config", "worker"]
    ]


def test_restauration_arrete_tous_les_workers() -> None:
    texte = (RACINE / "scripts" / "restore.sh").read_text(encoding="utf-8")
    arret = next(ligne for ligne in texte.splitlines() if ligne.startswith("compose stop "))
    assert set(_workers_celery()) == {"worker", "worker-auth"}
    for nom in [*_workers_celery(), "web", "beat"]:
        assert nom in arret.split(), nom


def test_banc_des_secrets_inspecte_tous_les_workers() -> None:
    texte = (RACINE / "scripts" / "recette" / "tests" / "secrets.sh").read_text(encoding="utf-8")
    boucle = next(ligne for ligne in texte.splitlines() if ligne.startswith("for service in "))
    for nom in _workers_celery():
        assert nom in boucle.split(), nom


def test_commentaire_des_reseaux_a_jour() -> None:
    ligne = next(
        ligne for ligne in COMPOSE_PROD.splitlines() if ligne.startswith("#   backend  internal")
    )
    assert "worker-auth" in ligne
