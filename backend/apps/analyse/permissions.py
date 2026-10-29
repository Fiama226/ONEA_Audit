"""Accès à l'API d'analyse : rôles globaux, puis diffusion du référentiel à l'audité.

Ordre des refus : rôle (403) -> mission invisible (404) -> droit (403) -> sérialiseur (400)
-> règle métier ou fenêtre d'écriture (422, portée par les services).
"""

from rest_framework.request import Request
from rest_framework.views import APIView

from apps.missions.models import Mission
from apps.missions.permissions import MissionAccessPermission, exiger
from apps.users.models import Role, User

from .droits import droits_analyse

MSG_NON_DIFFUSE = "Le référentiel d'audit n'est pas encore diffusé aux audités."
ACTIONS_ECRITURE_AUDITE: frozenset[str] = frozenset({"opinions"})


class AnalyseAccessPermission(MissionAccessPermission):
    """Étend l'accès des missions : l'AUDITE ne lit que les actions ouvertes de la vue et
    n'écrit que par `opinions` (son avis)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        user = request.user
        if isinstance(user, User) and user.role == Role.AUDITE:
            return request.method in ("GET", "HEAD", "OPTIONS") or (
                getattr(view, "action", None) in ACTIONS_ECRITURE_AUDITE
            )
        return True


def exiger_referentiel_visible(user: User, mission: Mission) -> None:
    """403 « non diffusé » pour un audité tant que l'étape VI n'est pas démarrée."""
    if user.role == Role.AUDITE:
        exiger(droits_analyse(user, mission).voir_referentiel, MSG_NON_DIFFUSE)
