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
