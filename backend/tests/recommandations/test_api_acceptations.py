import pytest

from apps.recommandations.models import AcceptationRisque
from tests.accomplissement.fixtures_api import client_de
from tests.recommandations.fixtures_api import (
    ACCEPTATIONS,
    EquipePlan,
    equipe_plan,
)

# ruff: noqa: F811, F401
pytestmark = pytest.mark.django_db


def _corps(e: EquipePlan, **extra: object) -> dict[str, object]:
    return {
        "recommandation": str(e.recommandations[2].pk),
        "justification": "Coût disproportionné.",
        "confirme": True,
        **extra,
    }


def _accepter(e: EquipePlan) -> dict[str, object]:
    r = client_de(e.users["audite_b"]).post(ACCEPTATIONS, _corps(e), format="json")
    assert r.status_code == 201, r.json()
    corps: dict[str, object] = r.json()
    return corps


def test_acceptation_creee_et_lisible(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    corps = _accepter(e)
    assert corps["recommandation"] == str(e.recommandations[2].pk)
    assert "Coût disproportionné." in str(corps["texte"])
    assert corps["auteur"]["id"] == e.users["audite_b"].pk  # type: ignore[index]
    assert corps["confirmation"]["signataire"]["id"] == e.users["audite_b"].pk  # type: ignore[index]
    base = f"{ACCEPTATIONS}?mission={e.mission.pk}"
    rai = client_de(e.users["rai"])
    assert rai.get(base).json()["count"] == 1
    reco = e.recommandations[2].pk
    assert rai.get(f"{ACCEPTATIONS}?recommandation={reco}").json()["count"] == 1
    assert rai.get(f"{ACCEPTATIONS}{corps['id']}/").status_code == 200
    # l'audité de l'autre entité ne la voit pas
    assert client_de(e.users["audite_a"]).get(base).json()["count"] == 0
    assert client_de(e.users["audite_a"]).get(f"{ACCEPTATIONS}{corps['id']}/").status_code == 404


def test_acceptation_sans_confirme_400(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    audite = client_de(e.users["audite_b"])
    absent = {k: v for k, v in _corps(e).items() if k != "confirme"}
    for corps in (_corps(e, confirme=False), absent):
        r = audite.post(ACCEPTATIONS, corps, format="json")
        assert r.status_code == 400, r.json()
        assert r.json()["errors"].get("confirme") in (
            ["Cochez la case de confirmation."],
            ["Ce champ est obligatoire."],
        )
    r = audite.post(ACCEPTATIONS, _corps(e, confirme=False), format="json")
    assert r.json()["errors"]["confirme"] == ["Cochez la case de confirmation."]
    assert AcceptationRisque.objects.count() == 0


def test_acceptation_regles_metier_422(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    audite = client_de(e.users["audite_b"])
    r = audite.post(ACCEPTATIONS, _corps(e, justification="  "), format="json")
    assert r.status_code == 422 and set(r.json()) == {"detail", "errors"}
    _accepter(e)
    assert audite.post(ACCEPTATIONS, _corps(e), format="json").status_code == 422  # déjà acceptée
    # recommandation portant déjà des actions : l'audité A ne peut pas accepter
    r = client_de(e.users["audite_a"]).post(
        ACCEPTATIONS, _corps(e, recommandation=str(e.recommandations[0].pk)), format="json"
    )
    assert r.status_code == 422


def test_acceptation_corps_invalide_et_invisible(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    audite = client_de(e.users["audite_b"])
    assert audite.post(ACCEPTATIONS, {"confirme": True}, format="json").status_code == 400
    r = audite.post(ACCEPTATIONS, _corps(e, recommandation="xyz"), format="json")
    assert r.status_code == 400
    inconnue = "00000000-0000-0000-0000-000000000000"
    assert (
        audite.post(ACCEPTATIONS, _corps(e, recommandation=inconnue), format="json").status_code
        == 404
    )


def test_retrait_par_auteur_ou_rai(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    for qui in ("audite_b", "rai"):
        acceptation = _accepter(e)
        url = f"{ACCEPTATIONS}{acceptation['id']}/withdraw/"
        for refus in ("chef", "auditeur", "superviseur"):
            assert client_de(e.users[refus]).post(url).status_code == 403, refus
        assert client_de(e.users["audite_a"]).post(url).status_code == 404
        assert client_de(e.users["admin"]).post(url).status_code == 403
        assert client_de(e.users[qui]).post(url).status_code == 204, qui
        assert not AcceptationRisque.objects.filter(pk=acceptation["id"]).exists()


def test_liste_exige_mission_ou_recommandation(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    rai = client_de(e.users["rai"])
    assert rai.get(ACCEPTATIONS).status_code == 400
    assert rai.get(f"{ACCEPTATIONS}?recommandation=xyz").status_code == 400
    assert rai.get(f"{ACCEPTATIONS}?mission=xyz").status_code == 400
    inconnue = "00000000-0000-0000-0000-000000000000"
    assert rai.get(f"{ACCEPTATIONS}?mission={inconnue}").status_code == 404
    assert rai.get(f"{ACCEPTATIONS}?recommandation={inconnue}").status_code == 404
    assert (
        client_de(e.users["non_affecte"]).get(f"{ACCEPTATIONS}?mission={e.mission.pk}").status_code
        == 404
    )
