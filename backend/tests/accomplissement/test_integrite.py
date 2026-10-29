import logging
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accomplissement.models import FicheDeTest, PieceJustificative
from apps.accomplissement.services.integrite import (
    ABSENT,
    ouvrir_piece_verifiee,
    verifier_toutes,
)
from apps.accomplissement.services.pieces import deposer_piece
from apps.accomplissement.stockage import FichierIntrouvableError
from apps.documents.integrite import IntegriteError
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import PDF, pdf

pytestmark = pytest.mark.django_db


def _fichier_de(tmp_path: Path, piece: PieceJustificative) -> Path:
    return tmp_path / "preuves" / piece.cle_stockage


@pytest.fixture
def piece(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> PieceJustificative:
    return deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)


def test_telechargement_intact(piece: PieceJustificative) -> None:
    with ouvrir_piece_verifiee(piece) as flux:
        assert flux.read() == PDF


def test_telechargement_detecte_alteration(
    tmp_path: Path, piece: PieceJustificative, caplog: pytest.LogCaptureFixture
) -> None:
    chemin = _fichier_de(tmp_path, piece)
    chemin.chmod(0o600)
    chemin.write_bytes(b"%PDF-1.7 altere")
    with caplog.at_level(logging.CRITICAL), pytest.raises(IntegriteError) as exc:
        ouvrir_piece_verifiee(piece)
    assert exc.value.status_http == 409
    assert "Empreinte invalide" in caplog.text


def test_fichier_absent(tmp_path: Path, piece: PieceJustificative) -> None:
    _fichier_de(tmp_path, piece).unlink()
    with pytest.raises(FichierIntrouvableError):
        ouvrir_piece_verifiee(piece)


def test_verifier_toutes_signale_les_ecarts(
    tmp_path: Path,
    fiche_auditeur: FicheDeTest,
    auditeur_mission: User,
    piece: PieceJustificative,
) -> None:
    saine = deposer_piece(
        fiche_auditeur, fichier=pdf("b.pdf", PDF + b"b"), libelle="B", by=auditeur_mission
    )
    absente = deposer_piece(
        fiche_auditeur, fichier=pdf("c.pdf", PDF + b"c"), libelle="C", by=auditeur_mission
    )
    chemin = _fichier_de(tmp_path, piece)
    chemin.chmod(0o600)
    chemin.write_bytes(b"autre contenu")
    _fichier_de(tmp_path, absente).unlink()
    ecarts = {e.piece.pk: e for e in verifier_toutes()}
    assert set(ecarts) == {piece.pk, absente.pk}
    assert saine.pk not in ecarts
    assert ecarts[piece.pk].attendu == piece.empreinte_sha256
    assert ecarts[piece.pk].obtenu not in (piece.empreinte_sha256, ABSENT)
    assert ecarts[absente.pk].obtenu == ABSENT
    assert [e.piece.pk for e in verifier_toutes(piece.mission)] and len(
        verifier_toutes(piece.mission)
    ) == 2


def test_verifier_pieces_commande(
    tmp_path: Path, fiche_auditeur: FicheDeTest, auditeur_mission: User, piece: PieceJustificative
) -> None:
    sortie = StringIO()
    call_command("verifier_pieces", stdout=sortie)
    assert "0 écart" in sortie.getvalue()
    absente = deposer_piece(
        fiche_auditeur, fichier=pdf("c.pdf", PDF + b"c"), libelle="C", by=auditeur_mission
    )
    chemin = _fichier_de(tmp_path, piece)
    chemin.chmod(0o600)
    chemin.write_bytes(b"x")
    _fichier_de(tmp_path, absente).unlink()
    erreur = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("verifier_pieces", stdout=StringIO(), stderr=erreur)
    assert exc.value.code == 1
    assert "fichier absent" in erreur.getvalue()


def test_verifier_pieces_mission_inconnue() -> None:
    with pytest.raises(CommandError):
        call_command("verifier_pieces", "--mission", "DAI/2099/M99")
