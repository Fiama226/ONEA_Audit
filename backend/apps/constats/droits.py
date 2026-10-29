"""Droits sur les constats (D13 du plan du lot 6) : seule source pour les vues et le frontend.

Construits sur `missions.acces`. `contexte_constats` calcule une fois pour toutes les lignes
(rôle, déclaration levée, statuts des étapes XIV et XV) ; `actions_constat` est ensuite pur.
"""

from dataclasses import dataclass

from django.db.models import QuerySet

from apps.missions.acces import (
    est_chef,
    peut_contribuer,
    peut_valider_travaux,
    role_dans_mission,
)
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import ROLES_INTERVENANTS, EtapeMission, Mission, RoleMission
from apps.missions.services.travaux import STATUTS_TRAVAUX
from apps.users.models import Role, User

from .gardes import ETAPE_CONSTATS, ETAPE_REUNION_CLOTURE
from .models import Constat, StatutConstat
from .services._fenetres import ACTIFS

MODIFIER = "MODIFIER"
SUPPRIMER = "SUPPRIMER"
SOUMETTRE = "SOUMETTRE"
VALIDER = "VALIDER"
RENVOYER = "RENVOYER"
ROUVRIR = "ROUVRIR"
REPONDRE = "REPONDRE"

_EDITABLES = (StatutConstat.BROUILLON, StatutConstat.RENVOYE)
_REPONDABLES = (StatutConstat.SOUMIS, StatutConstat.VALIDE)


@dataclass(frozen=True)
class ContexteConstats:
    contribue: bool = False
    chef_ou_rai: bool = False
    valideur: bool = False
    audite: bool = False
    xiv_active: bool = False
    xv_ouverte: bool = False


MSG_DIRECTION_ABSENTE = (
    "Votre direction n'est pas renseignée sur votre profil : vous ne pouvez pas répondre."
)
MSG_AUTRE_ENTITE = "Ce constat concerne une autre entité que votre direction."


def refus_entite(user: User, constat: Constat) -> str | None:
    """D11 : la direction de l'audité est l'entité du constat ou sa direction de rattachement.

    Échoue fermé : sans `direction_code` ou sans entité, la réponse est refusée.
    """
    if not user.direction_code:
        return MSG_DIRECTION_ABSENTE
    entite = constat.entite if constat.entite_id else None
    if entite is None:
        return MSG_AUTRE_ENTITE
    codes = {entite.code}
    if entite.parent is not None:
        codes.add(entite.parent.code)
    return None if user.direction_code in codes else MSG_AUTRE_ENTITE


def contexte_constats(mission: Mission, user: User) -> ContexteConstats:
    libre = mission.statut in STATUTS_TRAVAUX
    statuts = dict(
        EtapeMission.objects.filter(
            mission=mission, numero__in=(ETAPE_CONSTATS, ETAPE_REUNION_CLOTURE)
        ).values_list("numero", "statut")
    )
    role = role_dans_mission(user, mission)
    audite = user.role == Role.AUDITE and role == RoleMission.AUDITE
    intervenant = user.role == Role.RAI or role in ROLES_INTERVENANTS
    contribue = intervenant and peut_contribuer(user, mission)
    return ContexteConstats(
        contribue=contribue,
        chef_ou_rai=contribue and (user.role == Role.RAI or est_chef(user, mission)),
        valideur=intervenant and peut_valider_travaux(user, mission),
        audite=audite,
        xiv_active=libre and statuts.get(ETAPE_CONSTATS) in ACTIFS,
        xv_ouverte=libre
        and ETAPE_REUNION_CLOTURE in statuts
        and statuts[ETAPE_REUNION_CLOTURE] not in STATUTS_ETAPE_CLOSE,
    )


def actions_constat(constat: Constat, user: User, *, contexte: ContexteConstats) -> list[str]:
    actions: list[str] = []
    statut = constat.statut
    if contexte.xiv_active:
        if contexte.contribue and statut in _EDITABLES:
            actions += [MODIFIER, SUPPRIMER]
        if contexte.chef_ou_rai and statut in _EDITABLES:
            actions.append(SOUMETTRE)
        if contexte.valideur and user.pk not in (constat.created_by_id, constat.soumis_par_id):
            if statut == StatutConstat.SOUMIS:
                actions += [VALIDER, RENVOYER]
            elif statut == StatutConstat.VALIDE:
                actions.append(ROUVRIR)
    if (
        contexte.audite
        and contexte.xv_ouverte
        and statut in _REPONDABLES
        and refus_entite(user, constat) is None
    ):
        actions.append(REPONDRE)
    return actions


def constats_visibles(user: User, mission: Mission) -> QuerySet[Constat]:
    """RAI et intervenants : tous ; audité affecté : constats soumis ou validés ; sinon rien."""
    base = Constat.objects.filter(mission=mission)
    if user.role == Role.RAI:
        return base
    role = role_dans_mission(user, mission)
    if user.role == Role.AUDITEUR and role in ROLES_INTERVENANTS:
        return base
    if user.role == Role.AUDITE and role == RoleMission.AUDITE:
        return base.filter(statut__in=_REPONDABLES)
    return Constat.objects.none()
