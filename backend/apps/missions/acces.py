"""Droits fondés sur les rôles uniquement (D4) ; l'état de la mission est géré ailleurs."""

from uuid import UUID

from django.db.models import Q, QuerySet

from apps.core.memoire import memoise
from apps.referentiel.models import Direction
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
    """Rôle de l'utilisateur dans la mission ; mémorisé dans un bloc `memo_lecture()`."""
    return memoise(
        ("role_dans_mission", user.pk, mission.pk),
        lambda: (
            mission.affectations.filter(utilisateur=user)
            .values_list("role_mission", flat=True)
            .first()
        ),
    )


def est_intervenant(user: User, mission: Mission) -> bool:
    return role_dans_mission(user, mission) in ROLES_INTERVENANTS


def est_chef(user: User, mission: Mission) -> bool:
    return role_dans_mission(user, mission) == RoleMission.CHEF_MISSION


def est_superviseur(user: User, mission: Mission) -> bool:
    return role_dans_mission(user, mission) == RoleMission.SUPERVISEUR


def declaration_levee(user: User, mission: Mission) -> bool:
    """Déclaration d'indépendance levée ; mémorisée dans un bloc `memo_lecture()`."""

    def calcul() -> bool:
        declaration = DeclarationIndependance.objects.filter(
            affectation__mission=mission,
            affectation__utilisateur=user,
            affectation__deleted_at__isnull=True,
        ).first()
        return declaration is not None and declaration.levee

    return memoise(("declaration_levee", user.pk, mission.pk), calcul)


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


def peut_valider_travaux(user: User, mission: Mission) -> bool:
    """Validation des travaux (jalon XIII) : RAI, ou superviseur à déclaration levée."""
    return peut_valider_jalon(user, mission, 13)


def est_responsable_entite(user: User, mission: Mission, entite_id: UUID | str) -> bool:
    """AUDITE affecté (affectation active) dont la direction est celle de l'entité."""
    if user.role != Role.AUDITE or not user.direction_code:
        return False
    if role_dans_mission(user, mission) != RoleMission.AUDITE:
        return False
    return Direction.objects.filter(pk=entite_id, code=user.direction_code).exists()


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
