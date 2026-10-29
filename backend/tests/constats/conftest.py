import pytest

from apps.missions.models import Mission, StatutEtape
from tests.accomplissement.conftest import stockage_temporaire  # noqa: F401
from tests.constats.factories import fiche_anomalie
from tests.missions.conftest import (  # noqa: F401
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)


@pytest.fixture
def mission_en_xiv(mission_lancee: Mission) -> Mission:  # noqa: F811
    """Fiche ANOMALIE validée existante ; I à XIII validées, XIV en cours, XV à faire."""
    fiche_anomalie(mission_lancee)
    forcer_etapes(
        mission_lancee,
        {
            **{n: StatutEtape.VALIDEE for n in range(1, 14)},
            14: StatutEtape.EN_COURS,
            15: StatutEtape.A_FAIRE,
        },
    )
    return mission_lancee
