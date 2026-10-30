"""Accès à l'API du suivi (R11) : rôle global seulement.

Ordre des refus : rôle global (403, ADMIN inclus) -> objet invisible (404) -> droit (403, calculé
par `droits.py`) -> sérialiseur (400) -> règle métier ou gel (422, par les services).
Les droits eux-mêmes viennent de `droits.py` : ce module ne fait que les appliquer.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.users.models import Role, User

ROLES_SUIVI: tuple[str, ...] = (Role.RAI, Role.AUDITEUR, Role.AUDITE, Role.DG)


class SuiviAccessPermission(BasePermission):
    """Les vues peuvent restreindre `roles_suivi` (ex. RAI seul pour la clôture de mission)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated and isinstance(user, User)):
            return False
        roles: tuple[str, ...] = getattr(view, "roles_suivi", ROLES_SUIVI)
        return user.role in roles
