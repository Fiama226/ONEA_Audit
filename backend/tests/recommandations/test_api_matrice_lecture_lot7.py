# ruff: noqa: F811, F401
"""Lecture du plan d'actions par rôle (D13) : complète `tests/test_matrice_droits_lot7.py`."""

import pytest

from tests.accomplissement.fixtures_api import client_de
from tests.recommandations.fixtures_api import (
    ACCEPTATIONS,
    ACTIONS,
    ENGAGEMENTS,
    SYNTHESE,
    EquipePlan,
    equipe_plan,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "qui,attendu",
    [
        ("rai", 200),
        ("chef", 200),
        ("auditeur", 200),
        ("superviseur", 200),
        ("audite_a", 200),
        ("audite_b", 200),
        ("non_affecte", 404),
        ("audite_non_affecte", 404),
        ("admin", 403),
        ("dg", 403),
    ],
)
def test_matrice_lecture_plan_d_actions(equipe_plan: EquipePlan, qui: str, attendu: int) -> None:
    client = client_de(equipe_plan.users[qui])
    m = equipe_plan.mission.pk
    for route in (ACTIONS, ACCEPTATIONS, ENGAGEMENTS, SYNTHESE):
        assert client.get(f"{route}?mission={m}").status_code == attendu, (route, qui)
