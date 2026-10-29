import logging
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accomplissement.models import FicheDeTest, PieceJustificative
from apps.accomplissement.services.integrite import (
    ABSENT,
    ORPHELIN,
    ouvrir_piece_verifiee,
    verifier_toutes,
)
from apps.accomplissement.services.pieces import deposer_piece
from apps.accomplissement.stockage import FichierIntrouvableError, stockage_preuves
from apps.documents.integrite import IntegriteError
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import PDF, pdf

pytestmark = pytest.mark.django_db


def _fichiers(tmp_path: Path) -> list[Path]:
    return [f for f in (tmp_path / "preuves").rglob("*") if f.is_file()]


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
    ecarts = {e.piece.pk: e for e in verifier_toutes() if e.piece}
    assert set(ecarts) == {piece.pk, absente.pk}
    assert saine.pk not in ecarts
    assert ecarts[piece.pk].attendu == piece.empreinte_sha256
    assert ecarts[piece.pk].obtenu not in (piece.empreinte_sha256, ABSENT)
    assert ecarts[absente.pk].obtenu == ABSENT
    assert len(verifier_toutes(piece.mission)) == 2


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


def test_telechargement_fichier_grossi_refuse(tmp_path: Path, piece: PieceJustificative) -> None:
    chemin = _fichier_de(tmp_path, piece)
    chemin.chmod(0o600)
    chemin.write_bytes(PDF + b"y" * 5000)  # plus gros que taille_octets
    with pytest.raises(IntegriteError):
        ouvrir_piece_verifiee(piece)


def test_telechargement_lit_par_blocs_bornes(
    monkeypatch: pytest.MonkeyPatch, piece: PieceJustificative
) -> None:
    """Aucune lecture non bornée : chaque `read` reçoit une taille de bloc."""
    import apps.accomplissement.services.integrite as module

    tailles: list[int | None] = []
    ouvrir = stockage_preuves().ouvrir

    class Espion:
        def __init__(self, flux: Any) -> None:
            self.flux = flux

        def read(self, n: int | None = None) -> bytes:
            tailles.append(n)
            data: bytes = self.flux.read(n)
            return data

        def __enter__(self) -> "Espion":
            return self

        def __exit__(self, *a: object) -> None:
            self.flux.close()

    class Faux:
        def ouvrir(self, cle: str) -> Espion:
            return Espion(ouvrir(cle))

    monkeypatch.setattr(module, "stockage_preuves", lambda: Faux())
    with ouvrir_piece_verifiee(piece) as flux:
        assert flux.read() == PDF
    assert tailles
    assert all(isinstance(t, int) and t > 0 for t in tailles)


def test_orphelin_detecte_par_le_balayage(tmp_path: Path, piece: PieceJustificative) -> None:
    orphelin = stockage_preuves().deposer(
        BytesIO(b"%PDF-1.7 orphelin"), prefixe=f"preuves/{piece.mission_id}", taille_max=10_000
    )
    ecarts = verifier_toutes()
    assert [e.cle for e in ecarts] == [orphelin.cle]
    assert ecarts[0].piece is None
    assert ecarts[0].obtenu == ORPHELIN
    assert len(_fichiers(tmp_path)) == 2  # jamais effacé


def test_orphelin_apres_echec_base_detecte(
    monkeypatch: pytest.MonkeyPatch, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    def echec(*args: object, **kwargs: object) -> None:
        raise RuntimeError("commit impossible")

    monkeypatch.setattr("apps.accomplissement.services.pieces.enregistrer", echec)
    with pytest.raises(RuntimeError):
        deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    assert [e.obtenu for e in verifier_toutes()] == [ORPHELIN]


def test_balayage_limite_a_la_mission(piece: PieceJustificative) -> None:
    stockage_preuves().deposer(
        BytesIO(b"%PDF-1.7 autre"), prefixe="preuves/autre-mission", taille_max=10_000
    )
    assert verifier_toutes(piece.mission) == []
    assert len(verifier_toutes()) == 1


def test_commande_signale_les_orphelins(piece: PieceJustificative) -> None:
    stockage_preuves().deposer(
        BytesIO(b"%PDF-1.7 orphelin"), prefixe=f"preuves/{piece.mission_id}", taille_max=10_000
    )
    erreur = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("verifier_pieces", stdout=StringIO(), stderr=erreur)
    assert exc.value.code == 1
    assert "fichier orphelin" in erreur.getvalue()
