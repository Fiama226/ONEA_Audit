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
from ..notifications import notifier_affectation

MSG_INTERVENANT = "Un intervenant doit avoir le rôle Auditeur interne."
MSG_AUDITE = "Un audité doit avoir le rôle Audité."
MSG_CHEF_EXISTE = "Cette mission a déjà un chef de mission."
MSG_SUPERVISEUR_EXISTE = "Cette mission a déjà un superviseur."
MSG_SUPERVISEUR_CHEF = "Le superviseur ne peut pas être le chef de mission."
MSG_DEJA_AFFECTE = "Cet utilisateur est déjà affecté à la mission."
MSG_RESPONSABLE_AUDITE = "Seul un audité peut être désigné responsable de l'entité."
MSG_RESPONSABLE_DIRECTION = (
    "Cet audité n'a pas de direction renseignée : il ne peut pas être responsable de l'entité."
)
MSG_RESPONSABLE_EXISTE = (
    "Cette direction a déjà un responsable de l'entité dans cette mission. "
    "Retirez-lui d'abord cette désignation."
)
MSG_CHEF_RETRAIT = "Le chef de mission ne peut être retiré qu'en le remplaçant."


def _creer_declaration(affectation: AffectationMission, by: User) -> None:
    enregistrer(DeclarationIndependance(affectation=affectation), by=by, creation=True)


def _actives(mission: Mission) -> QuerySet[AffectationMission]:
    return AffectationMission.objects.filter(mission=mission).select_related("utilisateur")


def _controler_responsable(
    existantes: list[AffectationMission], utilisateur: User, role_mission: str
) -> None:
    """Un responsable de l'entité est un audité, avec une direction, unique pour cette direction."""
    erreur = "responsable_entite"
    if role_mission != RoleMission.AUDITE:
        raise refuser(MSG_RESPONSABLE_AUDITE, **{erreur: MSG_RESPONSABLE_AUDITE})
    if not utilisateur.direction_code:
        raise refuser(MSG_RESPONSABLE_DIRECTION, **{erreur: MSG_RESPONSABLE_DIRECTION})
    if any(
        a.responsable_entite
        and a.utilisateur_id != utilisateur.pk
        and a.utilisateur.direction_code == utilisateur.direction_code
        for a in existantes
    ):
        raise refuser(MSG_RESPONSABLE_EXISTE, **{erreur: MSG_RESPONSABLE_EXISTE})


@transaction.atomic
def definir_responsable_entite(
    affectation: AffectationMission, *, responsable: bool, by: User
) -> AffectationMission:
    """Désigne ou retire le responsable de l'entité (mission verrouillée, trace d'audit)."""
    verrouiller_mission(affectation.mission_id)
    affectation = relire(affectation)
    if responsable and not affectation.responsable_entite:
        existantes = list(_actives(affectation.mission).select_for_update(of=("self",)))
        _controler_responsable(existantes, affectation.utilisateur, affectation.role_mission)
    if affectation.responsable_entite != responsable:
        affectation.responsable_entite = responsable
        enregistrer(affectation, by=by)
    return affectation


@transaction.atomic
def affecter(
    mission: Mission,
    *,
    utilisateur: User,
    role_mission: str,
    by: User,
    responsable_entite: bool = False,
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
    if responsable_entite:
        _controler_responsable(existantes, utilisateur, role_mission)

    affectation = AffectationMission(
        mission=mission,
        utilisateur=utilisateur,
        role_mission=role_mission,
        responsable_entite=responsable_entite,
    )
    enregistrer(affectation, by=by, creation=True)
    if role_mission in ROLES_INTERVENANTS:
        _creer_declaration(affectation, by)
    notifier_affectation(affectation, by=by)
    return affectation


@transaction.atomic
def desaffecter(affectation: AffectationMission, *, by: User) -> None:
    mission = verrouiller_mission(affectation.mission_id)
    affectation = relire(affectation)
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
    if utilisateur.role != Role.AUDITEUR:
        raise refuser(MSG_INTERVENANT, utilisateur=MSG_INTERVENANT)
    if not utilisateur.is_active:
        msg = "Cet utilisateur est désactivé."
        raise refuser(msg, utilisateur=msg)
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
