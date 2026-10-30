import pytest
from django.core.exceptions import PermissionDenied

from apps.analyse.models import ObjectifAudit
from apps.communication.exceptions import RapportFigeError
from apps.communication.models import EvenementRapport, Rapport, StatutRapport
from apps.communication.services.redaction import apercu, creer_rapport, modifier_rapport
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from apps.users.models import User
from tests.factories import ObjectifAuditFactory, RapportOrientationFactory


@pytest.fixture
def objectif_retenu(mission_lancee: Mission) -> ObjectifAudit:
    RapportOrientationFactory(mission=mission_lancee, contexte="Ctx", approche="Appr")
    objectif: ObjectifAudit = ObjectifAuditFactory(mission=mission_lancee, retenu=True, numero=1)
    return objectif


def test_creation_preremplie_depuis_orientation_et_mission(
    objectif_retenu: ObjectifAudit, mission_en_communication: Mission, chef: User
) -> None:
    objectif = objectif_retenu
    rapport = creer_rapport(mission_en_communication, by=chef)
    assert rapport.statut == StatutRapport.BROUILLON and rapport.numero_version == 1
    assert rapport.contexte == "Ctx"
    assert rapport.methodologie == "Appr"
    assert rapport.perimetre_texte == mission_en_communication.perimetre
    assert f"OA-01 : {objectif.libelle}" in rapport.objectifs_texte
    assert rapport.synthese == "" and rapport.appreciation_globale == ""
    assert EvenementRapport.objects.filter(rapport=rapport, type="CREE").exists()


def test_creation_sans_orientation(mission_en_communication: Mission, chef: User) -> None:
    rapport = creer_rapport(mission_en_communication, by=chef)
    assert rapport.contexte == "" and rapport.methodologie == ""


def test_rapport_unique(mission_en_communication: Mission, chef: User) -> None:
    creer_rapport(mission_en_communication, by=chef)
    with pytest.raises(RegleMetierError, match="Un rapport existe déjà pour cette mission."):
        creer_rapport(mission_en_communication, by=chef)


def test_creation_hors_communication(mission_lancee: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError, match="phase de communication"):
        creer_rapport(mission_lancee, by=chef)


def test_creation_refusee_a_l_audite(
    mission_en_communication: Mission, audite_affecte: User
) -> None:
    with pytest.raises(PermissionDenied):
        creer_rapport(mission_en_communication, by=audite_affecte)


def test_modification_des_sections(rapport_brouillon: Rapport, auditeur_mission: User) -> None:
    modifie = modifier_rapport(
        rapport_brouillon,
        by=auditeur_mission,
        synthese="Nouvelle synthèse",
        appreciation_globale="INSUFFISANTE",
    )
    modifie.refresh_from_db()
    assert modifie.synthese == "Nouvelle synthèse"
    assert modifie.appreciation_globale == "INSUFFISANTE"
    assert modifie.updated_by == auditeur_mission


def test_modification_valeur_invalide(rapport_brouillon: Rapport, chef: User) -> None:
    with pytest.raises(RegleMetierError):
        modifier_rapport(rapport_brouillon, by=chef, appreciation_globale="EXCELLENTE")


def test_modification_champ_non_modifiable(rapport_brouillon: Rapport, chef: User) -> None:
    with pytest.raises(ValueError, match="statut"):
        modifier_rapport(rapport_brouillon, by=chef, statut="VALIDE")


def test_modification_refusee_apres_soumission(rapport_soumis: Rapport, chef: User) -> None:
    with pytest.raises(RapportFigeError):
        modifier_rapport(rapport_soumis, by=chef, synthese="Trop tard")
    rapport_soumis.refresh_from_db()
    assert rapport_soumis.synthese == "Synthèse"


def test_modification_refusee_a_l_audite(rapport_brouillon: Rapport, audite_affecte: User) -> None:
    with pytest.raises(PermissionDenied):
        modifier_rapport(rapport_brouillon, by=audite_affecte, synthese="x")


def test_modification_d_une_copie_perimee_ne_ressuscite_rien(
    rapport_brouillon: Rapport, chef: User
) -> None:
    perimee = Rapport.objects.get(pk=rapport_brouillon.pk)
    modifier_rapport(rapport_brouillon, by=chef, conclusion="Première")
    modifier_rapport(perimee, by=chef, synthese="Seconde")
    en_base = Rapport.objects.get(pk=rapport_brouillon.pk)
    assert (en_base.conclusion, en_base.synthese) == ("Première", "Seconde")


def test_apercu_est_l_assemblage_complet(rapport_redige: Rapport) -> None:
    donnees = apercu(rapport_redige)
    assert donnees["sections"]["synthese"] == "Synthèse"
    assert rapport_redige.instantane_soumis is None
