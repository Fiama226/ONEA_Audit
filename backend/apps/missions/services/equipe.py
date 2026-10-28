"""Équipe de la mission : affectations, déclarations associées, remplacement du chef (D11)."""

from django.db import transaction
from django.db.models import QuerySet

from apps.core.services import enregistrer, refuser, relire
from apps.users.models import Role, User

from ..gardes import verrouiller_mission
from ..models import (
    ROLES_INTERVENANTS,
    AffectationMission,
    DeclarationIndependance,
    Mission,
    RoleMission,
    StatutMission,
)

MSG_INTERVENANT = "Un intervenant doit avoir le rôle Auditeur interne."
MSG_AUDITE = "Un audité doit avoir le rôle Audité."
MSG_CHEF_EXISTE = "Cette mission a déjà un chef de mission."
MSG_SUPERVISEUR_EXISTE = "Cette mission a déjà un superviseur."
MSG_SUPERVISEUR_CHEF = "Le superviseur ne peut pas être le chef de mission."
MSG_DEJA_AFFECTE = "Cet utilisateur est déjà affecté à la mission."
MSG_CHEF_RETRAIT = "Le chef de mission ne peut être retiré qu'en le remplaçant."


def _creer_declaration(affectation: AffectationMission, by: User) -> None:
    enregistrer(DeclarationIndependance(affectation=affectation), by=by, creation=True)


def _actives(mission: Mission) -> QuerySet[AffectationMission]:
    return AffectationMission.objects.filter(mission=mission).select_related("utilisateur")


@transaction.atomic
def affecter(
    mission: Mission, *, utilisateur: User, role_mission: str, by: User
) -> AffectationMission:
    mission = verrouiller_mission(mission)
    if role_mission not in RoleMission.values:
        msg = "Rôle dans la mission inconnu."
        raise refuser(msg, role_mission=msg)
    if not utilisateur.is_active:
        msg = "Cet utilisateur est désactivé."
        raise refuser(msg, utilisateur=msg)
    if role_mission == RoleMission.AUDITE:
        if utilisateur.role != Role.AUDITE:
            raise refuser(MSG_AUDITE, utilisateur=MSG_AUDITE)
    elif utilisateur.role != Role.AUDITEUR:
        raise refuser(MSG_INTERVENANT, utilisateur=MSG_INTERVENANT)

    existantes = list(_actives(mission))
    roles = {a.utilisateur_id: a.role_mission for a in existantes}
    ancien = roles.get(utilisateur.pk)
    if {ancien, role_mission} == {RoleMission.CHEF_MISSION, RoleMission.SUPERVISEUR}:
        raise refuser(MSG_SUPERVISEUR_CHEF, role_mission=MSG_SUPERVISEUR_CHEF)
    if ancien is not None:
        raise refuser(MSG_DEJA_AFFECTE, utilisateur=MSG_DEJA_AFFECTE)
    if role_mission == RoleMission.CHEF_MISSION and RoleMission.CHEF_MISSION in roles.values():
        raise refuser(MSG_CHEF_EXISTE, role_mission=MSG_CHEF_EXISTE)
    if role_mission == RoleMission.SUPERVISEUR and RoleMission.SUPERVISEUR in roles.values():
        raise refuser(MSG_SUPERVISEUR_EXISTE, role_mission=MSG_SUPERVISEUR_EXISTE)

    affectation = AffectationMission(
        mission=mission, utilisateur=utilisateur, role_mission=role_mission
    )
    enregistrer(affectation, by=by, creation=True)
    if role_mission in ROLES_INTERVENANTS:
        _creer_declaration(affectation, by)
    return affectation


@transaction.atomic
def desaffecter(affectation: AffectationMission, *, by: User) -> None:
    mission = verrouiller_mission(affectation.mission_id)
    affectation = relire(affectation)
    if affectation.deleted_at is not None:
        return
    if affectation.role_mission == RoleMission.CHEF_MISSION and mission.statut not in (
        StatutMission.BROUILLON,
        StatutMission.PLANIFIEE,
    ):
        raise refuser(MSG_CHEF_RETRAIT, role_mission=MSG_CHEF_RETRAIT)
    declaration = DeclarationIndependance.objects.filter(affectation=affectation).first()
    if declaration is not None:
        declaration.soft_delete(by)
    affectation.soft_delete(by)


@transaction.atomic
def remplacer_chef(mission: Mission, *, utilisateur: User, by: User) -> AffectationMission:
    mission = verrouiller_mission(mission)
    if utilisateur.role != Role.AUDITEUR or not utilisateur.is_active:
        raise refuser(MSG_INTERVENANT, utilisateur=MSG_INTERVENANT)
    existantes = list(_actives(mission).select_for_update(of=("self",)))
    ancien_chef = next((a for a in existantes if a.role_mission == RoleMission.CHEF_MISSION), None)
    if ancien_chef is None:
        msg = "Cette mission n'a pas de chef de mission à remplacer."
        raise refuser(msg, utilisateur=msg)
    if ancien_chef.utilisateur_id == utilisateur.pk:
        msg = "Cet utilisateur est déjà le chef de la mission."
        raise refuser(msg, utilisateur=msg)
    courante = next((a for a in existantes if a.utilisateur_id == utilisateur.pk), None)
    if courante is not None and courante.role_mission == RoleMission.SUPERVISEUR:
        raise refuser(MSG_SUPERVISEUR_CHEF, utilisateur=MSG_SUPERVISEUR_CHEF)

    ancien_chef.role_mission = RoleMission.AUDITEUR
    enregistrer(ancien_chef, by=by)
    if courante is not None:
        courante.role_mission = RoleMission.CHEF_MISSION
        enregistrer(courante, by=by)
        return courante
    nouveau = AffectationMission(
        mission=mission, utilisateur=utilisateur, role_mission=RoleMission.CHEF_MISSION
    )
    enregistrer(nouveau, by=by, creation=True)
    _creer_declaration(nouveau, by)
    return nouveau


def audites_par_defaut(mission: Mission) -> QuerySet[User]:
    """Audités actifs rattachés à une entité de la mission (D5) : valeur proposée au RAI."""
    codes = mission.entites.values_list("code", flat=True)
    return User.objects.filter(
        role=Role.AUDITE, is_active=True, direction_code__in=list(codes)
    ).order_by("last_name", "first_name", "username")
