"""Accès à l'API des constats (D11, D13) : rôles, périmètre de lecture et ordre des refus.

Ordre des refus : rôle global (403, ADMIN et DG inclus ; l'AUDITE seulement sur les actions de
`audite_actions` de la vue) -> mission ou objet invisible (404) -> droit (403) -> contenu de la
requête (400) -> règle métier, gel ou fenêtre d'écriture (422, par les services).
"""

from django.db.models import Q, QuerySet

from apps.missions.acces import missions_visibles
from apps.missions.permissions import MissionAccessPermission
from apps.users.models import Role, User

from .models import Constat, StatutConstat

REPONDABLES = (StatutConstat.SOUMIS, StatutConstat.VALIDE)


class ConstatsAccessPermission(MissionAccessPermission):
    """Les vues déclarent `audite_actions` : lecture (et réponse) seulement pour l'audité."""


def constats_lisibles(user: User) -> QuerySet[Constat]:
    """Constats lisibles par l'utilisateur, dans les missions qu'il voit.

    L'audité ne lit que les constats soumis ou validés de sa direction (ou rattachés à elle) ;
    sans `direction_code`, il n'en lit aucun (même règle fermée que `droits.refus_entite`).
    """
    base = Constat.objects.filter(mission__in=missions_visibles(user))
    if user.role != Role.AUDITE:
        return base
    if not user.direction_code:
        return base.none()
    code = user.direction_code
    return base.filter(statut__in=REPONDABLES).filter(
        Q(entite__code=code) | Q(entite__parent__code=code)
    )
