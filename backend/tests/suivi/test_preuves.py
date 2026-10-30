import hashlib
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404

from apps.core.consultations import Consultation
from apps.core.exceptions import RegleMetierError
from apps.core.fichiers import FichierRefuseError
from apps.documents.integrite import IntegriteError
from apps.missions.models import Mission
from apps.suivi import droits
from apps.suivi.models import (
    EvenementSuivi,
    PreuveImmuableError,
    PreuveMiseEnOeuvre,
    StatutSuivi,
    SuiviAction,
    TypeEvenementSuivi,
)
from apps.suivi.services.preuves import (
    deposer_preuve,
    modifier_preuve,
    ouvrir_preuve_verifiee,
    retirer_preuve,
)
from apps.users.models import User
from config.documents_settings import configuration_stockage

PDF = b"%PDF-1.7\n" + b"x" * 500


@pytest.fixture(autouse=True)
def dossier_documents(settings: Any, tmp_path: Path) -> Path:
    racine = tmp_path / "documents"
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(racine)}
        ),
    }
    return racine


def suivi_de(user: User) -> SuiviAction:
    suivi: SuiviAction = SuiviAction.objects.filter(responsable=user).first()
    return suivi


def deposer(suivi: SuiviAction, by: User, contenu: bytes = PDF, nom: str = "pv.pdf") -> Any:
    return deposer_preuve(
        suivi, fichier=SimpleUploadedFile(nom, contenu), libelle="PV de mise en place", by=by
    )


def test_depot_ignore_le_nom_et_calcule_l_empreinte(
    mission_en_suivi: Mission, responsable: User, dossier_documents: Path
) -> None:
    s = suivi_de(responsable)
    p = deposer_preuve(
        s,
        fichier=SimpleUploadedFile("../../etc/passwd.pdf", PDF),
        libelle="PV de mise en place",
        by=responsable,
    )
    assert (
        p.cle_stockage.startswith(f"suivi/preuves/{s.mission_id}/") and ".." not in p.cle_stockage
    )
    assert "passwd" not in p.cle_stockage
    assert p.empreinte_sha256 == hashlib.sha256(PDF).hexdigest()
    assert p.nom_fichier_original == "passwd.pdf"
    assert p.type_mime == "application/pdf"
    assert p.numero == 1
    assert (dossier_documents / p.cle_stockage).read_bytes() == PDF
    evenement = EvenementSuivi.objects.get(suivi=s, type=TypeEvenementSuivi.PREUVE_DEPOSEE)
    assert evenement.par == responsable and evenement.pour_compte_de is None


def test_numeros_croissants_et_jamais_reattribues(
    mission_en_suivi: Mission, responsable: User
) -> None:
    s = suivi_de(responsable)
    p1 = deposer(s, responsable)
    p2 = deposer(s, responsable, PDF + b"2")
    retirer_preuve(p2, by=responsable)
    p3 = deposer(s, responsable, PDF + b"3")
    assert (p1.numero, p2.numero, p3.numero) == (1, 2, 3)


@pytest.mark.parametrize(
    ("nom", "contenu"),
    [
        ("faux.pdf", b"MZ\x90\x00" + b"x" * 200),
        ("image.pdf", b"\x89PNG\r\n\x1a\n" + b"x" * 200),
        ("script.exe", b"MZ\x90\x00" + b"x" * 200),
        ("macro.xlsm", b"PK\x03\x04" + b"x" * 200),
        ("sans_extension", PDF),
    ],
)
def test_depot_type_usurpe_refuse(
    mission_en_suivi: Mission, responsable: User, nom: str, contenu: bytes
) -> None:
    with pytest.raises(FichierRefuseError):
        deposer(suivi_de(responsable), responsable, contenu, nom)
    assert not PreuveMiseEnOeuvre.all_objects.exists()


def test_content_type_annonce_ignore(mission_en_suivi: Mission, responsable: User) -> None:
    fichier = SimpleUploadedFile(
        "faux.pdf", b"MZ\x90\x00" + b"x" * 200, content_type="application/pdf"
    )
    with pytest.raises(FichierRefuseError):
        deposer_preuve(suivi_de(responsable), fichier=fichier, libelle="x", by=responsable)


def test_depot_taille(mission_en_suivi: Mission, responsable: User, settings: Any) -> None:
    s = suivi_de(responsable)
    with pytest.raises(FichierRefuseError):
        deposer(s, responsable, b"")
    settings.PIECE_TAILLE_MAX_OCTETS = 100
    with pytest.raises(FichierRefuseError):
        deposer(s, responsable, b"%PDF-" + b"x" * 100)  # 105 octets > maximum
    assert not PreuveMiseEnOeuvre.all_objects.exists()


def test_depot_quota_atteint_sans_ecriture(
    mission_en_suivi: Mission, responsable: User, settings: Any, dossier_documents: Path
) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1
    with pytest.raises(RegleMetierError):
        deposer(suivi_de(responsable), responsable, b"%PDF-" + b"x" * (2 * 1024 * 1024))
    assert not PreuveMiseEnOeuvre.all_objects.exists()
    assert not list(dossier_documents.rglob("*.*")) and not [
        f for f in dossier_documents.rglob("*") if f.is_file()
    ]


def test_quota_compte_les_preuves(
    mission_en_suivi: Mission, responsable: User, settings: Any
) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1
    s = suivi_de(responsable)
    deposer(s, responsable, b"%PDF-" + b"x" * (700 * 1024))
    with pytest.raises(RegleMetierError):
        deposer(s, responsable, b"%PDF-" + b"y" * (700 * 1024))


def test_libelle_obligatoire(mission_en_suivi: Mission, responsable: User) -> None:
    with pytest.raises(RegleMetierError):
        deposer_preuve(
            suivi_de(responsable),
            fichier=SimpleUploadedFile("a.pdf", PDF),
            libelle=" ",
            by=responsable,
        )


def test_depot_reserve_au_responsable_ou_rai(
    mission_en_suivi: Mission, responsable: User, autre_audite: User, autre_auditeur: User, dg: User
) -> None:
    s = suivi_de(responsable)
    for intrus in (autre_audite, autre_auditeur, dg):
        with pytest.raises(PermissionDenied):
            deposer(s, intrus)
    assert not PreuveMiseEnOeuvre.all_objects.exists()


def test_depot_par_le_rai_exige_un_commentaire(
    mission_en_suivi: Mission, responsable: User, rai: User
) -> None:
    s = suivi_de(responsable)
    with pytest.raises(RegleMetierError):
        deposer(s, rai)
    p = deposer_preuve(
        s,
        fichier=SimpleUploadedFile("a.pdf", PDF),
        libelle="PV",
        by=rai,
        commentaire="Reçu par courrier",
    )
    evenement = EvenementSuivi.objects.get(suivi=s, type=TypeEvenementSuivi.PREUVE_DEPOSEE)
    assert evenement.pour_compte_de == responsable
    assert evenement.texte.startswith("Saisi par le RAI pour le compte de ")
    assert "Reçu par courrier" in evenement.texte
    assert p.deposee_par == rai


def test_preuve_gelee_apres_declaration(mission_en_suivi: Mission, responsable: User) -> None:
    s = suivi_de(responsable)
    p = deposer(s, responsable)
    SuiviAction.objects.filter(pk=s.pk).update(statut=StatutSuivi.REALISEE)
    s.refresh_from_db()
    with pytest.raises(RegleMetierError):
        deposer(s, responsable, PDF + b"2")
    with pytest.raises(RegleMetierError):
        retirer_preuve(p, by=responsable)
    with pytest.raises(RegleMetierError):
        modifier_preuve(p, by=responsable, libelle="autre")
    SuiviAction.objects.filter(pk=s.pk).update(statut=StatutSuivi.EN_COURS)  # après rejet
    s.refresh_from_db()
    deposer(s, responsable, PDF + b"2")
    retirer_preuve(p, by=responsable)


def test_mission_figee_refuse_le_depot(mission_en_suivi: Mission, responsable: User) -> None:
    from apps.missions.exceptions import MissionFigeeError
    from apps.missions.models import StatutMission

    Mission.objects.filter(pk=mission_en_suivi.pk).update(statut=StatutMission.CLOTUREE)
    with pytest.raises(MissionFigeeError):
        deposer(suivi_de(responsable), responsable)


def test_retrait_logique_conserve_le_fichier(
    mission_en_suivi: Mission, responsable: User, dossier_documents: Path
) -> None:
    s = suivi_de(responsable)
    p = deposer(s, responsable)
    retirer_preuve(p, by=responsable)
    assert not PreuveMiseEnOeuvre.objects.filter(pk=p.pk).exists()
    ligne = PreuveMiseEnOeuvre.all_objects.get(pk=p.pk)
    assert ligne.deleted_at is not None
    assert (dossier_documents / p.cle_stockage).is_file()
    assert EvenementSuivi.objects.filter(suivi=s, type=TypeEvenementSuivi.PREUVE_RETIREE).exists()


def test_modifier_libelle_seulement_et_champs_fichier_immuables(
    mission_en_suivi: Mission, responsable: User
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    p = modifier_preuve(p, by=responsable, libelle="Nouveau libellé", description="d")
    assert (p.libelle, p.description) == ("Nouveau libellé", "d")
    p.empreinte_sha256 = "0" * 64
    with pytest.raises(PreuveImmuableError):
        p.save()
    with pytest.raises(PreuveImmuableError):
        PreuveMiseEnOeuvre.objects.filter(pk=p.pk).update(empreinte_sha256="1" * 64)


def test_telechargement_rend_le_contenu_et_journalise(
    mission_en_suivi: Mission, responsable: User, rai: User, auditeur_mission: User
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    for lecteur in (responsable, rai, auditeur_mission):
        assert ouvrir_preuve_verifiee(p, by=lecteur, adresse_ip="10.0.0.5") == PDF
    journal = Consultation.objects.filter(object_id=p.pk, action="TELECHARGEMENT")
    assert journal.count() == 3
    assert {c.par_id for c in journal} == {responsable.pk, rai.pk, auditeur_mission.pk}
    assert journal.first().adresse_ip == "10.0.0.5"


def test_telechargement_detecte_alteration(
    mission_en_suivi: Mission, responsable: User, dossier_documents: Path
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    chemin = dossier_documents / p.cle_stockage
    chemin.write_bytes(PDF[:-1] + b"Y")  # même taille, contenu altéré
    with pytest.raises(IntegriteError):
        ouvrir_preuve_verifiee(p, by=responsable, adresse_ip=None)
    chemin.write_bytes(PDF + b"z")  # taille différente
    with pytest.raises(IntegriteError):
        ouvrir_preuve_verifiee(p, by=responsable, adresse_ip=None)
    assert not Consultation.objects.filter(object_id=p.pk).exists()


def test_telechargement_fichier_absent(
    mission_en_suivi: Mission, responsable: User, dossier_documents: Path
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    (dossier_documents / p.cle_stockage).unlink()
    with pytest.raises(IntegriteError):
        ouvrir_preuve_verifiee(p, by=responsable, adresse_ip=None)


def test_dg_ne_telecharge_pas(
    mission_en_suivi: Mission, responsable: User, dg: User, admin: User
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    for intrus in (dg, admin):
        assert droits.peut_telecharger_preuve(intrus, p) is False
        with pytest.raises(PermissionDenied):
            ouvrir_preuve_verifiee(p, by=intrus, adresse_ip=None)
    assert not Consultation.objects.exists()


def test_non_affecte_ne_telecharge_pas(
    mission_en_suivi: Mission, responsable: User, autre_audite: User, autre_auditeur: User
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    for intrus in (autre_audite, autre_auditeur):
        with pytest.raises(PermissionDenied):
            ouvrir_preuve_verifiee(p, by=intrus, adresse_ip=None)


def test_preuve_retiree_introuvable(
    mission_en_suivi: Mission, responsable: User, rai: User
) -> None:
    p = deposer(suivi_de(responsable), responsable)
    retirer_preuve(p, by=responsable)
    p = PreuveMiseEnOeuvre.all_objects.get(pk=p.pk)
    with pytest.raises(Http404):
        ouvrir_preuve_verifiee(p, by=rai, adresse_ip=None)
