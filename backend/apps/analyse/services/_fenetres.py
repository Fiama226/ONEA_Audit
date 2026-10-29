"""Fenêtres d'écriture de l'étape III et du QCI (D4 du plan du lot 5)."""

from apps.missions.gardes import exiger_etape_ouverte
from apps.missions.models import Mission
from apps.missions.services.travaux import verrouiller_travaux

from .. import gardes
from ..models import TypeQuestionnaire

MSG_III = "Commencez l'étape III pour documenter la prise de connaissance."
MSG_V = "Commencez l'étape V pour constituer le référentiel d'audit."


def ouvrir_iii(mission: Mission) -> Mission:
    """Verrouille la mission puis exige III en cours ou renvoyée."""
    mission = verrouiller_travaux(mission)
    exiger_etape_ouverte(mission.pk, 3)
    gardes.exiger_actives(mission.pk, une_de=(3,), message=MSG_III)
    return mission


def ouvrir_v(mission: Mission) -> Mission:
    """Verrouille la mission puis exige la fenêtre MARC / QCI (V ou VI en cours)."""
    mission = verrouiller_travaux(mission)
    gardes.exiger_fenetre_marc(mission.pk)
    gardes.exiger_actives(mission.pk, une_de=(5, 6), message=MSG_V)
    return mission


def ouvrir_pour_type(mission: Mission, type_: str) -> Mission:
    if type_ == TypeQuestionnaire.PRISE_CONNAISSANCE:
        return ouvrir_iii(mission)
    return ouvrir_v(mission)
