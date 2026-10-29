"""Contrôles de livrables des étapes XII et XIII (D12 du plan du lot 6).

Seuls les tests au statut PREVU comptent : un test abandonné (avec motif) est hors contrôle.
"""

from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from ..models import FicheDeTest, StatutFiche, StatutTest, TestPrevu


def _tests_actifs(etape: EtapeMission) -> list[TestPrevu]:
    return list(
        TestPrevu.objects.filter(mission_id=etape.mission_id, statut=StatutTest.PREVU).order_by(
            "numero"
        )
    )


def _tests_sans_statut(etape: EtapeMission, acceptes: set[str]) -> list[str]:
    statuts = dict(
        FicheDeTest.objects.filter(mission_id=etape.mission_id).values_list("test_id", "statut")
    )
    return [t.code for t in _tests_actifs(etape) if statuts.get(t.pk) not in acceptes]


def _fiches_soumises(etape: EtapeMission) -> str | None:
    codes = _tests_sans_statut(etape, {StatutFiche.SOUMIS, StatutFiche.VALIDE})
    if not codes:
        return None
    return f"Tests sans fiche soumise : {len(codes)} ({', '.join(codes)})."


def _fiches_validees(etape: EtapeMission) -> str | None:
    codes = _tests_sans_statut(etape, {StatutFiche.VALIDE})
    if not codes:
        return None
    return f"Fiches non validées : {len(codes)} ({', '.join(codes)})."


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    12: [_fiches_soumises],
    13: [_fiches_validees],
}
