from collections.abc import Mapping

import pytest

from apps.missions.models import (
    AffectationMission,
    EtapeMission,
    Mission,
    RoleMission,
    StatutDeclaration,
    StatutEtape,
    StatutMission,
)
from apps.users.models import Role, User
from tests.factories import (
    AffectationFactory,
    DeclarationFactory,
    EtapeMissionFactory,
    MissionFactory,
    make_user,
)


def forcer_etapes(mission: Mission, statuts: Mapping[int, str]) -> None:
    """Force le statut d'étapes par `update` (la mission ne doit pas être figée)."""
    for numero, statut in statuts.items():
        EtapeMission.objects.filter(mission=mission, numero=numero).update(statut=statut)


def affecter(
    mission: Mission, utilisateur: User, role_mission: str, *, confirmee: bool = True
) -> AffectationMission:
    affectation = AffectationFactory(
        mission=mission, utilisateur=utilisateur, role_mission=role_mission
    )
    if role_mission != RoleMission.AUDITE:
        DeclarationFactory(
            affectation=affectation,
            statut=StatutDeclaration.CONFIRMEE if confirmee else StatutDeclaration.EN_ATTENTE,
        )
    return affectation


@pytest.fixture
def mission_lancee(db: None) -> Mission:
    mission = MissionFactory(
        statut=StatutMission.EN_PLANIFICATION,
        reference="DAI/2026/M01",
        annee=2026,
        numero=1,
    )
    for numero in range(1, 19):
        EtapeMissionFactory(
            mission=mission,
            numero=numero,
            statut=StatutEtape.EN_COURS if numero == 1 else StatutEtape.A_FAIRE,
        )
    return mission


@pytest.fixture
def chef(mission_lancee: Mission) -> User:
    user = make_user(Role.AUDITEUR)
    affecter(mission_lancee, user, RoleMission.CHEF_MISSION)
    return user


@pytest.fixture
def auditeur_mission(mission_lancee: Mission) -> User:
    user = make_user(Role.AUDITEUR)
    affecter(mission_lancee, user, RoleMission.AUDITEUR)
    return user


@pytest.fixture
def audite_affecte(mission_lancee: Mission) -> User:
    user = make_user(Role.AUDITE)
    affecter(mission_lancee, user, RoleMission.AUDITE)
    return user
