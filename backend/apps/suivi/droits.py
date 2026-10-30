"""Droits du suivi : section visibilité (R11).

- RAI : tout ; DG : lecture seule ; AUDITEUR et AUDITE : leurs missions (`missions_visibles`) ;
  ADMIN : rien.
- Le suivi n'est lisible que pour les missions dont le rapport est déjà diffusé.
"""

from django.db.models import QuerySet

from apps.missions.acces import missions_visibles
from apps.missions.models import Mission, StatutMission
from apps.users.models import Role, User

from .models import SuiviAction

STATUTS_MISSION_SUIVI: frozenset[str] = frozenset(
    {StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI, StatutMission.CLOTUREE}
)


def missions_suivi_visibles(user: User) -> QuerySet[Mission]:
    if user.role in (Role.RAI, Role.DG):
        base = Mission.objects.all()
    elif user.role in (Role.AUDITEUR, Role.AUDITE):
        base = missions_visibles(user)
    else:
        return Mission.objects.none()
    return base.filter(statut__in=STATUTS_MISSION_SUIVI)


def suivis_visibles(user: User) -> QuerySet[SuiviAction]:
    return SuiviAction.objects.filter(mission__in=missions_suivi_visibles(user).values("pk"))
