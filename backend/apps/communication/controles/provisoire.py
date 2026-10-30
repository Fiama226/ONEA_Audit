"""Contrôles de livrables de l'étape XV (D15 du plan du lot 7).

Les contrôles de l'étape XVI (plan d'actions) sont enregistrés par l'app `recommandations`.
"""

from apps.constats.models import Constat, StatutConstat
from apps.missions.models import EtapeMission, TypeReunion
from apps.missions.services.livrables import Controle, _reunion_tenue

from ..models import RapportProvisoire

MSG_TRANSMETTRE = "Transmettez le rapport provisoire aux audités."

_reunion_cloture = _reunion_tenue(TypeReunion.CLOTURE, "de clôture")


def _provisoire_transmis(etape: EtapeMission) -> str | None:
    """Exigé seulement si au moins un constat est VALIDE (sinon pas de rapport provisoire)."""
    if not Constat.objects.filter(
        mission_id=etape.mission_id, statut=StatutConstat.VALIDE
    ).exists():
        return None
    transmis = RapportProvisoire.objects.filter(mission_id=etape.mission_id).exists()
    return None if transmis else MSG_TRANSMETTRE


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    15: [_reunion_cloture, _provisoire_transmis],
}
