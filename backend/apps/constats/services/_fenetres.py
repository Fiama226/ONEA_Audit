"""Fenêtres d'écriture des constats (XIV) et des réponses de l'audité (XV).

Ordre de verrouillage commun : mission, puis étape, puis entité (constat).
"""

from uuid import UUID

from apps.core.exceptions import RegleMetierError
from apps.missions.etapes import romain
from apps.missions.exceptions import EtapeCloseError
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.travaux import verrouiller_travaux

from ..gardes import ETAPE_CONSTATS, ETAPE_REUNION_CLOTURE

ACTIFS: frozenset[str] = frozenset({StatutEtape.EN_COURS, StatutEtape.RENVOYEE})
MSG_XIV = "Commencez l'étape XIV pour rédiger les constats."


def verrouiller_etape(mission_id: UUID, numero: int) -> str | None:
    """Verrouille la ligne de l'étape (transaction requise) et renvoie son statut."""
    ligne = (
        EtapeMission.objects.select_for_update()
        .filter(mission_id=mission_id, numero=numero)
        .values_list("statut", flat=True)
        .first()
    )
    return None if ligne is None else str(ligne)


def ouvrir_xiv(mission: Mission) -> Mission:
    """Mission puis étape XIV verrouillées ; XIV doit être en cours ou renvoyée."""
    mission = verrouiller_travaux(mission)
    statut = verrouiller_etape(mission.pk, ETAPE_CONSTATS)
    if statut in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError(romain(ETAPE_CONSTATS))
    if statut not in ACTIFS:
        raise RegleMetierError(MSG_XIV)
    return mission


def ouvrir_xv(mission: Mission) -> Mission:
    """Mission puis étape XV verrouillées ; XV ne doit pas être close."""
    mission = verrouiller_travaux(mission)
    statut = verrouiller_etape(mission.pk, ETAPE_REUNION_CLOTURE)
    if statut in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError(romain(ETAPE_REUNION_CLOTURE))
    return mission
