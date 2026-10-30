import pytest
from django.core.exceptions import PermissionDenied

from apps.constats.models import Recommandation
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from apps.recommandations.models import EngagementPlanActions
from apps.recommandations.services.actions import creer_action, modifier_action
from apps.recommandations.services.engagements import (
    MSG_AUCUNE,
    engager,
    etat_engagement,
    texte_engagement,
)
from apps.signatures.services import verifier
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_engagement_a_renouveler_apres_modification(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    chef: User,
) -> None:
    mission = mission_en_communication
    assert etat_engagement(mission, audite_entite_a) == "NON_CONFIRME"
    action = creer_action(recommandations[0], libelle="M", by=chef, responsable=audite_entite_a)
    creer_action(recommandations[1], libelle="N", by=chef, responsable=audite_entite_a)
    engagement = engager(mission, by=audite_entite_a, adresse_ip="10.0.0.2")
    assert etat_engagement(mission, audite_entite_a) == "CONFIRME"
    assert "les 2 actions" in engagement.confirmation.texte
    assert engagement.confirmation.texte == texte_engagement(mission, audite_entite_a)
    assert verifier(engagement.confirmation)
    modifier_action(action, by=chef, indicateur="Nouvel indicateur")
    assert etat_engagement(mission, audite_entite_a) == "A_RENOUVELER"
    engager(mission, by=audite_entite_a)
    assert etat_engagement(mission, audite_entite_a) == "CONFIRME"
    assert EngagementPlanActions.objects.filter(auteur=audite_entite_a).count() == 2


def test_engagement_sans_action_refuse(
    mission_en_communication: Mission, audite_entite_a: User, chef: User
) -> None:
    with pytest.raises(RegleMetierError, match=MSG_AUCUNE):
        engager(mission_en_communication, by=audite_entite_a)
    with pytest.raises(PermissionDenied):
        engager(mission_en_communication, by=chef)
