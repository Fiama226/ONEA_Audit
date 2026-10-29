"""Droits sur les fiches de test et les pièces (étapes XII et XIII).

Section « fiches » : fonctions distinctes de celles du programme (tâche 4). L'audité ne voit
ni fiches ni pièces en v1. Les gardes d'écriture relisent la base ; ici, les actions proposées
aux vues et au frontend.
"""

from django.core.exceptions import PermissionDenied

from apps.missions import acces
from apps.missions.gardes import STATUTS_FIGES
from apps.missions.models import ROLES_INTERVENANTS, Mission, RoleMission, StatutEtape
from apps.missions.services.etapes import MSG_DECLARATION, MSG_DROIT, ContexteActions
from apps.users.models import Role, User

from .gardes import ETAPE_FICHES, ETAPE_VALIDATION_PREUVES
from .models import FicheDeTest, PieceJustificative, StatutFiche

ACTIFS = frozenset({StatutEtape.EN_COURS, StatutEtape.RENVOYEE})
EDITABLES = (StatutFiche.BROUILLON, StatutFiche.RENVOYE)


def exiger_contributeur(user: User, mission: Mission) -> None:
    """403 si `user` ne peut pas contribuer aux fiches (RAI, ou intervenant à déclaration levée)."""
    if acces.peut_contribuer(user, mission):
        return
    if acces.est_intervenant(user, mission):
        raise PermissionDenied(MSG_DECLARATION)
    raise PermissionDenied(MSG_DROIT)


def exiger_valideur(user: User, mission: Mission) -> None:
    """403 si `user` ne peut pas valider les travaux (RAI, ou superviseur à déclaration levée)."""
    if not acces.peut_valider_travaux(user, mission):
        raise PermissionDenied(MSG_DROIT)


def _statut_etape(mission: Mission, numero: int) -> str | None:
    from apps.missions.models import EtapeMission

    statut: str | None = (
        EtapeMission.all_objects.filter(mission=mission, numero=numero, deleted_at__isnull=True)
        .values_list("statut", flat=True)
        .first()
    )
    return statut


def _contribue(user: User, contexte: ContexteActions) -> bool:
    if user.role == Role.RAI:
        return True
    return contexte.role_mission in ROLES_INTERVENANTS and contexte.levee


def _valide(user: User, contexte: ContexteActions) -> bool:
    return user.role == Role.RAI or (
        contexte.role_mission == RoleMission.SUPERVISEUR and contexte.levee
    )


def actions_fiche(fiche: FicheDeTest, user: User, *, contexte: ContexteActions) -> list[str]:
    """Actions possibles : MODIFIER, SOUMETTRE, DEPOSER_PIECE, VALIDER, RENVOYER, ROUVRIR."""
    mission = contexte.mission
    if mission.statut in STATUTS_FIGES:
        return []
    actions: list[str] = []
    if _contribue(user, contexte) and (
        fiche.statut in EDITABLES and _statut_etape(mission, ETAPE_FICHES) in ACTIFS
    ):
        actions += ["MODIFIER", "SOUMETTRE", "DEPOSER_PIECE"]
    if _valide(user, contexte) and _statut_etape(mission, ETAPE_VALIDATION_PREUVES) in ACTIFS:
        if fiche.statut == StatutFiche.SOUMIS:
            if fiche.auteur_id != user.pk:
                actions.append("VALIDER")
            actions.append("RENVOYER")
        elif fiche.statut == StatutFiche.VALIDE:
            actions.append("ROUVRIR")
    return actions


def actions_piece(piece: PieceJustificative, user: User, *, contexte: ContexteActions) -> list[str]:
    """Actions possibles : MODIFIER, RETIRER (fiche modifiable), TELECHARGER (équipe, RAI)."""
    mission = contexte.mission
    actions: list[str] = []
    if user.role == Role.RAI or contexte.role_mission in ROLES_INTERVENANTS:
        actions.append("TELECHARGER")
    if mission.statut in STATUTS_FIGES:
        return actions
    fiche_statut = (
        FicheDeTest.all_objects.filter(pk=piece.fiche_id).values_list("statut", flat=True).first()
    )
    if (
        _contribue(user, contexte)
        and fiche_statut in EDITABLES
        and _statut_etape(mission, ETAPE_FICHES) in ACTIFS
    ):
        actions += ["MODIFIER", "RETIRER"]
    return actions
