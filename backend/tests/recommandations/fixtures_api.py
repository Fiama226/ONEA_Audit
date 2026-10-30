"""Équipe et plan d'actions pour les tests de l'API du plan d'actions (T10)."""

from dataclasses import dataclass

import pytest
from django.utils import timezone

from apps.constats.models import Recommandation
from apps.missions.models import Mission, RoleMission
from apps.recommandations.models import Action
from apps.recommandations.services.actions import creer_action
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import affecter

ACTIONS = "/api/v1/corrective-actions/"
ACCEPTATIONS = "/api/v1/risk-acceptances/"
ENGAGEMENTS = "/api/v1/action-plan-commitments/"
SYNTHESE = "/api/v1/action-plans/summary/"


@dataclass
class EquipePlan:
    mission: Mission
    recommandations: list[Recommandation]  # a1, a2 (entité A), b1 (entité B)
    action_a: Action  # sur a1, sans responsable, proposée par le chef
    action_resp: Action  # sur a2, responsable : audité A
    users: dict[str, User]


@pytest.fixture
def equipe_plan(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    chef: User,
    auditeur_mission: User,
    audite_entite_a: User,
    audite_entite_b: User,
) -> EquipePlan:
    mission = mission_en_communication
    Mission.objects.filter(pk=mission.pk).update(ordre_mission_emis_le=timezone.now())
    superviseur = make_user(Role.AUDITEUR)
    affecter(mission, superviseur, RoleMission.SUPERVISEUR)
    action_a = creer_action(recommandations[0], libelle="Formaliser la procédure.", by=chef)
    action_resp = creer_action(
        recommandations[1], libelle="Former les agents.", by=chef, responsable=audite_entite_a
    )
    users = {
        "rai": make_user(Role.RAI),
        "chef": chef,
        "auditeur": auditeur_mission,
        "superviseur": superviseur,
        "audite_a": audite_entite_a,
        "audite_b": audite_entite_b,
        "non_affecte": make_user(Role.AUDITEUR),
        "audite_non_affecte": make_user(Role.AUDITE),
        "admin": make_user(Role.ADMIN),
        "dg": make_user(Role.DG),
    }
    return EquipePlan(mission, recommandations, action_a, action_resp, users)
