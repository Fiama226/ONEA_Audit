"""Contrat JSON d'une reponse de recherche (fixtures MSW, lot 8 T14)."""

from pathlib import Path

from apps.users.models import User
from tests.accomplissement.fixtures_api import client_de
from tests.contrat_forme import comparer

GOLDEN = Path(__file__).with_name("contrat_lot8.json")


def test_api_contrat_reponse_de_recherche(index_peuple: dict[str, str], rai: User) -> None:
    corps = client_de(rai).get("/api/v1/search/", {"q": "Rapprochement", "types": "CONSTAT"}).json()
    assert corps["resultats"]
    comparer(GOLDEN, "reponse", corps)
