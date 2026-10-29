"""Contrôles de livrables de l'étape XIV (D12 du plan du lot 6)."""

from apps.accomplissement.models import ConclusionTest, FicheDeTest, StatutFiche
from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from .models import Constat, StatutConstat


def _constat_valide(etape: EtapeMission) -> str | None:
    """Au moins un constat validé, sauf mission sans anomalie validée (hypothèse confirmée)."""
    constats = Constat.objects.filter(mission_id=etape.mission_id)
    if constats.filter(statut=StatutConstat.VALIDE).exists():
        return None
    anomalie = FicheDeTest.objects.filter(
        mission_id=etape.mission_id,
        statut=StatutFiche.VALIDE,
        conclusion=ConclusionTest.ANOMALIE,
    ).exists()
    return "Aucun constat n'est validé." if anomalie else None


def _constats_non_valides(etape: EtapeMission) -> str | None:
    restants = (
        Constat.objects.filter(mission_id=etape.mission_id)
        .exclude(statut=StatutConstat.VALIDE)
        .order_by("numero")
        .values_list("reference", flat=True)
    )
    refs = list(restants)
    if not refs:
        return None
    if len(refs) == 1:
        return f"Le constat {refs[0]} n'est pas validé."
    return "Constats non validés : " + ", ".join(refs) + "."


CONTROLES_ETAPE: dict[int, list[Controle]] = {14: [_constat_valide, _constats_non_valides]}
