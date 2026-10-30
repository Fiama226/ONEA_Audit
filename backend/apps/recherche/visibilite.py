"""Filtre de visibilité envoyé au moteur (R14) : premier des deux filtres.

- RAI : `audience = "EQUIPE"` ;
- AUDITEUR : `mission_id IN [missions visibles] AND audience = "EQUIPE"` ;
- AUDITE : `mission_id IN [missions visibles] AND audience = "AUDITE"` ;
- DG : `mission_id IN [missions diffusées] AND audience = "DG"` ;
- ADMIN, compte inactif ou liste de missions vide : `None` (aucun résultat possible, le moteur
  n'est pas interrogé).
"""

from apps.missions.acces import missions_visibles
from apps.suivi.droits import missions_suivi_visibles
from apps.users.models import Role, User

from .client import echapper_filtre
from .sources import AUDIENCE_AUDITE, AUDIENCE_DG, AUDIENCE_EQUIPE

ROLES_RECHERCHE: tuple[str, ...] = (Role.RAI, Role.AUDITEUR, Role.AUDITE, Role.DG)


def _egal(champ: str, valeur: str) -> str:
    return f'{champ} = "{echapper_filtre(valeur)}"'


def _missions_dans(user: User, audience: str, *, diffusees: bool = False) -> str | None:
    missions = missions_suivi_visibles(user) if diffusees else missions_visibles(user)
    ids = [str(pk) for pk in missions.values_list("pk", flat=True)]
    if not ids:
        return None
    liste = ", ".join(f'"{echapper_filtre(i)}"' for i in sorted(ids))
    return f"mission_id IN [{liste}] AND {_egal('audience', audience)}"


def filtre_pour(user: User) -> str | None:
    if not user.is_active or user.role not in ROLES_RECHERCHE:
        return None
    if user.role == Role.RAI:
        return _egal("audience", AUDIENCE_EQUIPE)
    if user.role == Role.AUDITEUR:
        return _missions_dans(user, AUDIENCE_EQUIPE)
    if user.role == Role.AUDITE:
        return _missions_dans(user, AUDIENCE_AUDITE)
    return _missions_dans(user, AUDIENCE_DG, diffusees=True)
