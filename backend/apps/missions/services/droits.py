"""Droits de l'utilisateur sur une mission : rôle (D4) et état de la mission (D2).

Seule source des booléens exposés par `Mission.mes_droits` ; les vues et le frontend la
consomment sans recalculer.
"""

from dataclasses import dataclass

from apps.users.models import Role, User

from ..gardes import STATUTS_FIGES
from ..models import (
    ROLES_INTERVENANTS,
    DeclarationIndependance,
    Mission,
    StatutDeclaration,
    StatutEtape,
    StatutMission,
)
from .missions import STATUTS_ORDRE, SUSPENDABLES

_EDITABLES = frozenset({StatutMission.BROUILLON, *SUSPENDABLES})
_TRAVAUX = frozenset(SUSPENDABLES)


@dataclass(frozen=True)
class DroitsMission:
    modifier: bool = False
    planifier: bool = False
    lancer: bool = False
    emettre_ordre: bool = False
    suspendre: bool = False
    reprendre: bool = False
    annuler: bool = False
    supprimer: bool = False
    affecter: bool = False
    contribuer: bool = False
    voir_travaux: bool = False
    confirmer_ma_declaration: bool = False


def _droits_rai(mission: Mission) -> DroitsMission:
    statut = mission.statut
    if statut == StatutMission.SUSPENDUE:
        return DroitsMission(reprendre=True, annuler=True, voir_travaux=True)
    if statut in STATUTS_FIGES:
        return DroitsMission(voir_travaux=True)
    ordre = (
        statut in STATUTS_ORDRE
        and mission.etapes.filter(
            numero=1, statut__in=(StatutEtape.EN_COURS, StatutEtape.RENVOYEE)
        ).exists()
    )
    return DroitsMission(
        modifier=statut in _EDITABLES,
        planifier=statut == StatutMission.BROUILLON,
        lancer=statut == StatutMission.PLANIFIEE,
        emettre_ordre=ordre,
        suspendre=statut in SUSPENDABLES,
        annuler=statut in SUSPENDABLES,
        supprimer=statut == StatutMission.BROUILLON,
        affecter=statut in _EDITABLES,
        contribuer=statut in _TRAVAUX,
        voir_travaux=True,
    )


def _droits_intervenant(user: User, mission: Mission) -> DroitsMission:
    """Une seule requête : la déclaration de l'intervenant donne son rôle et sa levée."""
    declaration = DeclarationIndependance.objects.filter(
        affectation__mission=mission,
        affectation__utilisateur=user,
        affectation__role_mission__in=ROLES_INTERVENANTS,
    ).first()
    statut = mission.statut
    if declaration is None or statut == StatutMission.BROUILLON:
        return DroitsMission()
    if statut in STATUTS_FIGES:
        return DroitsMission(voir_travaux=True)
    return DroitsMission(
        contribuer=statut in _TRAVAUX and declaration.levee,
        voir_travaux=True,
        confirmer_ma_declaration=declaration.statut == StatutDeclaration.EN_ATTENTE,
    )


def droits_mission(user: User, mission: Mission) -> DroitsMission:
    if user.role == Role.RAI:
        return _droits_rai(mission)
    if user.role == Role.AUDITEUR:
        return _droits_intervenant(user, mission)
    return DroitsMission()
