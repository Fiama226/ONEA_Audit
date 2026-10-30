# ruff: noqa: F811
"""Matrice rôle x route des deux apps du lot 6 (D13) : refus de rôle, visibilité, droits."""

import pytest

from tests.accomplissement.fixtures_api import client_de
from tests.constats.conftest import (
    mission_en_xiv,  # noqa: F401
    stockage_temporaire,  # noqa: F401
)
from tests.constats.fixtures_api import EquipeConstats, equipe_constats  # noqa: F401
from tests.missions.conftest import audite_affecte, auditeur_mission, chef, mission_lancee  # noqa: F401

pytestmark = pytest.mark.django_db


def _routes(e: EquipeConstats) -> dict[str, str]:
    m = e.mission.pk
    return {
        "findings": f"/api/v1/findings/?mission={m}",
        "finding": f"/api/v1/findings/{e.soumis.pk}/",
        "responses": f"/api/v1/finding-responses/?mission={m}",
        "recommendations": f"/api/v1/recommendations/?mission={m}",
        "work-programs": f"/api/v1/work-programs/?mission={m}",
        "planned-tests": f"/api/v1/planned-tests/?mission={m}",
        "test-sheets": f"/api/v1/test-sheets/?mission={m}",
    }


@pytest.mark.parametrize("role", ["admin", "dg"])
def test_admin_et_dg_refuses_partout(equipe_constats: EquipeConstats, role: str) -> None:
    client = client_de(equipe_constats.users[role])
    for nom, url in _routes(equipe_constats).items():
        assert client.get(url).status_code == 403, nom


def test_audite_lit_constats_mais_pas_l_accomplissement(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    client = client_de(e.users["audite"])
    statuts = {nom: client.get(url).status_code for nom, url in _routes(e).items()}
    assert statuts == {
        "findings": 200,
        "finding": 200,
        "responses": 200,
        "recommendations": 200,
        "work-programs": 403,
        "planned-tests": 403,
        "test-sheets": 403,
    }


@pytest.mark.parametrize("role", ["rai", "chef", "auditeur"])
def test_intervenants_lisent_tout(equipe_constats: EquipeConstats, role: str) -> None:
    client = client_de(equipe_constats.users[role])
    for nom, url in _routes(equipe_constats).items():
        assert client.get(url).status_code == 200, nom


def test_mission_invisible_404(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    for qui in ("non_affecte", "audite_non_affecte"):
        client = client_de(e.users[qui])
        for nom in ("findings", "responses", "recommendations"):
            url = _routes(e)[nom]
            expected = 403 if qui == "audite_non_affecte" and False else 404
            assert client.get(url).status_code == expected, (qui, nom)


def test_recommandations_de_l_audite(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"])
    corps = audite.get(f"/api/v1/recommendations/?mission={e.mission.pk}").json()
    assert corps["count"] == 1  # celles du constat soumis seulement
    assert corps["results"][0]["constat"] == str(e.soumis.pk)
    rai = client_de(e.users["rai"])
    assert rai.post("/api/v1/recommendations/", {}, format="json").status_code == 405
    assert rai.get(f"/api/v1/recommendations/?mission={e.mission.pk}").json()["count"] == 2
    assert (
        rai.get(f"/api/v1/recommendations/?mission={e.mission.pk}&priorite=FAIBLE").json()["count"]
        == 0
    )
