"""Équipe et chaîne du rapport pour les tests de l'API de la communication (lot 7, T11)."""

from dataclasses import dataclass

import pytest
from django.utils import timezone

from apps.constats.models import Constat
from apps.missions.models import Mission
from apps.users.models import Role, User
from tests.factories import make_user

RAPPORTS = "/api/v1/reports/"
PROVISOIRES = "/api/v1/draft-reports/"
REPONSES = "/api/v1/draft-report-responses/"
DESTINATAIRES = "/api/v1/report-recipients/"

ROLES = (
    "rai",
    "chef",
    "auditeur",
    "audite",
    "non_affecte",
    "audite_non_affecte",
    "admin",
    "dg",
)


@dataclass
class EquipeRapport:
    mission: Mission
    users: dict[str, User]


@pytest.fixture
def equipe(
    constat_valide: Constat,  # noqa: ARG001 - créé avant la clôture de l'étape XIV
    mission_en_communication: Mission,
    rai: User,
    chef: User,
    auditeur_mission: User,
    audite_affecte: User,
    admin: User,
    dg: User,
) -> EquipeRapport:
    """Intervenants, audité affecté, DG, ADMIN, et deux utilisateurs hors de la mission."""
    Mission.objects.filter(pk=mission_en_communication.pk).update(
        ordre_mission_emis_le=timezone.now()
    )
    mission_en_communication.refresh_from_db()
    users = {
        "rai": rai,
        "chef": chef,
        "auditeur": auditeur_mission,
        "audite": audite_affecte,
        "non_affecte": make_user(Role.AUDITEUR),
        "audite_non_affecte": make_user(Role.AUDITE),
        "admin": admin,
        "dg": dg,
    }
    return EquipeRapport(mission_en_communication, users)
