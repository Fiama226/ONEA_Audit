import hashlib
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.accomplissement.exceptions import FicheValideeError, FicheVerrouilleeError
from apps.accomplissement.models import FicheDeTest, PieceJustificative
from apps.accomplissement.services.fiches import valider_fiche
from apps.accomplissement.services.pieces import (
    deposer_piece,
    modifier_piece,
    retirer_piece,
)
from apps.accomplissement.stockage import StockageFichiers
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import PDF, ouvrir_xiii, pdf
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _fichiers(tmp_path: Path) -> list[Path]:
    return [f for f in (tmp_path / "preuves").rglob("*") if f.is_file()]


def test_depot_calcule_l_empreinte_et_ignore_le_nom(
    stockage_temporaire: StockageFichiers, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    contenu = b"%PDF-1.7\n" + b"x" * 1000
    p = deposer_piece(
        fiche_auditeur,
        fichier=SimpleUploadedFile("../../etc/passwd.pdf", contenu, content_type="text/html"),
        libelle="Facture 2026-031",
        by=auditeur_mission,
    )
    assert p.empreinte_sha256 == hashlib.sha256(contenu).hexdigest()
    assert ".." not in p.cle_stockage
    assert "passwd" not in p.cle_stockage
    assert p.nom_fichier_original == "passwd.pdf"
    assert p.type_mime == "application/pdf"  # jamais le content-type du client
    assert p.taille_octets == len(contenu)
    assert p.deposee_par == auditeur_mission
    assert p.numero == 1
    assert stockage_temporaire.existe(p.cle_stockage)


def test_depot_type_usurpe(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    with pytest.raises(RegleMetierError) as exc:
        deposer_piece(
            fiche_auditeur, fichier=pdf("faux.pdf", png), libelle="x", by=auditeur_mission
        )
    assert str(exc.value) == "Le contenu du fichier ne correspond pas à son extension."
    assert not PieceJustificative.all_objects.exists()


def test_depot_vide(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        deposer_piece(fiche_auditeur, fichier=pdf("v.pdf", b""), libelle="x", by=auditeur_mission)
    assert str(exc.value) == "Le fichier est vide."


@override_settings(PIECE_TAILLE_MAX_OCTETS=100)
def test_depot_trop_gros_refuse_sans_ecriture(
    tmp_path: Path, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        deposer_piece(
            fiche_auditeur,
            fichier=pdf("g.pdf", b"%PDF-1.7\n" + b"x" * 500),
            libelle="x",
            by=auditeur_mission,
        )
    assert str(exc.value) == "Le fichier dépasse la taille maximale de 50 Mo."
    assert not _fichiers(tmp_path)


def test_depot_taille_declaree_mensongere_refusee(
    tmp_path: Path, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    """Le contrôle porte aussi sur les octets réellement lus, pas seulement sur `size`."""
    f = pdf("g.pdf", b"%PDF-1.7\n" + b"x" * 500)
    f.size = 10  # taille annoncée mensongère
    with override_settings(PIECE_TAILLE_MAX_OCTETS=100), pytest.raises(RegleMetierError):
        deposer_piece(fiche_auditeur, fichier=f, libelle="x", by=auditeur_mission)
    assert not _fichiers(tmp_path)


def test_depot_libelle_obligatoire(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        deposer_piece(fiche_auditeur, fichier=pdf(), libelle="  ", by=auditeur_mission)
    assert str(exc.value) == "Le libellé est obligatoire."


def test_depot_idempotent_meme_octets(
    tmp_path: Path, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    premiere = deposer_piece(fiche_auditeur, fichier=pdf(), libelle="Facture", by=auditeur_mission)
    seconde = deposer_piece(fiche_auditeur, fichier=pdf(), libelle="Facture", by=auditeur_mission)
    assert seconde.pk == premiere.pk
    assert PieceJustificative.objects.count() == 1
    assert len(_fichiers(tmp_path)) == 1


def test_numeros_de_piece_consecutifs(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> None:
    a = deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    b = deposer_piece(
        fiche_auditeur, fichier=pdf("b.pdf", PDF + b"b"), libelle="B", by=auditeur_mission
    )
    assert (a.numero, b.numero) == (1, 2)


def test_depot_refuse_si_fiche_soumise(fiche_soumise: FicheDeTest, auditeur_mission: User) -> None:
    with pytest.raises(FicheVerrouilleeError):
        deposer_piece(
            fiche_soumise, fichier=pdf("c.pdf", PDF + b"c"), libelle="C", by=auditeur_mission
        )


def test_depot_refuse_si_fiche_validee(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, rai: User
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    valider_fiche(fiche_soumise, by=rai)
    with pytest.raises(FicheValideeError):
        deposer_piece(fiche_soumise, fichier=pdf("c.pdf", PDF + b"c"), libelle="C", by=rai)


def test_depot_refuse_si_xii_close(
    fiche_auditeur: FicheDeTest, mission_en_accomplissement: Mission, auditeur_mission: User
) -> None:
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    assert str(exc.value) == "Commencez l'étape XII pour saisir les fiches de test."


def test_depot_refuse_si_mission_suspendue(
    tmp_path: Path,
    fiche_auditeur: FicheDeTest,
    mission_en_accomplissement: Mission,
    auditeur_mission: User,
) -> None:
    Mission.objects.filter(pk=mission_en_accomplissement.pk).update(statut=StatutMission.SUSPENDUE)
    with pytest.raises(RegleMetierError):
        deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    assert not PieceJustificative.all_objects.exists()
    assert not _fichiers(tmp_path)


def test_depot_refuse_a_un_non_contributeur(
    fiche_auditeur: FicheDeTest, audite_affecte: User
) -> None:
    with pytest.raises(PermissionDenied):
        deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=audite_affecte)


def test_echec_base_apres_ecriture_consigne_l_orphelin_sans_effacer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    fiche_auditeur: FicheDeTest,
    auditeur_mission: User,
) -> None:
    def echec(*args: object, **kwargs: object) -> None:
        raise RuntimeError("base indisponible")

    monkeypatch.setattr("apps.accomplissement.services.pieces.enregistrer", echec)
    with pytest.raises(RuntimeError), caplog.at_level("ERROR"):
        deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    assert "orphelin" in caplog.text.lower()
    # Le fichier n'est jamais effacé : il reste signalé dans le journal.
    assert len(_fichiers(tmp_path)) == 1
    assert not PieceJustificative.all_objects.exists()


def test_modifier_piece_libelle_et_description(
    fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    p = deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    p = modifier_piece(p, by=auditeur_mission, libelle="Bon de commande 12", description="Visé")
    p.refresh_from_db()
    assert (p.libelle, p.description) == ("Bon de commande 12", "Visé")
    with pytest.raises(ValueError, match="non modifiables"):
        modifier_piece(p, by=auditeur_mission, empreinte_sha256="0" * 64)


def test_retirer_piece_suppression_logique_fichier_conserve(
    stockage_temporaire: StockageFichiers, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    p = deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    retirer_piece(p, by=auditeur_mission)
    assert not PieceJustificative.objects.filter(pk=p.pk).exists()
    assert PieceJustificative.all_objects.filter(pk=p.pk).exists()
    assert stockage_temporaire.existe(p.cle_stockage)


def test_fiche_validee_pieces_gelees(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, rai: User
) -> None:
    piece = fiche_soumise.pieces.get()
    ouvrir_xiii(mission_en_accomplissement)
    valider_fiche(fiche_soumise, by=rai)
    with pytest.raises(FicheValideeError):
        modifier_piece(piece, by=rai, libelle="autre")
    with pytest.raises(FicheValideeError):
        retirer_piece(piece, by=rai)


def test_piece_gelee_quand_fiche_soumise(
    fiche_soumise: FicheDeTest, auditeur_mission: User
) -> None:
    piece = fiche_soumise.pieces.get()
    with pytest.raises(FicheVerrouilleeError):
        retirer_piece(piece, by=auditeur_mission)
    with pytest.raises(FicheVerrouilleeError):
        modifier_piece(piece, by=auditeur_mission, libelle="x")


def test_xii_close_gele_les_pieces(
    fiche_auditeur: FicheDeTest, mission_en_accomplissement: Mission, auditeur_mission: User
) -> None:
    p = deposer_piece(fiche_auditeur, fichier=pdf(), libelle="A", by=auditeur_mission)
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        modifier_piece(p, by=auditeur_mission, libelle="B")
