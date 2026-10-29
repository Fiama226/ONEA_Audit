import pytest
from django.utils import timezone

from apps.missions.models import Mission, RisqueMission, StatutEtape
from apps.referentiel.models import CartographieVersion, StatutCartographie
from apps.users.models import Role
from tests.factories import (
    CartographieVersionFactory,
    ProcessusFactory,
    RisqueFactory,
    RisqueMissionFactory,
    make_user,
)
from tests.missions.conftest import (  # noqa: F401
    audite_affecte,
    auditeur_mission,
    chef,
    equipe_complete,
    forcer_etapes,
    mission_lancee,
)


@pytest.fixture
def mission_en_analyse(mission_lancee: Mission) -> Mission:  # noqa: F811
    """I, II, IV terminées ; III et V en cours ; deux risques de mission."""
    processus = ProcessusFactory()
    mission_lancee.processus.add(processus)
    version = CartographieVersionFactory()
    source = RisqueFactory(
        version=version,
        processus=processus,
        probabilite=4,
        impact=5,
        objectif_controle="Garantir l'exactitude des paiements.",
        dispositif_controle="Double validation des ordres de paiement.",
    )
    CartographieVersion._base_manager.filter(pk=version.pk).update(
        statut=StatutCartographie.VALIDEE,
        validee_le=timezone.now(),
        validee_par=make_user(Role.RAI),
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(cartographie=version)
    mission_lancee.refresh_from_db()
    RisqueMissionFactory(
        mission=mission_lancee,
        processus=processus,
        risque_source=source,
        code_source=source.code,
        libelle=source.libelle,
        probabilite=4,
        impact=5,
    )
    RisqueMissionFactory(mission=mission_lancee, processus=processus, probabilite=1, impact=2)
    forcer_etapes(
        mission_lancee,
        {
            1: StatutEtape.TERMINEE,
            2: StatutEtape.TERMINEE,
            4: StatutEtape.TERMINEE,
            3: StatutEtape.EN_COURS,
            5: StatutEtape.EN_COURS,
        },
    )
    return mission_lancee


@pytest.fixture
def risque_eleve(mission_en_analyse: Mission) -> RisqueMission:
    return mission_en_analyse.risques.get(risque_source__isnull=False)


@pytest.fixture
def risque_faible_nouveau(mission_en_analyse: Mission) -> RisqueMission:
    return mission_en_analyse.risques.get(risque_source__isnull=True)
