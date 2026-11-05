"""Contrôles de livrables de l'étape XIV (D12 du plan du lot 6)."""

from apps.accomplissement.models import ConclusionTest, FicheDeTest, StatutFiche
from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from .models import Constat, ReponseAudite, StatutConstat


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


def _constats_non_valides(etape: EtapeMission) -> list[str]:
    restants = (
        Constat.objects.filter(mission_id=etape.mission_id)
        .exclude(statut=StatutConstat.VALIDE)
        .order_by("numero")
        .values_list("reference", flat=True)
    )
    return [f"Le constat {reference} n'est pas validé." for reference in restants]


def controle_positions_audite(etape: EtapeMission) -> list[str]:
    """XIV (fiche IFACI « observations validées avec les audités ») : chaque constat validé
    porte la position de l'audité (accord, ou désaccord motivé) sur sa version courante."""
    constats = Constat.objects.filter(
        mission_id=etape.mission_id, statut=StatutConstat.VALIDE
    ).order_by("numero")
    reponses = set(
        ReponseAudite.objects.filter(mission_id=etape.mission_id).values_list("constat_id", "cycle")
    )
    return [
        f"L'audité n'a pas donné sa position sur le constat {c.reference}."
        for c in constats
        if (c.pk, c.cycle) not in reponses
    ]


CONTROLES_ETAPE: dict[int, list[Controle]] = {14: [_constat_valide, _constats_non_valides]}
