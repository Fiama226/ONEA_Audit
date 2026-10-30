from collections.abc import Iterator

import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from apps.missions.services import etapes as svc
from apps.missions.services.etapes import (
    ACTIONS_RESERVEES,
    actions_possibles,
    exiger_action_generique,
    reserver_actions,
    terminer_etape,
)
from apps.users.models import User

from .conftest import forcer_etapes


@pytest.fixture(autouse=True)
def _registre_restaure() -> Iterator[None]:
    avant = {n: set(a) for n, a in ACTIONS_RESERVEES.items()}
    yield
    ACTIONS_RESERVEES.clear()
    ACTIONS_RESERVEES.update(avant)


@pytest.fixture
def mission_xviii(mission_lancee: Mission) -> Mission:
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission_lancee.refresh_from_db()
    forcer_etapes(mission_lancee, {n: StatutEtape.VALIDEE for n in range(1, 18)})
    forcer_etapes(mission_lancee, {18: StatutEtape.EN_COURS})
    return mission_lancee


def test_actions_reservees_xviii(mission_xviii: Mission, chef: User) -> None:
    reserver_actions(18, "TERMINER", "VALIDER", "RENVOYER")
    etape = mission_xviii.etapes.get(numero=18)
    assert "TERMINER" not in actions_possibles(etape, chef)
    with pytest.raises(RegleMetierError, match="écran du rapport"):
        exiger_action_generique(etape, "TERMINER")
    exiger_action_generique(etape, "DEMARRER")
    # le service reste appelable : seul le contrôle des livrables peut le refuser
    with pytest.raises(RegleMetierError, match="Livrables manquants"):
        terminer_etape(etape, by=chef)


def test_actions_possibles_inclut_l_action_hors_reservation(
    mission_xviii: Mission, chef: User
) -> None:
    etape = mission_xviii.etapes.get(numero=18)
    assert "TERMINER" in actions_possibles(etape, chef)


def test_reserver_actions_idempotent() -> None:
    reserver_actions(18, "VALIDER")
    reserver_actions(18, "VALIDER", "RENVOYER")
    assert svc.ACTIONS_RESERVEES[18] == {"VALIDER", "RENVOYER"}


def test_route_generique_validate_xviii_422(
    api_client: APIClient, mission_xviii: Mission, chef: User, rai: User
) -> None:
    reserver_actions(18, "VALIDER")
    forcer_etapes(mission_xviii, {18: StatutEtape.TERMINEE})
    EtapeMission.objects.filter(mission=mission_xviii, numero=18).update(terminee_par=chef)
    etape = mission_xviii.etapes.get(numero=18)
    api_client.force_authenticate(rai)
    r = api_client.post(f"/api/v1/mission-steps/{etape.id}/validate/")
    assert r.status_code == 422
    assert "écran du rapport" in str(r.json())
    assert mission_xviii.etapes.get(numero=18).statut == StatutEtape.TERMINEE
