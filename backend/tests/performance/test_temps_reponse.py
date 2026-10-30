"""Temps de reponse (D10) : p95 de 20 appels <= 300 ms par route, base de volumetrie.

Marqueur `perf` : exclu par defaut (`pytest -m perf tests/performance`). Le seuil se regle par
la variable d'environnement PERF_P95_MS ; PERF_RAPPORT=<fichier> y ajoute une ligne par test.
"""

import os
import time
from typing import Any

import pytest

from .budgets import EXCLUES_TEMPS
from .conftest import client_pour, routes_get
from .outils import DEFAUT, ROLES, Resolveur

ROUTES = routes_get()
SEUIL_MS = float(os.environ.get("PERF_P95_MS", "300"))
APPELS = 20

pytestmark = pytest.mark.perf


@pytest.mark.parametrize("chemin", sorted(set(ROUTES) - EXCLUES_TEMPS))
def test_p95_route(chemin: str, volumetrie: dict[str, Any], db: None) -> None:
    client = client_pour(ROLES.get(chemin, DEFAUT))
    url = Resolveur(client, volumetrie, ROUTES).url(chemin)
    client.get(url)  # chauffe
    durees: list[float] = []
    for _ in range(APPELS):
        debut = time.perf_counter()
        client.get(url)
        durees.append((time.perf_counter() - debut) * 1000)
    durees.sort()
    p95 = durees[int(0.95 * APPELS) - 1]
    rapport = os.environ.get("PERF_RAPPORT")  # fichier CSV chemin;p95 (documentation)
    if rapport:
        with open(rapport, "a", encoding="utf-8") as f:
            f.write(f"{chemin};{p95:.0f}\n")
    assert p95 <= SEUIL_MS, f"{chemin} : p95 {p95:.0f} ms > {SEUIL_MS:.0f} ms"
