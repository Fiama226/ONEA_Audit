import pytest

from apps.recommandations.models import EngagementPlanActions
from tests.accomplissement.fixtures_api import client_de
from tests.recommandations.fixtures_api import (
    ENGAGEMENTS,
    EquipePlan,
    equipe_plan,
)

# ruff: noqa: F811, F401
pytestmark = pytest.mark.django_db


def _corps(e: EquipePlan, **extra: object) -> dict[str, object]:
    return {"mission": str(e.mission.pk), "confirme": True, **extra}


def test_texte_a_confirmer(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    url = f"{ENGAGEMENTS}texte/?mission={e.mission.pk}"
    r = client_de(e.users["audite_a"]).get(url)
    assert r.status_code == 200, r.json()
    assert r.json()["nb_actions"] == 1 and r.json()["etat"] == "NON_CONFIRME"
    assert "les 1 actions" in r.json()["texte"]
    for qui in ("rai", "chef", "auditeur", "admin", "dg"):
        assert client_de(e.users[qui]).get(url).status_code == 403, qui
    assert client_de(e.users["audite_non_affecte"]).get(url).status_code == 404
    audite = client_de(e.users["audite_a"])
    assert audite.get(f"{ENGAGEMENTS}texte/").status_code == 400
    assert audite.get(f"{ENGAGEMENTS}texte/?mission=xyz").status_code == 400


def test_engagement_cree_confirme_puis_a_renouveler(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    audite = client_de(e.users["audite_a"])
    texte = audite.get(f"{ENGAGEMENTS}texte/?mission={e.mission.pk}").json()["texte"]
    r = audite.post(ENGAGEMENTS, _corps(e), format="json")
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["texte"] == texte
    assert corps["auteur"]["id"] == e.users["audite_a"].pk
    assert corps["confirmation"]["signataire"]["id"] == e.users["audite_a"].pk
    assert len(corps["empreinte_actions"]) == 64
    url = f"{ENGAGEMENTS}texte/?mission={e.mission.pk}"
    assert audite.get(url).json()["etat"] == "CONFIRME"
    r = client_de(e.users["chef"]).patch(
        f"/api/v1/corrective-actions/{e.action_resp.pk}/", {"indicateur": "Autre"}, format="json"
    )
    assert r.status_code == 200
    assert audite.get(url).json()["etat"] == "A_RENOUVELER"


def test_engagement_sans_confirme_400(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    audite = client_de(e.users["audite_a"])
    r = audite.post(ENGAGEMENTS, _corps(e, confirme=False), format="json")
    assert r.status_code == 400
    assert r.json()["errors"]["confirme"] == ["Cochez la case de confirmation."]
    r = audite.post(ENGAGEMENTS, {"mission": str(e.mission.pk)}, format="json")
    assert r.status_code == 400 and "confirme" in r.json()["errors"]
    assert audite.post(ENGAGEMENTS, {"confirme": True}, format="json").status_code == 400
    assert EngagementPlanActions.objects.count() == 0


def test_engagement_sans_action_422(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    r = client_de(e.users["audite_b"]).post(ENGAGEMENTS, _corps(e), format="json")
    assert r.status_code == 422 and set(r.json()) == {"detail", "errors"}


def test_lecture_des_engagements(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    client_de(e.users["audite_a"]).post(ENGAGEMENTS, _corps(e), format="json")
    base = f"{ENGAGEMENTS}?mission={e.mission.pk}"
    for qui in ("rai", "chef", "auditeur", "superviseur", "audite_a"):
        assert client_de(e.users[qui]).get(base).json()["count"] == 1, qui
    assert client_de(e.users["audite_b"]).get(base).json()["count"] == 0
    assert client_de(e.users["non_affecte"]).get(base).status_code == 404
    assert client_de(e.users["dg"]).get(base).status_code == 403
    assert client_de(e.users["rai"]).get(ENGAGEMENTS).status_code == 400
    # ajout seul : ni modification ni suppression
    pk = EngagementPlanActions.objects.get().pk
    rai = client_de(e.users["rai"])
    assert rai.delete(f"{ENGAGEMENTS}{pk}/").status_code in (404, 405)
    assert rai.patch(f"{ENGAGEMENTS}{pk}/", {}, format="json").status_code in (404, 405)
