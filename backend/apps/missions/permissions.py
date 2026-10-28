"""Accès à l'API des missions : rôles (D4), visibilité (404) et refus de droit (403).

Les droits eux-mêmes sont calculés dans `acces.py`, `services/droits.py` et
`services/etapes.py` ; ce module ne fait que les appliquer aux routes.
"""

from typing import cast
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.handlers import FORBIDDEN
from apps.users.models import Role, User

from . import acces
from .models import Mission

MSG_DECLARATION = "Confirmez votre déclaration d'indépendance avant de contribuer à la mission."
ROLES_MISSIONS: tuple[str, ...] = (Role.RAI, Role.AUDITEUR, Role.AUDITE)


def exiger(condition: bool, message: str = FORBIDDEN) -> None:
    """Refuse (403) quand le droit n'est pas accordé."""
    if not condition:
        raise PermissionDenied(message)


def exiger_rai(user: User) -> None:
    exiger(user.role == Role.RAI)


def exiger_contribution(user: User, mission: Mission) -> None:
    """RAI, ou intervenant dont la déclaration est levée (`peut_contribuer`)."""
    if acces.peut_contribuer(user, mission):
        return
    if user.role == Role.AUDITEUR and acces.est_intervenant(user, mission):
        raise PermissionDenied(MSG_DECLARATION)
    raise PermissionDenied(FORBIDDEN)


def mission_visible(user: User, pk: UUID | str) -> Mission:
    """Mission visible pour l'utilisateur, sinon 404 (ne révèle pas son existence)."""
    return get_object_or_404(acces.missions_visibles(user), pk=pk)


def mission_du_corps(request: Request) -> Mission | None:
    """Résout le champ `mission` d'un POST enfant avant le sérialiseur.

    Mission invisible : 404, jamais 400. Champ absent ou illisible : `None`, le sérialiseur
    répondra 400.
    """
    brut = request.data.get("mission") if hasattr(request.data, "get") else None
    if brut is None:
        return None
    try:
        identifiant = UUID(str(brut))
    except ValueError:
        return None
    return mission_visible(cast(User, request.user), identifiant)


class MissionAccessPermission(BasePermission):
    """ADMIN et DG sont refusés (403) ; l'AUDITE n'accède qu'aux actions de `audite_actions`."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated and isinstance(user, User)):
            return False
        if user.role not in ROLES_MISSIONS:
            return False
        if user.role == Role.AUDITE:
            ouvertes: frozenset[str] = getattr(view, "audite_actions", frozenset())
            return getattr(view, "action", None) in ouvertes
        return True
