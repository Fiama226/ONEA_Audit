"""Account administration: the ADMIN role, or rights delegated by an admin (`delegation`).

The rights are re-read from the database on each check, never cached. The services repeat
every check on the locked target row: these classes only give the early 403.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .delegation import ACTIONS, Action, droits_effectifs, peut
from .models import Role, User


def _acteur(request: Request) -> User | None:
    user = request.user
    if user and user.is_authenticated and isinstance(user, User):
        return user
    return None


def _admin_de_la_requete(acteur: User) -> bool:
    """Shortcut without a query: the session authentication re-reads the user (role,
    active flag) on every request. Delegated rights are always read from the database."""
    return acteur.role == Role.ADMIN and acteur.is_active


def PeutGererComptes(*actions: Action) -> type[BasePermission]:  # noqa: N802
    """Allowed when the user holds at least one of ``actions``; on an object, at least one
    of them on that very account (a delegate never acts on an ADMIN, another manager or
    himself)."""
    if not actions or any(a not in ACTIONS for a in actions):
        raise ValueError(f"Unknown account actions: {actions!r}")

    class _PeutGererComptes(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool:
            acteur = _acteur(request)
            if acteur is None:
                return False
            if _admin_de_la_requete(acteur):
                return True
            droits = droits_effectifs(acteur)
            return any(droits[a] for a in actions)

        def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
            acteur = _acteur(request)
            if acteur is None or not isinstance(obj, User):
                return False
            if _admin_de_la_requete(acteur):
                return True
            return any(peut(acteur, a, obj) for a in actions)

    _PeutGererComptes.__name__ = "PeutGererComptes_" + "_".join(actions)
    return _PeutGererComptes


class LectureComptes(BasePermission):
    """Reading the accounts: the ADMIN, or anyone holding a delegated right (a delegate
    must see the accounts he acts on, admins included)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        acteur = _acteur(request)
        if acteur is None:
            return False
        return _admin_de_la_requete(acteur) or any(droits_effectifs(acteur).values())


class AccountAdminPermission(BasePermission):
    """Everything else (delegations, imports, import password files): ADMIN only."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        acteur = _acteur(request)
        return acteur is not None and _admin_de_la_requete(acteur)
