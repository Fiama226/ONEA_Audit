"""Guard on DOCUMENTS_ROOT in production (pure function, container paths simulated)."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.documents_settings import valider_documents_root


def test_conteneur_depot_a_la_racine_et_dossier_hors_code_accepte() -> None:
    # Image layout: COPY backend/ /app/ -> BASE_DIR=/app, BASE_DIR.parent == "/".
    valider_documents_root("/var/lib/onea/documents", repo_root="/", code_dir="/app")


@pytest.mark.parametrize("racine", ["/app", "/app/documents", "/app/../app/x"])
def test_conteneur_dossier_dans_le_code_refuse(racine: str) -> None:
    with pytest.raises(ImproperlyConfigured, match="DOCUMENTS_ROOT"):
        valider_documents_root(racine, repo_root="/", code_dir="/app")


def test_depot_normal_dossier_dedans_refuse() -> None:
    with pytest.raises(ImproperlyConfigured, match="DOCUMENTS_ROOT"):
        valider_documents_root(
            "/srv/onea-audit/media", repo_root="/srv/onea-audit", code_dir="/srv/onea-audit/backend"
        )
    valider_documents_root(
        "/srv/onea/documents", repo_root="/srv/onea-audit", code_dir="/srv/onea-audit/backend"
    )


@pytest.mark.parametrize("racine", ["", "relatif/dossier", "./x"])
def test_chemin_relatif_refuse(racine: str) -> None:
    with pytest.raises(ImproperlyConfigured, match="DOCUMENTS_ROOT"):
        valider_documents_root(racine, repo_root="/", code_dir="/app")


def test_racine_du_systeme_de_fichiers_refusee() -> None:
    with pytest.raises(ImproperlyConfigured, match="DOCUMENTS_ROOT"):
        valider_documents_root("/", repo_root="/", code_dir="/app")
