"""Contrôles de livrables des étapes XII et XIII (D12 du plan du lot 6).

Messages exacts de D12, un par test concerné, dans l'ordre des tests (un contrôle renvoie une
seule chaîne : les phrases sont jointes par une espace). Seuls les tests PREVU comptent pour
XII ; un test abandonné (avec motif) est hors contrôle. XIII porte sur les fiches actives.
"""

from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from ..models import FicheDeTest, StatutFiche, StatutTest, TestPrevu


def _statuts_fiches(etape: EtapeMission) -> dict[object, str]:
    return dict(
        FicheDeTest.objects.filter(mission_id=etape.mission_id).values_list("test_id", "statut")
    )


def _fiches_soumises(etape: EtapeMission) -> str | None:
    """XII : test sans fiche, ou fiche non soumise (un message D12 par test)."""
    statuts = _statuts_fiches(etape)
    messages: list[str] = []
    tests = TestPrevu.objects.filter(mission_id=etape.mission_id, statut=StatutTest.PREVU)
    for test in tests.order_by("numero"):
        statut = statuts.get(test.pk)
        if statut is None:
            messages.append(f"Le test {test.code} n'a pas de fiche.")
        elif statut not in (StatutFiche.SOUMIS, StatutFiche.VALIDE):
            messages.append(f"La fiche du test {test.code} n'est pas soumise.")
    return " ".join(messages) or None


def _fiches_validees(etape: EtapeMission) -> str | None:
    """XIII : « La fiche du test {code} n'est pas validée. » (toutes les fiches actives)."""
    fiches = FicheDeTest.objects.filter(mission_id=etape.mission_id).exclude(
        statut=StatutFiche.VALIDE
    )
    codes = fiches.order_by("test__numero").values_list("test__code", flat=True)
    return " ".join(f"La fiche du test {code} n'est pas validée." for code in codes) or None


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    12: [_fiches_soumises],
    13: [_fiches_validees],
}
