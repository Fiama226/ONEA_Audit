"""Droits sur le rapport avant diffusion (section rédaction, D4, D13).

`contexte_rapport` calcule une fois le rôle, l'état de l'étape XVII et les rapports dont
l'utilisateur est destinataire ; `actions_rapport` est ensuite pur. Section validation et
diffusion (D9, D11, D12, D13) : `VALIDER`, `RENVOYER`, `DIFFUSER`, `CORRIGER`, `ACCUSER_RECEPTION`
et `rapports_diffuses_visibles`.
"""

from dataclasses import dataclass, field
from uuid import UUID

from django.db.models import QuerySet

from apps.missions.acces import (
    declaration_levee,
    est_chef,
    missions_visibles,
    peut_contribuer,
    role_dans_mission,
)
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import ROLES_INTERVENANTS, EtapeMission, Mission, StatutMission
from apps.users.models import Role, User

from .gardes import STATUTS_REDACTION
from .models import DestinataireDiffusion, Rapport, StatutRapport

MODIFIER = "MODIFIER"
SOUMETTRE = "SOUMETTRE"
VALIDER = "VALIDER"
RENVOYER = "RENVOYER"
DIFFUSER = "DIFFUSER"
CORRIGER = "CORRIGER"
ACCUSER_RECEPTION = "ACCUSER_RECEPTION"

ETAPE_REDACTION = 17


@dataclass(frozen=True)
class ContexteRapport:
    mission_statut: str = ""
    contribue: bool = False
    chef: bool = False
    xvii_close: bool = False
    rai: bool = False
    # Rapports dont l'utilisateur est destinataire interne et n'a pas encore accusé réception.
    a_accuser: frozenset[UUID] = field(default_factory=frozenset)


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
        rai=user.role == Role.RAI,
        a_accuser=frozenset(
            DestinataireDiffusion.objects.filter(
                mission=mission, utilisateur=user, accuse_reception_le__isnull=True
            ).values_list("rapport_id", flat=True)
        ),
    )


def _ouvert(rapport: Rapport, contexte: ContexteRapport) -> bool:
    """Rédaction possible : mission en communication ; rapport corrigé sous RAPPORT_DIFFUSE."""
    if contexte.mission_statut == StatutMission.EN_COMMUNICATION:
        return True
    return rapport.corrige_de_id is not None and contexte.mission_statut == (
        StatutMission.RAPPORT_DIFFUSE
    )


def actions_rapport(rapport: Rapport, user: User, *, contexte: ContexteRapport) -> list[str]:
    """Actions permises à `user` sur le rapport, selon son statut et la phase de la mission.

    Rédaction : `MODIFIER`, `SOUMETTRE`. Validation et diffusion : `VALIDER` (RAI, jamais l'auteur
    de la soumission), `RENVOYER`, `DIFFUSER`, `CORRIGER` (RAI) ; `ACCUSER_RECEPTION`
    (destinataire interne d'un rapport diffusé).
    """
    actions: list[str] = []
    statut = rapport.statut
    if statut in STATUTS_REDACTION and _ouvert(rapport, contexte):
        if contexte.contribue:
            actions.append(MODIFIER)
        if contexte.chef and contexte.xvii_close:
            actions.append(SOUMETTRE)
    elif statut == StatutRapport.SOUMIS and contexte.rai and _ouvert(rapport, contexte):
        if rapport.soumis_par_id != user.pk:
            actions.append(VALIDER)
        actions.append(RENVOYER)
    elif statut == StatutRapport.VALIDE and contexte.rai and _ouvert(rapport, contexte):
        actions.append(DIFFUSER)
    elif statut == StatutRapport.DIFFUSE:
        if contexte.rai and contexte.mission_statut == StatutMission.RAPPORT_DIFFUSE:
            actions.append(CORRIGER)
        if rapport.pk in contexte.a_accuser:
            actions.append(ACCUSER_RECEPTION)
    return actions


def rapports_diffuses_visibles(user: User) -> QuerySet[Rapport]:
    """Rapports diffusés visibles de `user` (D13) : DG et RAI tous ; AUDITEUR et AUDITE ceux de
    leurs missions visibles ; ADMIN aucun. Inclut les rapports remplacés par un rapport corrigé."""
    diffuses = Rapport.objects.filter(statut__in=[StatutRapport.DIFFUSE, StatutRapport.REMPLACE])
    if user.role in (Role.DG, Role.RAI):
        return diffuses
    if user.role in (Role.AUDITEUR, Role.AUDITE):
        return diffuses.filter(mission__in=missions_visibles(user))
    return Rapport.objects.none()


def peut_lire_rapport_interne(user: User, mission: Mission) -> bool:
    """Rapport avant diffusion : RAI et intervenants de la mission (D13) ; jamais l'audité."""
    if user.role == Role.RAI:
        return True
    return user.role == Role.AUDITEUR and role_dans_mission(user, mission) in ROLES_INTERVENANTS
