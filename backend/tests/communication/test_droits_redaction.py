from apps.communication.droits import (
    MODIFIER,
    SOUMETTRE,
    actions_rapport,
    contexte_rapport,
    peut_lire_rapport_interne,
)
from apps.communication.models import Rapport
from apps.missions.models import Mission, StatutEtape
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes


def _actions(rapport: Rapport, user: User) -> list[str]:
    mission = Mission.objects.get(pk=rapport.mission_id)
    return actions_rapport(rapport, user, contexte=contexte_rapport(mission, user))


def test_chef_modifie_et_soumet_quand_xvii_close(rapport_brouillon: Rapport, chef: User) -> None:
    assert _actions(rapport_brouillon, chef) == [MODIFIER]
    forcer_etapes(rapport_brouillon.mission, {17: StatutEtape.TERMINEE})
    assert _actions(rapport_brouillon, chef) == [MODIFIER, SOUMETTRE]


def test_auditeur_modifie_sans_soumettre(
    rapport_brouillon: Rapport, auditeur_mission: User
) -> None:
    forcer_etapes(rapport_brouillon.mission, {17: StatutEtape.TERMINEE})
    assert _actions(rapport_brouillon, auditeur_mission) == [MODIFIER]


def test_rai_modifie_mais_ne_soumet_pas(rapport_brouillon: Rapport) -> None:
    rai = make_user(Role.RAI)
    forcer_etapes(rapport_brouillon.mission, {17: StatutEtape.TERMINEE})
    assert _actions(rapport_brouillon, rai) == [MODIFIER]


def test_audite_et_etranger_sans_action(rapport_brouillon: Rapport, audite_affecte: User) -> None:
    assert _actions(rapport_brouillon, audite_affecte) == []
    assert _actions(rapport_brouillon, make_user(Role.AUDITEUR)) == []
    assert _actions(rapport_brouillon, make_user(Role.DG)) == []


def test_rapport_fige_sans_action(rapport_soumis: Rapport, chef: User) -> None:
    forcer_etapes(rapport_soumis.mission, {17: StatutEtape.TERMINEE})
    assert _actions(rapport_soumis, chef) == []


def test_mission_hors_communication_sans_action(rapport_brouillon: Rapport, chef: User) -> None:
    Mission.objects.filter(pk=rapport_brouillon.mission_id).update(statut="RAPPORT_DIFFUSE")
    assert _actions(rapport_brouillon, chef) == []


def test_lecture_interne(
    mission_en_communication: Mission,
    chef: User,
    auditeur_mission: User,
    audite_affecte: User,
) -> None:
    assert peut_lire_rapport_interne(make_user(Role.RAI), mission_en_communication)
    assert peut_lire_rapport_interne(chef, mission_en_communication)
    assert peut_lire_rapport_interne(auditeur_mission, mission_en_communication)
    assert not peut_lire_rapport_interne(audite_affecte, mission_en_communication)
    assert not peut_lire_rapport_interne(make_user(Role.DG), mission_en_communication)
    assert not peut_lire_rapport_interne(make_user(Role.ADMIN), mission_en_communication)
    assert not peut_lire_rapport_interne(make_user(Role.AUDITEUR), mission_en_communication)
