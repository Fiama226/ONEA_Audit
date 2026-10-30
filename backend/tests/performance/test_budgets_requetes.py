"""Budgets de requetes SQL (D10, tache 23 du lot 9) sur chaque route GET du schema OpenAPI.

- une route absente de `BUDGETS_REQUETES` echoue ;
- le nombre de requetes est inferieur ou egal au budget ;
- il est identique pour des pages de 10 et de 50 elements (aucun N+1 sur les listes).
"""

from typing import Any

import pytest

from .budgets import BUDGETS_REQUETES
from .conftest import client_pour, routes_get
from .outils import DEFAUT, ROLES, Resolveur, mesurer

ROUTES = routes_get()


def test_budgets_sans_route_orpheline() -> None:
    """Un budget qui ne correspond plus a aucune route est supprime avec elle."""
    assert set(BUDGETS_REQUETES) <= set(ROUTES)


@pytest.mark.parametrize("chemin", sorted(ROUTES))
def test_budget_requetes(
    chemin: str, volumetrie: dict[str, Any], db: None, fake_keycloak: Any
) -> None:
    assert chemin in BUDGETS_REQUETES, f"Route sans budget de requetes : {chemin}"
    client = client_pour(ROLES.get(chemin, DEFAUT))
    mesures = {
        taille: mesurer(client, Resolveur(client, volumetrie, ROUTES, taille).url(chemin))
        for taille in (10, 50)
    }
    for taille, mesure in mesures.items():
        assert mesure.statut < 500, f"{chemin} (page {taille}) : HTTP {mesure.statut}"
        assert mesure.requetes <= BUDGETS_REQUETES[chemin], (
            f"{chemin} (page {taille}) : {mesure.requetes} requetes > budget "
            f"{BUDGETS_REQUETES[chemin]}"
        )
    assert mesures[10].requetes == mesures[50].requetes, (
        f"{chemin} : le nombre de requetes depend de la taille de page "
        f"({mesures[10].requetes} pour 10, {mesures[50].requetes} pour 50)"
    )
