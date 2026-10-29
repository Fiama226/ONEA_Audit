"""Fixtures des tests de l'API d'analyse (équipe complète à un état donné des étapes)."""

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from apps.analyse.models import EvaluationConception
from apps.missions.models import EtapeMission, Mission, RisqueMission, StatutEtape
from apps.users.models import User
from tests.factories import LigneMARCFactory, RisqueMissionFactory
from tests.missions.conftest import equipe_complete, forcer_etapes  # noqa: F401

Equipe = tuple[Mission, dict[str, User]]
EquipeVI = tuple[Mission, dict[str, User], RisqueMission]

ETAPES_AVANT = {1: StatutEtape.TERMINEE, 2: StatutEtape.TERMINEE, 4: StatutEtape.TERMINEE}


@contextmanager
def travaux_ouverts(mission: Mission) -> Iterator[None]:
    """Ouvre les étapes III à VI le temps de créer des objets de test, puis les restitue."""
    numeros = (3, 4, 5, 6, 7)
    avant = dict(
        EtapeMission.objects.filter(mission=mission, numero__in=numeros).values_list(
            "numero", "statut"
        )
    )
    forcer_etapes(
        mission,
        {3: StatutEtape.EN_COURS, 4: StatutEtape.EN_COURS, 5: StatutEtape.EN_COURS,
         6: StatutEtape.EN_COURS, 7: StatutEtape.A_FAIRE},
    )  # fmt: skip
    try:
        yield
    finally:
        forcer_etapes(mission, avant)


@pytest.fixture
def equipe_en_iii(equipe_complete: Equipe) -> Equipe:  # noqa: F811
    """III et V en cours."""
    m, users = equipe_complete
    forcer_etapes(
        m,
        {**ETAPES_AVANT, 3: StatutEtape.EN_COURS, 5: StatutEtape.EN_COURS, 6: StatutEtape.A_FAIRE},
    )
    return m, users


@pytest.fixture
def equipe_en_vi(equipe_complete: Equipe) -> EquipeVI:  # noqa: F811
    """V terminée, VI en cours ; un risque de mission élevé."""
    m, users = equipe_complete
    with travaux_ouverts(m):
        risque = RisqueMissionFactory(
            mission=m, processus=m.processus.first(), probabilite=4, impact=5
        )
    forcer_etapes(
        m,
        {**ETAPES_AVANT, 3: StatutEtape.TERMINEE, 5: StatutEtape.TERMINEE, 6: StatutEtape.EN_COURS},
    )
    return m, users, risque


@pytest.fixture
def equipe_en_vii(equipe_complete: Equipe) -> EquipeVI:  # noqa: F811
    """VI validée, VII en cours ; une ligne MARC clé."""
    m, users = equipe_complete
    with travaux_ouverts(m):
        risque = RisqueMissionFactory(
            mission=m, processus=m.processus.first(), probabilite=4, impact=5
        )
        LigneMARCFactory(
            mission=m,
            risque=risque,
            controle_existant="Double signature.",
            evaluation=EvaluationConception.ADEQUATE,
            cle=True,
        )
    forcer_etapes(
        m,
        {
            **ETAPES_AVANT,
            3: StatutEtape.TERMINEE,
            5: StatutEtape.TERMINEE,
            6: StatutEtape.VALIDEE,
            7: StatutEtape.EN_COURS,
        },
    )
    return m, users, risque
