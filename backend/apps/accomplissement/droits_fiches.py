"""Droits sur les fiches de test et les pièces (étapes XII et XIII), D13 du plan du lot 6.

Rédiger (créer, modifier, soumettre une fiche ; déposer, renommer, retirer une pièce) :
le RAI, le chef de mission, ou l'auditeur DU TEST (déclaration d'indépendance levée pour les
deux derniers). Un autre auditeur ou le superviseur ne rédige pas ; ils valident (XIII) via
`peut_valider_travaux`. L'audité ne voit ni fiches ni pièces en v1.
"""

from django.core.exceptions import PermissionDenied

from apps.missions import acces
from apps.missions.gardes import STATUTS_FIGES
from apps.missions.models import ROLES_INTERVENANTS, Mission, RoleMission, StatutEtape
from apps.missions.services.etapes import MSG_DECLARATION, MSG_DROIT, ContexteActions
from apps.users.models import Role, User

from .gardes import ETAPE_FICHES, ETAPE_VALIDATION_PREUVES
from .models import FicheDeTest, PieceJustificative, StatutFiche, TestPrevu

ACTIFS = frozenset({StatutEtape.EN_COURS, StatutEtape.RENVOYEE})
EDITABLES = (StatutFiche.BROUILLON, StatutFiche.RENVOYE)


def peut_rediger(user: User, mission: Mission, test: TestPrevu) -> bool:
    """RAI, chef de mission (levé) ou auditeur du test (levé)."""
    if user.role == Role.RAI:
        return True
    role = acces.role_dans_mission(user, mission)
    if role == RoleMission.CHEF_MISSION or (
        role in ROLES_INTERVENANTS and test.auditeur_id == user.pk
    ):
        return acces.declaration_levee(user, mission)
    return False


def exiger_redacteur(user: User, mission: Mission, test: TestPrevu) -> None:
    """403 si `user` ne peut pas rédiger la fiche de `test`."""
    if peut_rediger(user, mission, test):
        return
    if acces.est_intervenant(user, mission) and not acces.declaration_levee(user, mission):
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


def _redige(user: User, contexte: ContexteActions, auditeur_id: object) -> bool:
    if user.role == Role.RAI:
        return True
    if not contexte.levee:
        return False
    return contexte.role_mission == RoleMission.CHEF_MISSION or (
        contexte.role_mission in ROLES_INTERVENANTS and auditeur_id == user.pk
    )


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
    auditeur_id = (
        TestPrevu.all_objects.filter(pk=fiche.test_id).values_list("auditeur_id", flat=True).first()
    )
    if (
        _redige(user, contexte, auditeur_id)
        and fiche.statut in EDITABLES
        and _statut_etape(mission, ETAPE_FICHES) in ACTIFS
    ):
        actions += ["MODIFIER", "SOUMETTRE", "DEPOSER_PIECE"]
    if _valide(user, contexte) and _statut_etape(mission, ETAPE_VALIDATION_PREUVES) in ACTIFS:
        if fiche.statut == StatutFiche.SOUMIS:
            if user.pk not in (fiche.auteur_id, fiche.soumise_par_id):
                actions.append("VALIDER")
            actions.append("RENVOYER")
        elif fiche.statut == StatutFiche.VALIDE:
            actions.append("ROUVRIR")
    return actions


def actions_piece(piece: PieceJustificative, user: User, *, contexte: ContexteActions) -> list[str]:
    """Actions possibles : MODIFIER, RETIRER (rédacteur, fiche modifiable), TELECHARGER."""
    mission = contexte.mission
    actions: list[str] = []
    if user.role == Role.RAI or contexte.role_mission in ROLES_INTERVENANTS:
        actions.append("TELECHARGER")
    if mission.statut in STATUTS_FIGES:
        return actions
    ligne = (
        FicheDeTest.all_objects.filter(pk=piece.fiche_id)
        .values_list("statut", "test__auditeur_id")
        .first()
    )
    if ligne is None:
        return actions
    statut, auditeur_id = ligne
    if (
        _redige(user, contexte, auditeur_id)
        and statut in EDITABLES
        and _statut_etape(mission, ETAPE_FICHES) in ACTIFS
    ):
        actions += ["MODIFIER", "RETIRER"]
    return actions
