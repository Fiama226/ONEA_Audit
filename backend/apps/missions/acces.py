"""Droits fondés sur les rôles uniquement (D4) ; l'état de la mission est géré ailleurs."""

from django.db.models import Q, QuerySet

from apps.users.models import Role, User

from .etapes import JALONS, JALONS_DELEGABLES
from .models import (
    ROLES_INTERVENANTS,
    DeclarationIndependance,
    Mission,
    RoleMission,
    StatutMission,
)


def role_dans_mission(user: User, mission: Mission) -> str | None:
    return (
        mission.affectations.filter(utilisateur=user).values_list("role_mission", flat=True).first()
    )


def est_intervenant(user: User, mission: Mission) -> bool:
    return role_dans_mission(user, mission) in ROLES_INTERVENANTS


def est_chef(user: User, mission: Mission) -> bool:
    return role_dans_mission(user, mission) == RoleMission.CHEF_MISSION


def est_superviseur(user: User, mission: Mission) -> bool:
    return role_dans_mission(user, mission) == RoleMission.SUPERVISEUR


def declaration_levee(user: User, mission: Mission) -> bool:
    declaration = DeclarationIndependance.objects.filter(
        affectation__mission=mission,
        affectation__utilisateur=user,
        affectation__deleted_at__isnull=True,
    ).first()
    return declaration is not None and declaration.levee


def peut_contribuer(user: User, mission: Mission) -> bool:
    if user.role == Role.RAI:
        return True
    return est_intervenant(user, mission) and declaration_levee(user, mission)


def peut_valider_jalon(user: User, mission: Mission, numero: int) -> bool:
    if numero not in JALONS:
        return False
    if user.role == Role.RAI:
        return True
    return (
        numero in JALONS_DELEGABLES
        and est_superviseur(user, mission)
        and declaration_levee(user, mission)
    )


def missions_visibles(user: User) -> QuerySet[Mission]:
    if user.role == Role.RAI:
        return Mission.objects.all()
    if user.role == Role.AUDITEUR:
        return Mission.objects.filter(
            ~Q(statut=StatutMission.BROUILLON),
            affectations__utilisateur=user,
            affectations__deleted_at__isnull=True,
            affectations__role_mission__in=ROLES_INTERVENANTS,
        ).distinct()
    if user.role == Role.AUDITE:
        return Mission.objects.filter(
            ordre_mission_emis_le__isnull=False,
            affectations__utilisateur=user,
            affectations__deleted_at__isnull=True,
            affectations__role_mission=RoleMission.AUDITE,
        ).distinct()
    return Mission.objects.none()
