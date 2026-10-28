import pytest

from apps.missions.etapes import (
    ETAPE_DE_REUNION,
    ETAPES,
    ETAPES_DE_PHASE,
    JALON_DE_PHASE,
    JALONS,
    JALONS_DELEGABLES,
    PHASE_DU_STATUT,
    etape,
    romain,
)
from apps.missions.models import Phase, StatutMission, TypeReunion


def test_registre_18_etapes_phases_et_jalons() -> None:
    assert [e.numero for e in ETAPES] == list(range(1, 19))
    for e in ETAPES:
        if e.numero <= 10:
            expected = Phase.PLANIFICATION
        elif e.numero <= 14:
            expected = Phase.ACCOMPLISSEMENT
        else:
            expected = Phase.COMMUNICATION
        assert e.phase == expected
        assert e.titre and e.objectif and e.livrables and e.acteurs
        assert e.jalon == (e.numero in {6, 10, 13, 18})
    assert JALONS == frozenset({6, 10, 13, 18})
    assert JALONS_DELEGABLES == frozenset({6, 10, 13})
    assert etape(4).titre == "Identifier et évaluer les risques"
    assert etape(4).romain == "IV"
    assert [romain(n) for n in (1, 9, 14, 18)] == ["I", "IX", "XIV", "XVIII"]


def test_lots_de_livrables() -> None:
    lots = {e.numero: e.lot_livrables for e in ETAPES}
    assert [n for n, lot in lots.items() if lot == 3] == [1, 2, 4, 11]
    assert [n for n, lot in lots.items() if lot == 5] == [3, 5, 6, 7]
    assert [n for n, lot in lots.items() if lot == 6] == [8, 9, 10, 12, 13, 14]
    assert [n for n, lot in lots.items() if lot == 7] == [15, 16, 17, 18]


def test_tables_de_correspondance() -> None:
    assert PHASE_DU_STATUT[StatutMission.EN_PLANIFICATION] is Phase.PLANIFICATION
    assert PHASE_DU_STATUT[StatutMission.EN_ACCOMPLISSEMENT] is Phase.ACCOMPLISSEMENT
    assert PHASE_DU_STATUT[StatutMission.EN_COMMUNICATION] is Phase.COMMUNICATION
    assert StatutMission.BROUILLON not in PHASE_DU_STATUT
    assert list(ETAPES_DE_PHASE[Phase.PLANIFICATION]) == list(range(1, 11))
    assert list(ETAPES_DE_PHASE[Phase.ACCOMPLISSEMENT]) == [11, 12, 13, 14]
    assert list(ETAPES_DE_PHASE[Phase.COMMUNICATION]) == [15, 16, 17, 18]
    assert JALON_DE_PHASE == {Phase.PLANIFICATION: 10, Phase.ACCOMPLISSEMENT: 13}
    assert ETAPE_DE_REUNION == {
        TypeReunion.OUVERTURE: 2,
        TypeReunion.LANCEMENT: 11,
        TypeReunion.CLOTURE: 15,
    }


def test_numero_inconnu() -> None:
    with pytest.raises(KeyError):
        etape(19)
