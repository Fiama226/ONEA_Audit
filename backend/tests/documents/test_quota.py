"""Quota de stockage unique : gabarits, versions Word/PDF et pièces justificatives."""

from pathlib import Path
from typing import Any

import pytest
from django.db import connection

from apps.core.exceptions import RegleMetierError
from apps.documents.models import DocumentVersion, GabaritDocument
from apps.documents.services.quota import controler_quota, utilise_octets
from tests.accomplissement.factories import PieceFactory

pytestmark = pytest.mark.django_db

KO = 1024


def _taille(table: str, colonne: str, pk: Any, valeur: int) -> None:
    with connection.cursor() as cur:  # SQL brut : les gardes du modèle gèlent les tailles
        cur.execute(f"UPDATE {table} SET {colonne} = %s WHERE id = %s", [valeur, pk])  # noqa: S608


@pytest.fixture
def stockage_pieces(settings: Any, tmp_path: Path) -> None:
    settings.STOCKAGE_PREUVES = {
        "BACKEND": "tests.accomplissement.fakes.StockageDisqueTemporaire",
        "OPTIONS": {"RACINE": str(tmp_path / "preuves")},
    }


def test_utilise_octets_compte_gabarits_versions_et_pieces(
    gabarit_actif_test: GabaritDocument, version_prete: DocumentVersion, stockage_pieces: None
) -> None:
    _taille("documents_gabaritdocument", "taille", gabarit_actif_test.pk, 300 * KO)
    _taille("documents_documentversion", "taille_docx", version_prete.pk, 200 * KO)
    _taille("documents_documentversion", "taille_pdf", version_prete.pk, 100 * KO)
    assert utilise_octets() == 600 * KO
    piece = PieceFactory(contenu=b"%PDF-1.4 " + b"x" * 50)
    assert utilise_octets() == 600 * KO + piece.taille_octets


def test_piece_supprimee_logiquement_reste_comptee(stockage_pieces: None) -> None:
    piece = PieceFactory(contenu=b"%PDF-1.4 " + b"x" * 500)
    avant = utilise_octets()
    piece.soft_delete(piece.deposee_par)
    assert utilise_octets() == avant == piece.taille_octets


def test_controler_quota_refuse_quand_les_pieces_font_depasser(
    settings: Any, stockage_pieces: None
) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1
    piece = PieceFactory(contenu=b"%PDF-1.4 " + b"x" * 500)
    _taille("accomplissement_piecejustificative", "taille_octets", piece.pk, 924 * KO)
    controler_quota(100 * KO)  # 924 + 100 Ko = 1 Mo : accepté
    with pytest.raises(RegleMetierError, match="quota"):
        controler_quota(100 * KO + 1)


def test_quota_zero_sans_limite(settings: Any) -> None:
    settings.DOCUMENTS_QUOTA_MO = 0
    controler_quota(10**12)


def test_taille_inconnue_refusee_seulement_si_quota_atteint(
    settings: Any, gabarit_actif_test: GabaritDocument
) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1
    _taille("documents_gabaritdocument", "taille", gabarit_actif_test.pk, 1024 * KO - 1)
    controler_quota(0)
    _taille("documents_gabaritdocument", "taille", gabarit_actif_test.pk, 1024 * KO)
    with pytest.raises(RegleMetierError, match="quota"):
        controler_quota(0)
