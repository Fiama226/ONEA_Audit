import pytest

from apps.analyse.models import ForceFaiblesse, LigneMARC
from apps.analyse.services import marc
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, RisqueMission
from apps.missions.services.risques import retirer_risque_mission
from apps.users.models import User
from tests.factories import MissionFactory, ObjectifAuditFactory, RisqueMissionFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_ajouter_ligne_preremplit_depuis_le_risque_source(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    assert ligne.objectif_controle == "Garantir l'exactitude des paiements."
    assert ligne.controle_attendu == "Double validation des ordres de paiement."
    source = risque_eleve.risque_source
    assert source is not None
    assert ligne.objet_auditable_id == source.objet_auditable_id


def test_preremplissage_respecte_les_valeurs_fournies(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse, risque=risque_eleve, by=chef, objectif_controle="Mon objectif"
    )
    assert ligne.objectif_controle == "Mon objectif"


def test_risque_d_une_autre_mission_refuse(mission_en_analyse: Mission, chef: User) -> None:
    autre = RisqueMissionFactory(mission=MissionFactory())
    with pytest.raises(RegleMetierError, match="n'appartient pas à la mission") as e:
        marc.ajouter_ligne_marc(mission_en_analyse, risque=autre, by=chef)
    assert "risque" in e.value.errors


def test_evaluation_exige_controle_existant(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    with pytest.raises(RegleMetierError) as e:
        marc.ajouter_ligne_marc(
            mission_en_analyse, risque=risque_eleve, by=chef, evaluation="ADEQUATE"
        )
    assert "controle_existant" in e.value.errors


def test_cle_exige_controle_present(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    with pytest.raises(RegleMetierError) as e:
        marc.ajouter_ligne_marc(
            mission_en_analyse, risque=risque_eleve, by=chef, evaluation="ABSENTE", cle=True
        )
    assert "cle" in e.value.errors


def test_risque_non_modifiable(
    mission_en_analyse: Mission,
    risque_eleve: RisqueMission,
    risque_faible_nouveau: RisqueMission,
    chef: User,
) -> None:
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    with pytest.raises(RegleMetierError) as e:
        marc.modifier_ligne_marc(ligne, by=chef, risque=risque_faible_nouveau)
    assert "risque" in e.value.errors


def test_initialiser_marc_idempotent(mission_en_analyse: Mission, chef: User) -> None:
    creees = marc.initialiser_marc(mission_en_analyse, by=chef)
    assert len(creees) == 2
    assert marc.initialiser_marc(mission_en_analyse, by=chef) == []
    assert LigneMARC.objects.filter(mission=mission_en_analyse).count() == 2


def test_retrait_risque_analyse_refuse(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    EtapeMission.objects.filter(mission=mission_en_analyse, numero=4).update(statut="EN_COURS")
    with pytest.raises(RegleMetierError, match="analysé dans la matrice MARC"):
        retirer_risque_mission(risque_eleve, by=chef)
    marc.retirer_ligne_marc(ligne, by=chef)
    retirer_risque_mission(risque_eleve, by=chef)
    assert not RisqueMission.objects.filter(pk=risque_eleve.pk).exists()


def test_retrait_ligne_avec_objectif_refuse(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    ObjectifAuditFactory(mission=mission_en_analyse, ligne_marc=ligne)
    with pytest.raises(RegleMetierError, match="porte un objectif d'audit"):
        marc.retirer_ligne_marc(ligne, by=chef)


def test_retrait_ligne_retire_la_force_faiblesse_liee(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Contrôle",
        evaluation="ADEQUATE",
    )
    assert ForceFaiblesse.objects.filter(mission=mission_en_analyse).count() == 1
    marc.retirer_ligne_marc(ligne, by=chef)
    assert ForceFaiblesse.objects.filter(mission=mission_en_analyse).count() == 0
    assert not LigneMARC.objects.filter(pk=ligne.pk).exists()


def test_risques_non_couverts_moyen_eleve_seulement(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    # Le risque faible (1 x 2) n'est jamais exigé ; le risque élevé l'est tant qu'il est sans ligne.
    assert marc.risques_non_couverts(mission_en_analyse) == [risque_eleve.code_source]
    marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    assert marc.risques_non_couverts(mission_en_analyse) == []


def test_risques_non_couverts_libelle_des_nouveaux(mission_en_analyse: Mission) -> None:
    forcer_etapes(mission_en_analyse, {4: "EN_COURS"})
    RisqueMissionFactory(
        mission=mission_en_analyse,
        processus=mission_en_analyse.processus.first(),
        libelle="X" * 60,
        probabilite=3,
        impact=3,
    )
    assert f"Nouveau : {'X' * 40}" in marc.risques_non_couverts(mission_en_analyse)
