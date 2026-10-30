import pytest

from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.missions.services.droits import droits_mission
from apps.missions.services.etapes import actions_possibles
from apps.missions.services.missions import marquer_rapport_diffuse
from apps.users.models import User

from .conftest import forcer_etapes


@pytest.fixture
def mission_xviii(mission_lancee: Mission) -> Mission:
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission_lancee.refresh_from_db()
    forcer_etapes(mission_lancee, {n: StatutEtape.VALIDEE for n in range(1, 19)})
    return mission_lancee


def test_marquer_rapport_diffuse_nominal(mission_xviii: Mission, rai: User) -> None:
    mission = marquer_rapport_diffuse(mission_xviii, by=rai)
    assert mission.statut == StatutMission.RAPPORT_DIFFUSE
    mission_xviii.refresh_from_db()
    assert mission_xviii.statut == StatutMission.RAPPORT_DIFFUSE


def test_xviii_non_validee_422(mission_xviii: Mission, rai: User) -> None:
    forcer_etapes(mission_xviii, {18: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError, match="rapport ne peut être diffusé"):
        marquer_rapport_diffuse(mission_xviii, by=rai)


@pytest.mark.parametrize("statut", [StatutEtape.A_REVALIDER, StatutEtape.RENVOYEE])
def test_etape_rouverte_422(mission_xviii: Mission, rai: User, statut: str) -> None:
    forcer_etapes(mission_xviii, {16: statut})
    with pytest.raises(RegleMetierError, match="rapport ne peut être diffusé"):
        marquer_rapport_diffuse(mission_xviii, by=rai)


def test_hors_communication_refuse(mission_lancee: Mission, rai: User) -> None:
    with pytest.raises(RegleMetierError):
        marquer_rapport_diffuse(mission_lancee, by=rai)


def test_mission_rapport_diffuse_lecture_seule(
    mission_xviii: Mission, rai: User, chef: User
) -> None:
    marquer_rapport_diffuse(mission_xviii, by=rai)
    mission_xviii.refresh_from_db()
    for etape in mission_xviii.etapes.all():
        assert actions_possibles(etape, rai) == []
        assert actions_possibles(etape, chef) == []
    assert droits_mission(rai, mission_xviii).contribuer is False
