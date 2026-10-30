"""Fenêtre d'écriture du plan d'actions (D8 du plan du lot 7).

Ordre de verrouillage commun : mission, puis étapes (XV, XVI), puis entité.
"""

from apps.constats.services._fenetres import ACTIFS, verrouiller_etape
from apps.core.exceptions import RegleMetierError
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import Mission
from apps.missions.services.travaux import verrouiller_travaux

from ..gardes import ETAPE_PLAN_ACTIONS

ETAPE_CLOTURE = 15
MSG_FENETRE = "Le plan d'actions se saisit pendant les étapes XV et XVI."


def fenetre_ouverte(statut_xv: str | None, statut_xvi: str | None) -> bool:
    """XVI non close, et XV non close (ébauche) ou XVI en cours."""
    if statut_xvi is None or statut_xvi in STATUTS_ETAPE_CLOSE:
        return False
    if statut_xvi in ACTIFS:
        return True
    return statut_xv is not None and statut_xv not in STATUTS_ETAPE_CLOSE


def ouvrir_plan(mission: Mission) -> Mission:
    """Mission puis étapes XV et XVI verrouillées ; la saisie doit être dans la fenêtre."""
    mission = verrouiller_travaux(mission)
    statut_xv = verrouiller_etape(mission.pk, ETAPE_CLOTURE)
    statut_xvi = verrouiller_etape(mission.pk, ETAPE_PLAN_ACTIONS)
    if not fenetre_ouverte(statut_xv, statut_xvi):
        raise RegleMetierError(MSG_FENETRE)
    return mission
