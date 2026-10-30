"""Clôture de la mission (R7) : toutes les actions du plan sont closes."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet

from apps.core.audit import actor_scope
from apps.core.services import refuser
from apps.missions.gardes import verrouiller_mission
from apps.missions.models import Mission, StatutMission
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.users.models import Role, User

from .. import sources
from ..models import STATUTS_CLOS, EvenementSuivi, SuiviAction, TypeEvenementSuivi
from . import commun
from .ouverture import STATUTS_OUVRABLES


def _non_closes(mission: Mission) -> int:
    """Suivis non clos, et actions éligibles du plan dont le suivi n'est pas encore ouvert."""
    ouverts = SuiviAction.objects.filter(mission=mission).exclude(statut__in=STATUTS_CLOS).count()
    suivies = set(
        SuiviAction.all_objects.filter(mission=mission).values_list("action_id", flat=True)
    )
    sans_suivi = sum(
        1
        for a in sources.actions_du_plan(mission)
        if a.id not in suivies and a.responsable_id is not None and a.echeance is not None
    )
    return ouverts + sans_suivi


def missions_a_cloturer() -> QuerySet[Mission]:
    """Missions diffusées dont tous les suivis sont clos (y compris sans aucune action)."""
    ouvert = SuiviAction.objects.filter(mission=OuterRef("pk")).exclude(statut__in=STATUTS_CLOS)
    return Mission.objects.filter(statut__in=STATUTS_OUVRABLES).filter(~Exists(ouvert))


def proposer_cloture_si_complete(mission: Mission) -> bool:
    """Prévient le RAI, une fois par cycle, quand la dernière action vient de se clore."""
    if mission.statut not in STATUTS_OUVRABLES or _non_closes(mission):
        return False
    reouvertures = EvenementSuivi.objects.filter(
        suivi__mission=mission, type=TypeEvenementSuivi.ROUVERTE
    ).count()
    notifier(
        commun.rai_actifs(),
        type=TypeNotification.MISSION_A_CLOTURER,
        titre="Mission à clôturer",
        message=f"Toutes les actions de la mission {mission.reference} sont closes.",
        lien=f"/missions/{mission.pk}",
        objet=mission,
        cle=f"MISSION_A_CLOTURER:{mission.pk}:{reouvertures}",
    )
    return True


@transaction.atomic
def cloturer_mission(mission: Mission, *, by: User, commentaire: str = "") -> Mission:  # noqa: ARG001
    if by.role != Role.RAI:
        raise PermissionDenied("Seul le responsable de l'audit interne clôture une mission.")
    verrouillee = verrouiller_mission(mission)
    if verrouillee.statut not in STATUTS_OUVRABLES:
        libelle = StatutMission(verrouillee.statut).label
        raise refuser(f"Cette opération n'est pas possible pour une mission « {libelle} ».")
    restantes = _non_closes(verrouillee)
    if restantes:
        raise refuser(f"{restantes} action(s) du plan ne sont pas closes.")
    verrouillee.statut = StatutMission.CLOTUREE
    verrouillee.updated_by = by
    with actor_scope(by):
        verrouillee.save(update_fields=["statut", "updated_by", "updated_at"])
    return verrouillee
