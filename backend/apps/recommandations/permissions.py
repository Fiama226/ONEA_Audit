"""Accès à l'API du plan d'actions (D8, D13) : rôles et périmètre de lecture.

Ordre des refus : rôle global (403, ADMIN et DG inclus ; l'AUDITE seulement sur les actions de
`audite_actions` de la vue) -> mission ou objet invisible (404) -> droit (403) -> contenu de la
requête (400) -> règle métier, gel ou fenêtre d'écriture (422, par les services).
Les droits eux-mêmes viennent de `droits.py` : ce module ne fait que les appliquer.
"""

from django.db.models import Q, QuerySet

from apps.constats.models import Recommandation
from apps.constats.permissions import constats_lisibles
from apps.missions.acces import missions_visibles
from apps.missions.permissions import MissionAccessPermission
from apps.users.models import Role, User

from .models import AcceptationRisque, Action, EngagementPlanActions


class RecommandationsAccessPermission(MissionAccessPermission):
    """Les vues déclarent `audite_actions` : l'audité n'accède qu'à celles-ci."""


def actions_lisibles(user: User) -> QuerySet[Action]:
    """Actions des missions visibles ; l'audité : ses actions et celles de sa direction."""
    base = Action.objects.filter(mission__in=missions_visibles(user))
    if user.role != Role.AUDITE:
        return base
    critere = Q(responsable=user)
    if user.direction_code:
        critere |= Q(recommandation__constat__entite__code=user.direction_code)
    return base.filter(critere)


def recommandations_lisibles(user: User) -> QuerySet[Recommandation]:
    """Recommandations des constats lisibles (l'audité : soumis ou validés de sa direction)."""
    return Recommandation.objects.filter(constat__in=constats_lisibles(user))


def acceptations_lisibles(user: User) -> QuerySet[AcceptationRisque]:
    return AcceptationRisque.objects.filter(recommandation__in=recommandations_lisibles(user))


def engagements_lisibles(user: User) -> QuerySet[EngagementPlanActions]:
    """Équipe : tous les engagements des missions visibles ; l'audité : les siens."""
    base = EngagementPlanActions.objects.filter(mission__in=missions_visibles(user))
    return base.filter(auteur=user) if user.role == Role.AUDITE else base
