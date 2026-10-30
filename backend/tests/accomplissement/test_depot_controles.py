"""Dépôt d'une pièce : contrôle commun, antivirus et quota unique (lot 9, tâche 15)."""

import io
import zipfile
from typing import Any

import pytest

from apps.accomplissement.models import FicheDeTest, PieceJustificative
from apps.accomplissement.services.pieces import deposer_piece
from apps.core.exceptions import RegleMetierError
from apps.core.fichiers import FichierRefuseError
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import pdf
from tests.core.test_antivirus import EICAR, faux_clamd

pytestmark = pytest.mark.django_db


def _docx(extra: dict[str, bytes] | None = None) -> bytes:
    tampon = io.BytesIO()
    entrees = {
        "[Content_Types].xml": b"<Types/>",
        "word/document.xml": b"<d/>" * 50,
        **(extra or {}),
    }
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, donnees in entrees.items():
            z.writestr(nom, donnees)
    return tampon.getvalue()


def _deposer(fiche: FicheDeTest, user: User, fichier: Any) -> PieceJustificative:
    return deposer_piece(fiche, fichier=fichier, libelle="Pièce", by=user)


def test_docx_avec_macro_refuse_et_rien_ecrit(
    fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    with pytest.raises(RegleMetierError, match="macros"):
        _deposer(
            fiche_auditeur, auditeur_mission, pdf("n.docx", _docx({"word/vbaProject.bin": b"x"}))
        )
    assert not PieceJustificative.all_objects.exists()


def test_docx_valide_accepte(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> None:
    piece = _deposer(fiche_auditeur, auditeur_mission, pdf("n.docx", _docx()))
    assert piece.type_mime.endswith("wordprocessingml.document")


def test_refus_de_contenu_reste_422_pour_les_pieces(
    fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        _deposer(fiche_auditeur, auditeur_mission, pdf("faux.png", b"%PDF-1.7\n" + b"x" * 50))
    assert not isinstance(exc.value, FichierRefuseError)
    assert exc.value.status_http == 422


def test_antivirus_eicar_refuse_400_sans_ecriture(
    settings: Any, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    settings.ANTIVIRUS_MOTEUR = "clamd"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    contenu = b"%PDF-1.7\n" + EICAR
    with faux_clamd(lambda c: b"stream: Eicar FOUND\x00") as (port, _):
        settings.ANTIVIRUS_CLAMD_PORT = port
        with pytest.raises(FichierRefuseError) as exc:
            _deposer(fiche_auditeur, auditeur_mission, pdf("e.pdf", contenu))
    assert exc.value.status_http == 400
    assert not PieceJustificative.all_objects.exists()


def test_antivirus_indisponible_503_sans_ecriture(
    settings: Any, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    settings.ANTIVIRUS_MOTEUR = "clamd"
    settings.ANTIVIRUS_CLAMD_HOTE = "127.0.0.1"
    settings.ANTIVIRUS_CLAMD_PORT = port
    with pytest.raises(RegleMetierError) as exc:
        _deposer(fiche_auditeur, auditeur_mission, pdf("a.pdf", b"%PDF-1.7\n" + b"x" * 50))
    assert exc.value.status_http == 503
    assert not PieceJustificative.all_objects.exists()


def test_quota_applique_au_depot_de_pieces(
    settings: Any, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1
    premiere = _deposer(
        fiche_auditeur, auditeur_mission, pdf("a.pdf", b"%PDF-1.7\n" + b"a" * 600_000)
    )
    assert premiere.pk
    with pytest.raises(RegleMetierError, match="quota"):
        _deposer(fiche_auditeur, auditeur_mission, pdf("b.pdf", b"%PDF-1.7\n" + b"b" * 600_000))
    assert PieceJustificative.all_objects.count() == 1
    # Le même fichier redéposé (réessai) n'est pas refusé par le quota : c'est un doublon.
    assert _deposer(
        fiche_auditeur, auditeur_mission, pdf("a.pdf", b"%PDF-1.7\n" + b"a" * 600_000)
    ).doublon
