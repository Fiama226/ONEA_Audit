"""Rédaction du rapport final (étape XVII, D4, D5) : création préremplie, sections, aperçu."""

from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max

from apps.analyse.services.objectifs import code_objectif, objectifs_retenus
from apps.analyse.services.orientation import obtenir_rapport
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, relire
from apps.missions.acces import peut_contribuer
from apps.missions.models import Mission, StatutMission
from apps.users.models import User

from ..exceptions import RapportFigeError
from ..gardes import CHAMPS_REDACTION, STATUTS_REDACTION
from ..models import Rapport, StatutRapport, TypeEvenementRapport
from ._ecriture import journaliser, ouvrir_mission
from .assemblage import assembler

MSG_DROIT = "Seule l'équipe d'audit peut rédiger le rapport."
MSG_RAPPORT_EXISTANT = "Un rapport existe déjà pour cette mission."
MSG_HORS_COMMUNICATION = "Le rapport se rédige pendant la phase de communication de la mission."


def _objectifs_texte(mission: Mission) -> str:
    lignes = [mission.objectifs.strip()] if mission.objectifs.strip() else []
    lignes += [f"{code_objectif(o)} : {o.libelle}" for o in objectifs_retenus(mission)]
    return "\n".join(lignes)


@transaction.atomic
def creer_rapport(mission: Mission, *, by: User) -> Rapport:
    """Crée le rapport initial, prérempli (D5) ; un seul rapport actif par mission."""
    if not peut_contribuer(by, mission):
        raise PermissionDenied(MSG_DROIT)
    mission = ouvrir_mission(mission)
    if mission.statut != StatutMission.EN_COMMUNICATION:
        raise RegleMetierError(MSG_HORS_COMMUNICATION)
    if Rapport.objects.filter(mission=mission).exclude(statut=StatutRapport.REMPLACE).exists():
        raise RegleMetierError(MSG_RAPPORT_EXISTANT)
    orientation = obtenir_rapport(mission)
    dernier = Rapport.all_objects.filter(mission=mission).aggregate(m=Max("numero_version"))["m"]
    rapport = Rapport(
        mission=mission,
        numero_version=(dernier or 0) + 1,
        contexte=orientation.contexte if orientation else "",
        methodologie=orientation.approche if orientation else "",
        objectifs_texte=_objectifs_texte(mission),
        perimetre_texte=mission.perimetre,
    )
    enregistrer(rapport, by=by, creation=True)
    journaliser(rapport, TypeEvenementRapport.CREE, by=by)
    return rapport


@transaction.atomic
def modifier_rapport(rapport: Rapport, *, by: User, **sections: Any) -> Rapport:
    """Modifie les sections saisies (D5) ; seulement en BROUILLON ou RENVOYE."""
    mission = ouvrir_mission(rapport.mission_id)
    if not peut_contribuer(by, mission):
        raise PermissionDenied(MSG_DROIT)
    rapport = relire(rapport)
    if rapport.statut not in STATUTS_REDACTION:
        raise RapportFigeError(str(StatutRapport(rapport.statut).label).lower())
    appliquer(rapport, sections, set(CHAMPS_REDACTION))
    enregistrer(rapport, by=by)
    return rapport


def apercu(rapport: Rapport) -> dict[str, Any]:
    """Aperçu du rapport final (non figé) : l'assemblage complet du moment."""
    return assembler(rapport, provisoire=False)
