"""Écritures communes aux services du rapport : fenêtre, événements, sauvegarde de transition.

Ordre de verrouillage commun : mission, puis étape, puis entité (rapport).
"""

from uuid import UUID

from django.db import transaction

from apps.core.audit import actor_scope
from apps.missions.gardes import verrouiller_mission
from apps.missions.models import EtapeMission, Mission, StatutMission
from apps.users.models import User

from ..models import EvenementRapport, Rapport

# Un rapport corrigé (D12) vit sous une mission RAPPORT_DIFFUSE.
MISSIONS_REDACTION: frozenset[str] = frozenset(
    {StatutMission.EN_COMMUNICATION, StatutMission.RAPPORT_DIFFUSE}
)


def verrouiller_etape(mission_id: UUID, numero: int) -> str | None:
    """Verrouille la ligne de l'étape (transaction requise) et renvoie son statut."""
    statut = (
        EtapeMission.objects.select_for_update()
        .filter(mission_id=mission_id, numero=numero)
        .values_list("statut", flat=True)
        .first()
    )
    return None if statut is None else str(statut)


def ouvrir_mission(mission: Mission | UUID) -> Mission:
    """Verrouille la mission (refuse si figée)."""
    return verrouiller_mission(mission)


def sauver_transition(rapport: Rapport, champs: list[str], *, by: User) -> None:
    """Sauvegarde limitée aux colonnes de la transition (liste blanche de `gardes`)."""
    rapport.updated_by = by
    with actor_scope(by), transaction.atomic():
        rapport.save(update_fields=[*champs, "updated_at", "updated_by"])


def journaliser(
    rapport: Rapport, type_: str, *, by: User, avant: str = "", motif: str = ""
) -> None:
    with actor_scope(by):
        EvenementRapport.journaliser(rapport, type_, par=by, motif=motif, statut_avant=avant)
