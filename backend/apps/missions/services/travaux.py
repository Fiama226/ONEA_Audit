"""Garde commune aux écritures de travaux (réunions, entretiens, risques de mission)."""

from apps.core.exceptions import RegleMetierError

from ..gardes import verrouiller_mission
from ..models import Mission, StatutMission

STATUTS_TRAVAUX: frozenset[str] = frozenset(
    {
        StatutMission.PLANIFIEE,
        StatutMission.EN_PLANIFICATION,
        StatutMission.EN_ACCOMPLISSEMENT,
        StatutMission.EN_COMMUNICATION,
    }
)


def verrouiller_travaux(mission: Mission) -> Mission:
    """Verrouille la mission (transaction requise) ; refuse si elle est figée ou pas planifiée."""
    verrouillee = verrouiller_mission(mission)
    if verrouillee.statut not in STATUTS_TRAVAUX:
        raise RegleMetierError("Les travaux commencent une fois la mission planifiée.")
    return verrouillee
