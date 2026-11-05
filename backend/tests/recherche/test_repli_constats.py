"""Règle de gouvernance « repli de la recherche » : missions seules, ou missions et constats."""

from typing import Any

import pytest

from apps.gouvernance import regles_gouvernance as rg
from apps.recherche.client import Hit
from apps.recherche.exceptions import RechercheIndisponibleError
from apps.recherche.services import rechercher
from apps.users.models import User
from tests.regles import regler

pytestmark = pytest.mark.django_db


@pytest.fixture
def panne(monkeypatch: pytest.MonkeyPatch) -> None:
    class Panne:
        def rechercher(self, *a: Any, **k: Any) -> list[Hit]:
            raise RechercheIndisponibleError

    monkeypatch.setattr("apps.recherche.services.moteur", lambda: Panne())


def test_default_fallback_ignores_findings(
    index_peuple: dict[str, str], auditeur_mission: User, panne: None
) -> None:
    res = rechercher(auditeur_mission, "Rapprochement bancaire")
    assert res.degrade is True
    assert all(h.type == "MISSION" for h in res.resultats)
    with pytest.raises(RechercheIndisponibleError):
        rechercher(auditeur_mission, "Rapprochement bancaire", types=["CONSTAT"])


def test_extended_fallback_finds_findings_within_rights(
    index_peuple: dict[str, str], auditeur_mission: User, audite_affecte: User, panne: None
) -> None:
    regler(rg.SEARCH_FALLBACK, scope="MISSIONS_AND_FINDINGS")
    res = rechercher(auditeur_mission, "Rapprochement bancaire")
    assert res.degrade is True
    assert {h.id for h in res.resultats} == set(index_peuple.values())
    # L'audité ne lit que le constat soumis, comme avec le moteur.
    ids = {h.id for h in rechercher(audite_affecte, "Rapprochement", types=["CONSTAT"]).resultats}
    assert ids == {index_peuple["CONSTAT-soumis"]}


def test_extended_fallback_still_refuses_other_types(
    index_peuple: dict[str, str], auditeur_mission: User, panne: None
) -> None:
    regler(rg.SEARCH_FALLBACK, scope="MISSIONS_AND_FINDINGS")
    with pytest.raises(RechercheIndisponibleError):
        rechercher(auditeur_mission, "Rapprochement", types=["DOCUMENT"])
