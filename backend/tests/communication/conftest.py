import pytest

from apps.communication.models import (
    Rapport,
    RapportProvisoire,
    StatutRapport,
)
from apps.constats.models import Constat
from apps.missions.models import Mission, StatutEtape, StatutMission
from tests.communication.factories import RapportFactory, RapportProvisoireFactory
from tests.constats.factories import ConstatFactory
from tests.missions.conftest import (  # noqa: F401
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)


@pytest.fixture
def constat(mission_lancee: Mission) -> Constat:  # noqa: F811
    """Constat créé tant que XIV est ouverte (avant `mission_en_communication`)."""
    constat: Constat = ConstatFactory(mission=mission_lancee)
    return constat


@pytest.fixture
def mission_en_communication(mission_lancee: Mission, constat: Constat) -> Mission:  # noqa: F811
    """I à XIV validées, XV à XVIII en cours, mission EN_COMMUNICATION."""
    forcer_etapes(
        mission_lancee,
        {
            **{n: StatutEtape.VALIDEE for n in range(1, 15)},
            **{n: StatutEtape.EN_COURS for n in range(15, 19)},
        },
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission_lancee.refresh_from_db()
    return mission_lancee


@pytest.fixture
def rapport_brouillon(mission_en_communication: Mission) -> Rapport:
    rapport: Rapport = RapportFactory(mission=mission_en_communication)
    return rapport


@pytest.fixture
def rapport_soumis(mission_en_communication: Mission) -> Rapport:
    """Rapport SOUMIS avec instantané factice cohérent (empreinte = SHA-256 de l'instantané)."""
    rapport: Rapport = RapportFactory(mission=mission_en_communication, fige=True)
    assert rapport.statut == StatutRapport.SOUMIS
    return rapport


@pytest.fixture
def provisoire_transmis(rapport_brouillon: Rapport) -> RapportProvisoire:
    provisoire: RapportProvisoire = RapportProvisoireFactory(rapport=rapport_brouillon)
    return provisoire
