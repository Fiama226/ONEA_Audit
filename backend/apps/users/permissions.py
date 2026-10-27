from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import Role, User


def HasRole(*roles: str) -> type[BasePermission]:  # noqa: N802
    """Factory of DRF permission classes granting access to the given roles."""

    class _HasRole(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool:
            user = request.user
            return bool(
                user and user.is_authenticated and isinstance(user, User) and user.has_role(*roles)
            )

    _HasRole.__name__ = "HasRole_" + "_".join(roles)
    return _HasRole


IsAdmin = HasRole(Role.ADMIN)
IsRAI = HasRole(Role.RAI)
IsRAIOrAdmin = HasRole(Role.RAI, Role.ADMIN)


class ReadOnlyForDG(BasePermission):
    """Authenticated users; the DG role is restricted to safe (read) methods."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated and isinstance(user, User)):
            return False
        if user.has_role(Role.DG):
            return request.method in SAFE_METHODS
        return True
