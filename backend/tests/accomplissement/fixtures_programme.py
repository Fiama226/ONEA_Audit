"""Fixtures du programme de travail (étapes VIII à X), propres à la tâche 4."""

import pytest

from apps.accomplissement.models import ProgrammeDeTravail
from apps.missions.models import Mission, StatutEtape
from apps.users.models import User
from tests.accomplissement.factories import ProgrammeFactory, TestPrevuFactory
from tests.factories import ObjectifAuditFactory
from tests.missions.conftest import forcer_etapes

AVANT_VIII = {n: StatutEtape.VALIDEE for n in range(1, 8)}


@pytest.fixture
def mission_viii(mission_lancee: Mission) -> Mission:
    """Étapes I à VII validées, VIII en cours ; deux objectifs retenus, aucun programme."""
    for numero in (1, 2):
        ObjectifAuditFactory(mission=mission_lancee, numero=numero)
    forcer_etapes(mission_lancee, {**AVANT_VIII, 8: StatutEtape.EN_COURS})
    return mission_lancee


@pytest.fixture
def programme_viii(mission_viii: Mission) -> ProgrammeDeTravail:
    objectif = mission_viii.objectifs_audit.get(numero=1)
    programme: ProgrammeDeTravail = ProgrammeFactory(mission=mission_viii, objectif=objectif)
    return programme


@pytest.fixture
def mission_programme_complet(
    mission_lancee: Mission, chef: User, auditeur_mission: User
) -> Mission:
    """VIII et IX terminées, X en cours ; deux programmes complets (auditeur, charge)."""
    for numero in (1, 2):
        objectif = ObjectifAuditFactory(mission=mission_lancee, numero=numero)
        programme = ProgrammeFactory(mission=mission_lancee, objectif=objectif)
        TestPrevuFactory(
            mission=mission_lancee,
            programme=programme,
            auditeur=chef if numero == 1 else auditeur_mission,
            charge_prevue_jours=3,
        )
    forcer_etapes(
        mission_lancee,
        {
            **AVANT_VIII,
            8: StatutEtape.TERMINEE,
            9: StatutEtape.TERMINEE,
            10: StatutEtape.EN_COURS,
        },
    )
    return mission_lancee
