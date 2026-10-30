"""Remise au lot 8 (D14) : actions des rapports diffusés."""

from django.db.models import QuerySet

from apps.missions.models import Mission, StatutMission

from ..models import Action

STATUTS_A_SUIVRE = (StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI)


def actions_a_suivre(mission: Mission | None = None) -> QuerySet[Action]:
    """Actions non supprimées des missions `RAPPORT_DIFFUSE` ou `EN_SUIVI`."""
    actions = Action.objects.filter(mission__statut__in=STATUTS_A_SUIVRE)
    if mission is not None:
        actions = actions.filter(mission=mission)
    return actions
