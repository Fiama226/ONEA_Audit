"""Contrôles de livrables des étapes V et VI (D13)."""

from apps.missions.models import EtapeMission, StatutEtape
from apps.missions.services.livrables import Controle

from ..models import LigneMARC
from ..services.marc import risques_non_couverts

MSG_MATRICE_VIDE = "La matrice d'analyse des risques et contrôles est vide."
MSG_V_NON_TERMINEE = "Terminez l'étape V avant de soumettre le référentiel d'audit."


def _matrice_non_vide(etape: EtapeMission) -> str | None:
    if LigneMARC.objects.filter(mission_id=etape.mission_id).exists():
        return None
    return MSG_MATRICE_VIDE


def _lignes_evaluees(etape: EtapeMission) -> str | None:
    n = LigneMARC.objects.filter(mission_id=etape.mission_id, evaluation="").count()
    return f"Lignes de la matrice sans évaluation de la conception : {n}." if n else None


def _risques_couverts(etape: EtapeMission) -> str | None:
    codes = risques_non_couverts(etape.mission)
    if not codes:
        return None
    return f"Risques moyens ou élevés sans contrôle analysé : {', '.join(codes)}"


def _v_terminee(etape: EtapeMission) -> str | None:
    statut = (
        EtapeMission.objects.filter(mission_id=etape.mission_id, numero=5)
        .values_list("statut", flat=True)
        .first()
    )
    return None if statut == StatutEtape.TERMINEE else MSG_V_NON_TERMINEE


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    5: [_matrice_non_vide, _lignes_evaluees, _risques_couverts],
    6: [_v_terminee, _matrice_non_vide],
}
