from typing import Protocol, cast

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.users.models import Role, User

TOUS_ROLES: tuple[str, ...] = tuple(Role.values)
LECTURE_CARTOGRAPHIE: tuple[str, ...] = (Role.ADMIN, Role.RAI, Role.AUDITEUR, Role.DG)
ECRITURE_STRUCTURE: tuple[str, ...] = (Role.RAI, Role.ADMIN)
ECRITURE_CARTOGRAPHIE: tuple[str, ...] = (Role.RAI,)


class VueAvecRoles(Protocol):
    read_roles: tuple[str, ...]
    write_roles: tuple[str, ...]


class RolePermission(BasePermission):
    """Lecture / écriture réservées aux rôles de `view.read_roles` / `view.write_roles` (D4)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated and isinstance(user, User)):
            return False
        vue = cast(VueAvecRoles, view)
        roles = vue.read_roles if request.method in SAFE_METHODS else vue.write_roles
        return user.has_role(*roles)
