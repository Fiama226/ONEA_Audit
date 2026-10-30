import pytest

from tests.accomplissement.fixtures_api import client_de
from tests.recommandations.fixtures_api import (
    ENGAGEMENTS,
    SYNTHESE,
    EquipePlan,
    equipe_plan,
)

# ruff: noqa: F811, F401
pytestmark = pytest.mark.django_db


def _synthese(e: EquipePlan, qui: str) -> dict[str, object]:
    r = client_de(e.users[qui]).get(f"{SYNTHESE}?mission={e.mission.pk}")
    assert r.status_code == 200, r.json()
    corps: dict[str, object] = r.json()
    return corps


def test_synthese_de_l_equipe(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    for qui in ("rai", "chef", "auditeur", "superviseur"):
        s = _synthese(e, qui)
        assert len(s["recommandations"]) == 3, qui  # type: ignore[arg-type]
        statuts = {r["reference"]: r["statut_derive"] for r in s["recommandations"]}  # type: ignore[attr-defined]
        assert sorted(statuts.values()) == ["A_LANCER", "A_LANCER", "SANS_ACTION"]
        assert len(s["recommandations_sans_suite"]) == 1  # type: ignore[arg-type]
        assert s["actions_incompletes"] == ["A-01", "A-02"]
        assert [r["utilisateur"]["id"] for r in s["responsables"]] == [e.users["audite_a"].pk]  # type: ignore[attr-defined]
        assert s["responsables"][0]["engagement"] == "NON_CONFIRME"  # type: ignore[index]
        assert len(s["engagements_manquants"]) == 1  # type: ignore[arg-type]


def test_synthese_de_l_audite_limitee_a_son_perimetre(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    a = _synthese(e, "audite_a")
    assert len(a["recommandations"]) == 2  # type: ignore[arg-type]
    assert a["recommandations_sans_suite"] == []
    assert a["actions_incompletes"] == ["A-01", "A-02"]
    assert [r["utilisateur"]["id"] for r in a["responsables"]] == [e.users["audite_a"].pk]  # type: ignore[attr-defined]
    b = _synthese(e, "audite_b")
    assert len(b["recommandations"]) == 1  # type: ignore[arg-type]
    assert len(b["recommandations_sans_suite"]) == 1  # type: ignore[arg-type]
    assert (
        b["actions_incompletes"] == []
        and b["responsables"] == []
        and b["engagements_manquants"] == []
    )
    client_de(e.users["audite_a"]).post(
        ENGAGEMENTS, {"mission": str(e.mission.pk), "confirme": True}, format="json"
    )
    apres = _synthese(e, "audite_a")
    assert apres["responsables"][0]["engagement"] == "CONFIRME"  # type: ignore[index]
    assert apres["engagements_manquants"] == []


def test_synthese_refus_et_parametres(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    rai = client_de(e.users["rai"])
    assert rai.get(SYNTHESE).status_code == 400
    assert rai.get(f"{SYNTHESE}?mission=xyz").status_code == 400
    inconnue = "00000000-0000-0000-0000-000000000000"
    assert rai.get(f"{SYNTHESE}?mission={inconnue}").status_code == 404
    url = f"{SYNTHESE}?mission={e.mission.pk}"
    for qui in ("non_affecte", "audite_non_affecte"):
        assert client_de(e.users[qui]).get(url).status_code == 404, qui
    for qui in ("admin", "dg"):
        assert client_de(e.users[qui]).get(url).status_code == 403, qui
    assert rai.post(SYNTHESE, {}, format="json").status_code == 405


def test_synthese_requetes_bornees(equipe_plan: EquipePlan, django_assert_max_num_queries) -> None:  # type: ignore[no-untyped-def]
    e = equipe_plan
    for qui in ("rai", "audite_a"):
        with django_assert_max_num_queries(10):
            assert (
                client_de(e.users[qui]).get(f"{SYNTHESE}?mission={e.mission.pk}").status_code == 200
            )
