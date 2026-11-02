"""Droits sur le rapport avant diffusion (section rédaction, D4, D13).

`contexte_rapport` calcule une fois le rôle, l'état de l'étape XVII et les rapports dont
l'utilisateur est destinataire ; `actions_rapport` est ensuite pur. Section validation et
diffusion (D9, D11, D12, D13) : `VALIDER`, `RENVOYER`, `DIFFUSER`, `CORRIGER`, `ACCUSER_RECEPTION`
et `rapports_diffuses_visibles`.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from django.db.models import Q, QuerySet

from apps.constats.models import Constat
from apps.missions.acces import (
    declaration_levee,
    est_chef,
    est_responsable_entite,
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


def rapports_dont_destinataire(user: User) -> QuerySet[Rapport]:
    """Rapports diffusés dont `user` figure, comme destinataire interne actif, dans la liste de
    diffusion (écart 1). Donne la lecture du rapport et de ses pièces de diffusion, jamais celle de
    la mission : les destinataires sont figés à la diffusion et n'existent qu'à elle."""
    return Rapport.objects.filter(
        statut__in=[StatutRapport.DIFFUSE, StatutRapport.REMPLACE],
        pk__in=DestinataireDiffusion.objects.filter(utilisateur=user).values("rapport_id"),
    )


def rapports_diffuses_visibles(user: User) -> QuerySet[Rapport]:
    """Rapports diffusés visibles de `user` (D13) : DG et RAI tous ; AUDITEUR et AUDITE ceux de
    leurs missions visibles ou dont ils sont destinataires de la diffusion ; ADMIN aucun. Inclut
    les rapports remplacés par un rapport corrigé."""
    diffuses = Rapport.objects.filter(statut__in=[StatutRapport.DIFFUSE, StatutRapport.REMPLACE])
    if user.role in (Role.DG, Role.RAI):
        return diffuses
    if user.role in (Role.AUDITEUR, Role.AUDITE):
        return diffuses.filter(
            Q(mission__in=missions_visibles(user)) | Q(pk__in=rapports_dont_destinataire(user))
        )
    return Rapport.objects.none()


def peut_lire_rapport_interne(user: User, mission: Mission) -> bool:
    """Rapport avant diffusion : RAI et intervenants de la mission (D13) ; jamais l'audité."""
    if user.role == Role.RAI:
        return True
    return user.role == Role.AUDITEUR and role_dans_mission(user, mission) in ROLES_INTERVENANTS


# --- Rapport provisoire (étape XV) et réponses (étape XVI) ---------------------------------

TRANSMETTRE = "TRANSMETTRE"
ETAPE_CLOTURE = 15


@dataclass(frozen=True)
class ContexteProvisoire:
    mission_statut: str = ""
    rai: bool = False
    chef: bool = False
    xv_ouverte: bool = False


def contexte_provisoire(mission: Mission, user: User) -> ContexteProvisoire:
    """Rôle de `user` et état de l'étape XV, calculés une fois pour toutes les lignes."""
    statut_xv = (
        EtapeMission.objects.filter(mission=mission, numero=ETAPE_CLOTURE)
        .values_list("statut", flat=True)
        .first()
    )
    return ContexteProvisoire(
        mission_statut=mission.statut,
        rai=user.role == Role.RAI,
        chef=est_chef(user, mission) and declaration_levee(user, mission),
        xv_ouverte=statut_xv is not None and statut_xv not in STATUTS_ETAPE_CLOSE,
    )


def actions_provisoire(
    rapport: Rapport,  # noqa: ARG001
    user: User,  # noqa: ARG001
    *,
    contexte: ContexteProvisoire,
) -> list[str]:
    """`TRANSMETTRE` : chef ou RAI, mission en communication, XV non close."""
    if contexte.mission_statut != StatutMission.EN_COMMUNICATION or not contexte.xv_ouverte:
        return []
    return [TRANSMETTRE] if contexte.rai or contexte.chef else []


def constats_a_repondre(user: User, provisoire: Any) -> list[UUID]:
    """Constats du provisoire dont `user` est le responsable d'entité (D7)."""
    if user.role != Role.AUDITE:
        return []
    instantane = provisoire.instantane or {}
    references = [c["reference"] for c in instantane.get("constats") or []]
    cache: dict[Any, bool] = {}
    ids: list[UUID] = []
    constats = Constat.objects.filter(
        mission_id=provisoire.mission_id, reference__in=references
    ).order_by("reference")
    for constat in constats:
        if constat.entite_id is None:
            continue
        if constat.entite_id not in cache:
            cache[constat.entite_id] = est_responsable_entite(
                user, provisoire.mission, constat.entite_id
            )
        if cache[constat.entite_id]:
            ids.append(constat.pk)
    return ids
