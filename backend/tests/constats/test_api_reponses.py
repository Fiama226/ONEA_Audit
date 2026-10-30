import pytest

from apps.constats.models import ReponseAudite
from tests.accomplissement.fixtures_api import client_de
from tests.constats.fixtures_api import EquipeConstats

pytestmark = pytest.mark.django_db
URL = "/api/v1/finding-responses/"


def _corps(e: EquipeConstats, **extra: object) -> dict[str, object]:
    return {
        "constat": str(e.soumis.pk),
        "position": "ACCORD",
        "commentaire": "",
        "confirme": True,
        "empreinte_soumise": e.soumis.empreinte_soumise,
        **extra,
    }


def test_reponse_creee_et_lisible(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"])
    r = audite.post(
        URL,
        _corps(e, position="DESACCORD", commentaire="Le contrôle existe."),
        format="json",
    )
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["position"] == "DESACCORD" and corps["cycle"] == 1
    assert corps["version_anterieure"] is False
    assert "en désaccord" in corps["texte"]
    assert corps["confirmation"]["signataire"]["id"] == e.users["audite"].pk
    detail = audite.get(f"/api/v1/findings/{e.soumis.pk}/").json()
    assert detail["derniere_reponse"]["id"] == corps["id"]
    assert detail["reponse_cycle_courant"] is True
    liste = client_de(e.users["rai"]).get(f"{URL}?constat={e.soumis.pk}").json()
    assert liste["count"] == 1
    assert audite.get(f"{URL}{corps['id']}/").status_code == 200


def test_reponse_sans_confirme_400(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"])
    for corps in (
        _corps(e, confirme=False),
        {k: v for k, v in _corps(e).items() if k != "confirme"},
    ):
        r = audite.post(URL, corps, format="json")
        assert r.status_code == 400 and "confirme" in r.json()["errors"]
    sans_empreinte = {k: v for k, v in _corps(e).items() if k != "empreinte_soumise"}
    assert audite.post(URL, sans_empreinte, format="json").status_code == 400
    assert ReponseAudite.objects.count() == 0


def test_desaccord_sans_commentaire_422(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    r = client_de(e.users["audite"]).post(URL, _corps(e, position="DESACCORD"), format="json")
    assert r.status_code == 422 and set(r.json()) == {"detail", "errors"}


def test_empreinte_perimee_422(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    r = client_de(e.users["audite"]).post(URL, _corps(e, empreinte_soumise="0" * 64), format="json")
    assert r.status_code == 422


def test_reponse_refusee_hors_perimetre(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    # autre entité et brouillon : 404 (invisibles) ; intervenants : 403
    assert client_de(e.users["autre_audite"]).post(URL, _corps(e), format="json").status_code == 404
    brouillon = _corps(e, constat=str(e.brouillon.pk))
    assert client_de(e.users["audite"]).post(URL, brouillon, format="json").status_code == 404
    for qui in ("chef", "rai", "auditeur", "admin", "dg"):
        assert client_de(e.users[qui]).post(URL, _corps(e), format="json").status_code == 403, qui
    assert ReponseAudite.objects.count() == 0


def test_historique_en_ajout_seul(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"])
    r1 = audite.post(URL, _corps(e), format="json")
    r2 = audite.post(
        URL, _corps(e, position="DESACCORD", commentaire="Finalement non"), format="json"
    )
    assert r1.status_code == r2.status_code == 201
    detail = audite.get(f"/api/v1/findings/{e.soumis.pk}/").json()
    assert detail["derniere_reponse"]["id"] == r2.json()["id"]
    assert ReponseAudite.objects.count() == 2
    url = f"{URL}{r1.json()['id']}/"
    audite = client_de(e.users["rai"])
    assert audite.patch(url, {"commentaire": "x"}, format="json").status_code == 405
    assert audite.delete(url).status_code == 405
    assert audite.put(url, {}, format="json").status_code == 405
