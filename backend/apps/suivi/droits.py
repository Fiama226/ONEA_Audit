"""Droits du suivi : section visibilité (R11).

- RAI : tout ; DG : lecture seule ; AUDITEUR et AUDITE : leurs missions (`missions_visibles`) ;
  ADMIN : rien.
- Le suivi n'est lisible que pour les missions dont le rapport est déjà diffusé.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from apps.missions.acces import missions_visibles, role_dans_mission
from apps.missions.models import Mission, StatutMission
from apps.users.models import Role, User

from .models import PreuveMiseEnOeuvre, SuiviAction

STATUTS_MISSION_SUIVI: frozenset[str] = frozenset(
    {StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI, StatutMission.CLOTUREE}
)


def missions_suivi_visibles(user: User) -> QuerySet[Mission]:
    if user.role in (Role.RAI, Role.DG):
        base = Mission.objects.all()
    elif user.role in (Role.AUDITEUR, Role.AUDITE):
        base = missions_visibles(user)
    else:
        return Mission.objects.none()
    return base.filter(statut__in=STATUTS_MISSION_SUIVI)


def suivis_visibles(user: User) -> QuerySet[SuiviAction]:
    return SuiviAction.objects.filter(mission__in=missions_suivi_visibles(user).values("pk"))


# --- preuves et reports (T6) ---------------------------------------------------------------
MSG_DROIT_SUIVI = "Vous n'avez pas le droit d'effectuer cette opération sur cette action."
MSG_DROIT_DECISION = "Seul le RAI peut décider d'une demande de report."
MSG_DROIT_PREUVE = "Vous n'avez pas le droit de consulter cette preuve."


def peut_operer_pour_responsable(user: User, suivi: SuiviAction) -> bool:
    """Responsable courant de l'action, ou RAI (saisie pour son compte, R3)."""
    if user.role == Role.RAI:
        return True
    return user.role == Role.AUDITE and suivi.responsable_id == user.pk


def exiger_operer_pour_responsable(user: User, suivi: SuiviAction) -> None:
    if not peut_operer_pour_responsable(user, suivi):
        raise PermissionDenied(MSG_DROIT_SUIVI)


def exiger_decideur_report(user: User) -> None:
    if user.role != Role.RAI:
        raise PermissionDenied(MSG_DROIT_DECISION)


def peut_telecharger_preuve(user: User, preuve: PreuveMiseEnOeuvre) -> bool:
    """RAI, auditeurs et audités affectés à la mission. DG et ADMIN : jamais (R8, R11)."""
    mission = preuve.mission
    if mission.statut not in STATUTS_MISSION_SUIVI:
        return False
    if user.role == Role.RAI:
        return True
    if user.role in (Role.AUDITEUR, Role.AUDITE):
        return role_dans_mission(user, mission) is not None
    return False


def exiger_telechargement_preuve(user: User, preuve: PreuveMiseEnOeuvre) -> None:
    if not peut_telecharger_preuve(user, preuve):
        raise PermissionDenied(MSG_DROIT_PREUVE)
