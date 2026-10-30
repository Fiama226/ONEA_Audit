"""Droits sur le rapport avant diffusion (section rédaction, D4, D13).

`contexte_rapport` calcule une fois le rôle et l'état de l'étape XVII ; `actions_rapport` est
ensuite pur. Les sections suivantes du lot (validation, diffusion) s'ajoutent à ce module.
"""

from dataclasses import dataclass

from apps.missions.acces import declaration_levee, est_chef, peut_contribuer, role_dans_mission
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import ROLES_INTERVENANTS, EtapeMission, Mission, StatutMission
from apps.users.models import Role, User

from .gardes import STATUTS_REDACTION
from .models import Rapport

MODIFIER = "MODIFIER"
SOUMETTRE = "SOUMETTRE"

ETAPE_REDACTION = 17


@dataclass(frozen=True)
class ContexteRapport:
    mission_statut: str = ""
    contribue: bool = False
    chef: bool = False
    xvii_close: bool = False


def contexte_rapport(mission: Mission, user: User) -> ContexteRapport:
    """Rôle de `user` et état de l'étape XVII, calculés une fois pour toutes les lignes."""
    statut_xvii = (
        EtapeMission.objects.filter(mission=mission, numero=ETAPE_REDACTION)
        .values_list("statut", flat=True)
        .first()
    )
    return ContexteRapport(
        mission_statut=mission.statut,
        contribue=peut_contribuer(user, mission),
        chef=est_chef(user, mission) and declaration_levee(user, mission),
        xvii_close=statut_xvii in STATUTS_ETAPE_CLOSE,
    )


def _ouvert(rapport: Rapport, contexte: ContexteRapport) -> bool:
    """Rédaction possible : mission en communication ; rapport corrigé sous RAPPORT_DIFFUSE."""
    if contexte.mission_statut == StatutMission.EN_COMMUNICATION:
        return True
    return rapport.corrige_de_id is not None and contexte.mission_statut == (
        StatutMission.RAPPORT_DIFFUSE
    )


def actions_rapport(rapport: Rapport, user: User, *, contexte: ContexteRapport) -> list[str]:
    """Actions de rédaction permises à `user` sur le rapport (`MODIFIER`, `SOUMETTRE`)."""
    if rapport.statut not in STATUTS_REDACTION or not _ouvert(rapport, contexte):
        return []
    actions: list[str] = []
    if contexte.contribue:
        actions.append(MODIFIER)
    if contexte.chef and contexte.xvii_close:
        actions.append(SOUMETTRE)
    return actions


def peut_lire_rapport_interne(user: User, mission: Mission) -> bool:
    """Rapport avant diffusion : RAI et intervenants de la mission (D13) ; jamais l'audité."""
    if user.role == Role.RAI:
        return True
    return user.role == Role.AUDITEUR and role_dans_mission(user, mission) in ROLES_INTERVENANTS
