from collections.abc import Mapping

import pytest
from django.utils import timezone

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
    ProcessusFactory,
    make_user,
)


def forcer_etapes(mission: Mission, statuts: Mapping[int, str]) -> None:
    """Force le statut d'étapes par `update` (la mission ne doit pas être figée)."""
    for numero, statut in statuts.items():
        EtapeMission.objects.filter(mission=mission, numero=numero).update(statut=statut)


def affecter(
    mission: Mission,
    utilisateur: User,
    role_mission: str,
    *,
    confirmee: bool = True,
    responsable_entite: bool | None = None,
) -> AffectationMission:
    """`responsable_entite` : par défaut vrai pour un audité (comportement historique des tests)."""
    if responsable_entite is None:
        responsable_entite = role_mission == RoleMission.AUDITE
    affectation = AffectationFactory(
        mission=mission,
        utilisateur=utilisateur,
        role_mission=role_mission,
        responsable_entite=responsable_entite,
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


@pytest.fixture
def equipe_complete(db: None) -> tuple[Mission, dict[str, User]]:
    """Mission EN_PLANIFICATION, ordre émis, étape VI terminée par le chef, tous les profils."""
    mission = MissionFactory(
        statut=StatutMission.EN_PLANIFICATION,
        reference="DAI/2026/M01",
        annee=2026,
        numero=1,
        objectifs="Évaluer le dispositif.",
        perimetre="Direction régionale du Centre.",
    )
    mission.processus.add(ProcessusFactory())
    for numero in range(1, 19):
        EtapeMissionFactory(mission=mission, numero=numero)
    users = {
        "rai": make_user(Role.RAI),
        "chef": make_user(Role.AUDITEUR),
        "superviseur": make_user(Role.AUDITEUR),
        "auditeur_confirme": make_user(Role.AUDITEUR),
        "auditeur_non_confirme": make_user(Role.AUDITEUR),
        "auditeur_non_affecte": make_user(Role.AUDITEUR),
        "audite_affecte": make_user(Role.AUDITE),
        "admin": make_user(Role.ADMIN),
        "dg": make_user(Role.DG),
    }
    affecter(mission, users["chef"], RoleMission.CHEF_MISSION)
    affecter(mission, users["superviseur"], RoleMission.SUPERVISEUR)
    affecter(mission, users["auditeur_confirme"], RoleMission.AUDITEUR)
    affecter(mission, users["auditeur_non_confirme"], RoleMission.AUDITEUR, confirmee=False)
    affecter(mission, users["audite_affecte"], RoleMission.AUDITE)
    forcer_etapes(mission, {1: StatutEtape.TERMINEE, 6: StatutEtape.TERMINEE})
    EtapeMission.objects.filter(mission=mission, numero=6).update(terminee_par=users["chef"])
    Mission.objects.filter(pk=mission.pk).update(ordre_mission_emis_le=timezone.now())
    mission.refresh_from_db()
    return mission, users
