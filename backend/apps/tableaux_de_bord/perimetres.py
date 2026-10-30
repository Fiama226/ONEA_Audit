"""Périmètres des tableaux de bord : année de référence et refus de rôle."""

from django.db.models import Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.core.handlers import FORBIDDEN
from apps.missions.models import Mission
from apps.suivi.droits import STATUTS_MISSION_SUIVI
from apps.suivi.models import SuiviAction
from apps.users.models import User


def exiger_role(user: User, *roles: str) -> None:
    """Refuse (403) un utilisateur dont le rôle n'est pas dans `roles`."""
    if user.role not in roles:
        raise PermissionDenied(FORBIDDEN)


def missions_de_l_annee(qs: QuerySet[Mission], annee: int) -> QuerySet[Mission]:
    """Missions de l'année ; un brouillon sans année compte dans l'année de sa création."""
    return qs.filter(Q(annee=annee) | Q(annee__isnull=True, created_at__year=annee))


def suivis_diffuses_de_l_annee(suivis: QuerySet[SuiviAction], annee: int) -> QuerySet[SuiviAction]:
    """Suivis des missions dont le rapport a été diffusé dans l'année (R12)."""
    return suivis.filter(diffuse_le__year=annee, mission__statut__in=STATUTS_MISSION_SUIVI)
