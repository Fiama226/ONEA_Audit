import pytest
from django.utils import timezone

from apps.communication.models import Rapport, StatutRapport
from apps.constats.models import Recommandation
from apps.missions.models import Mission, RoleMission, StatutEtape, StatutMission
from apps.recommandations.models import Action
from apps.users.models import Role, User
from tests.communication.factories import RapportFactory, creer_diffusion
from tests.constats.factories import ConstatFactory, RecommandationFactory
from tests.factories import make_user
from tests.missions.conftest import (  # noqa: F401
    affecter,
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)
from tests.recommandations.factories import AcceptationFactory, ActionFactory
from tests.suivi.factories import SuiviActionFactory


@pytest.fixture
def responsable(mission_lancee: Mission) -> User:  # noqa: F811
    user = make_user(Role.AUDITE)
    affecter(mission_lancee, user, RoleMission.AUDITE)
    return user


@pytest.fixture
def autre_audite(db: None) -> User:
    return make_user(Role.AUDITE)


@pytest.fixture
def autre_auditeur(db: None) -> User:
    return make_user(Role.AUDITEUR)


@pytest.fixture
def mission_en_suivi(
    mission_lancee: Mission,  # noqa: F811
    chef: User,  # noqa: F811
    auditeur_mission: User,  # noqa: F811
    responsable: User,
) -> Mission:
    """Rapport diffusé : deux constats, trois recommandations (une à risque accepté), trois suivis.

    La recommandation A porte deux actions, B une seule ; C est acceptée, sans action.
    """
    mission = mission_lancee
    constat_1 = ConstatFactory(mission=mission)
    constat_2 = ConstatFactory(mission=mission)
    reco_a: Recommandation = constat_1.recommandations.first()
    reco_b: Recommandation = constat_2.recommandations.first()
    reco_c = RecommandationFactory(constat=constat_1, ordre=2)
    forcer_etapes(
        mission,
        {
            **{n: StatutEtape.VALIDEE for n in range(1, 15)},
            **{n: StatutEtape.EN_COURS for n in range(15, 19)},
        },
    )
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission.refresh_from_db()
    for reco in (reco_a, reco_a, reco_b):
        ActionFactory(recommandation=reco, responsable=responsable)
    AcceptationFactory(recommandation=reco_c)
    rapport: Rapport = RapportFactory(mission=mission, fige=True, statut=StatutRapport.DIFFUSE)
    creer_diffusion(rapport)
    forcer_etapes(mission, {n: StatutEtape.VALIDEE for n in range(15, 19)})
    Mission.objects.filter(pk=mission.pk).update(
        statut=StatutMission.RAPPORT_DIFFUSE, ordre_mission_emis_le=timezone.now()
    )
    mission.refresh_from_db()
    for action in Action.objects.filter(mission=mission):
        SuiviActionFactory(action=action)
    return mission
