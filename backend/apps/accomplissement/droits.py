"""Droits de l'accomplissement : seule source, consommée par les services, les vues et le frontend.

Section programme (étapes VIII à X, D5, D6, D13). Construite sur `missions.acces` : aucune règle
de rôle n'est recopiée, les fonctions `peut_*` ci-dessous ne font que composer `peut_contribuer`,
`est_chef` et `est_superviseur`. Les T5 (fiches) et T6 ajoutent leurs sections plus bas.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from apps.analyse.gardes import ACTIFS, statuts_etapes
from apps.missions.gardes import STATUTS_FIGES
from apps.missions.models import ROLES_INTERVENANTS, Mission, RoleMission
from apps.missions.services.etapes import ContexteActions, contexte_actions
from apps.users.models import Role, User

from .models import FicheDeTest, StatutFiche, StatutTest, TestPrevu

MODIFIER_CONTENU = "MODIFIER_CONTENU"
MODIFIER_RESSOURCES = "MODIFIER_RESSOURCES"
AJOUTER_COMPLEMENTAIRE = "AJOUTER_COMPLEMENTAIRE"
MODIFIER = "MODIFIER"
SUPPRIMER = "SUPPRIMER"
ABANDONNER = "ABANDONNER"

ETAPE_CONTENU = 8
ETAPE_RESSOURCES = 9
ETAPE_COMPLEMENTAIRES = 12


@dataclass(frozen=True)
class ContexteProgramme(ContexteActions):
    """Rôle (comme `ContexteActions`) + statuts des étapes VIII, IX, XII + fiches des tests.

    À construire une fois pour toute une liste de tests : `actions_test` ne requête plus.
    """

    statuts: Mapping[int, str]
    fiches: Mapping[UUID, str]  # test_id -> statut de sa fiche active


def contexte_programme(mission: Mission, user: User) -> ContexteProgramme:
    """Quatre requêtes au plus (rôle, déclaration, statuts d'étapes, fiches)."""
    base = contexte_actions(mission, user)
    fiches = dict(FicheDeTest.objects.filter(mission=mission).values_list("test_id", "statut"))
    return ContexteProgramme(
        mission=base.mission,
        role_mission=base.role_mission,
        levee=base.levee,
        statuts=statuts_etapes(
            mission.pk, (ETAPE_CONTENU, ETAPE_RESSOURCES, ETAPE_COMPLEMENTAIRES)
        ),
        fiches=fiches,
    )


def profil(user: User, ctx: ContexteActions) -> tuple[bool, bool, bool]:
    """(contribue, ressources, complémentaires) à partir du contexte déjà calculé.

    Contribuer = `acces.peut_contribuer` ; ressources (IX) = RAI, chef ou superviseur levé ;
    compléments et abandons (XII, D6) = RAI ou chef levé. Source unique : les services
    appliquent ce même profil.
    """
    if user.role == Role.RAI:
        return True, True, True
    if ctx.role_mission not in ROLES_INTERVENANTS or not ctx.levee:
        return False, False, False
    chef = ctx.role_mission == RoleMission.CHEF_MISSION
    return True, chef or ctx.role_mission == RoleMission.SUPERVISEUR, chef


def _actif(ctx: ContexteProgramme, numero: int) -> bool:
    return ctx.statuts.get(numero) in ACTIFS


def actions_programme(user: User, mission: Mission) -> list[str]:
    """Actions d'écriture sur le programme (VIII), les ressources (IX) et les compléments (XII)."""
    if mission.statut in STATUTS_FIGES:
        return []
    ctx = contexte_programme(mission, user)
    contribue, ressources, complementaires = profil(user, ctx)
    actions: list[str] = []
    if contribue and _actif(ctx, ETAPE_CONTENU):
        actions.append(MODIFIER_CONTENU)
    if ressources and _actif(ctx, ETAPE_RESSOURCES):
        actions.append(MODIFIER_RESSOURCES)
    if complementaires and _actif(ctx, ETAPE_COMPLEMENTAIRES):
        actions.append(AJOUTER_COMPLEMENTAIRE)
    return actions


def actions_test(test: TestPrevu, user: User, *, contexte: ContexteProgramme) -> list[str]:
    """Actions possibles sur un test : MODIFIER, SUPPRIMER, ABANDONNER (D5, D6)."""
    if contexte.mission.statut in STATUTS_FIGES or test.statut != StatutTest.PREVU:
        return []
    contribue, ressources, complementaires = profil(user, contexte)
    statut_fiche = contexte.fiches.get(test.pk)
    actions: list[str] = []
    if test.complementaire:
        ouvert = complementaires and _actif(contexte, ETAPE_COMPLEMENTAIRES)
        if ouvert:
            actions.append(MODIFIER)
            if statut_fiche is None:
                actions.append(SUPPRIMER)
    else:
        contenu = contribue and _actif(contexte, ETAPE_CONTENU)
        if contenu or (ressources and _actif(contexte, ETAPE_RESSOURCES)):
            actions.append(MODIFIER)
        if contenu and statut_fiche is None:
            actions.append(SUPPRIMER)
    if (
        complementaires
        and _actif(contexte, ETAPE_COMPLEMENTAIRES)
        and statut_fiche != StatutFiche.VALIDE
    ):
        actions.append(ABANDONNER)
    return actions
