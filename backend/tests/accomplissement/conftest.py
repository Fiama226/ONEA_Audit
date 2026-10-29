from pathlib import Path
from typing import Any

import pytest

from apps.accomplissement.models import FicheDeTest
from apps.accomplissement.stockage import StockageFichiers, stockage_preuves
from apps.missions.models import Mission, StatutEtape
from tests.accomplissement.factories import (
    FicheFactory,
    ProgrammeFactory,
    TestPrevuFactory,
)
from tests.factories import ObjectifAuditFactory
from tests.missions.conftest import (  # noqa: F401
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)


@pytest.fixture(autouse=True)
def stockage_temporaire(settings: Any, tmp_path: Path) -> StockageFichiers:
    """Redirige le stockage des preuves vers un dossier temporaire."""
    settings.STOCKAGE_PREUVES = {
        "BACKEND": "tests.accomplissement.fakes.StockageDisqueTemporaire",
        "OPTIONS": {"RACINE": str(tmp_path / "preuves")},
    }
    return stockage_preuves()


@pytest.fixture
def mission_en_accomplissement(mission_lancee: Mission) -> Mission:  # noqa: F811
    """VIII à XI closes (X validée), XII en cours ; deux objectifs, deux programmes, deux tests."""
    for numero in (1, 2):
        objectif = ObjectifAuditFactory(mission=mission_lancee, numero=numero)
        programme = ProgrammeFactory(mission=mission_lancee, objectif=objectif)
        TestPrevuFactory(mission=mission_lancee, programme=programme)
    forcer_etapes(
        mission_lancee,
        {
            **{n: StatutEtape.VALIDEE for n in range(1, 8)},
            8: StatutEtape.TERMINEE,
            9: StatutEtape.TERMINEE,
            10: StatutEtape.VALIDEE,
            11: StatutEtape.TERMINEE,
            12: StatutEtape.EN_COURS,
            13: StatutEtape.A_FAIRE,
        },
    )
    return mission_lancee


@pytest.fixture
def fiche_brouillon(mission_en_accomplissement: Mission) -> FicheDeTest:
    test = mission_en_accomplissement.tests_prevus.order_by("numero").first()
    fiche: FicheDeTest = FicheFactory(mission=mission_en_accomplissement, test=test)
    return fiche


# Fixtures de la tâche 5 (fiches, pièces, intégrité).
from tests.accomplissement.fixtures_fiches import (  # noqa: E402, F401
    fiche_auditeur,
    fiche_complete,
    fiche_soumise,
    rai,
    superviseur,
    superviseur_non_leve,
    test_prevu,
)
from tests.accomplissement.fixtures_programme import (  # noqa: E402, F401
    mission_programme_complet,
    mission_viii,
    programme_viii,
)
