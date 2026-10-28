from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.referentiel.models import CartographieVersion, StatutCartographie
from apps.referentiel.services import valider_version
from apps.users.models import User
from tests.referentiel import typed

pytestmark = pytest.mark.django_db

MSG_FIGEE = "La cartographie 2026 est validée : elle ne peut plus être modifiée."


def _validee(rai: User, annee: int = 2026, **kw: Any) -> CartographieVersion:
    v = typed.version(annee=annee)
    typed.risque(version=v, **kw)
    valider_version(v, by=rai)
    v.refresh_from_db()
    return v


def test_creer_cartographie(auth_rai: APIClient) -> None:
    r = auth_rai.post(
        "/api/v1/risk-maps/", {"annee": 2027, "libelle": "Cartographie 2027"}, format="json"
    )
    assert r.status_code == 201
    corps = r.json()
    assert corps["statut"] == "BROUILLON"
    assert corps["nb_risques"] == 0
    assert corps["validee_par"] is None
    assert corps["validee_le"] is None


def test_annee_en_double_422(auth_rai: APIClient) -> None:
    typed.version(annee=2027)
    r = auth_rai.post("/api/v1/risk-maps/", {"annee": 2027, "libelle": "Bis"}, format="json")
    assert r.status_code == 422
    assert "annee" in r.json()["errors"]


def test_copie_depuis_source_validee_et_source_brouillon_refusee(
    auth_rai: APIClient, rai: User
) -> None:
    v = _validee(rai)
    r = auth_rai.post(
        "/api/v1/risk-maps/",
        {"annee": 2027, "libelle": "2027", "source": str(v.id)},
        format="json",
    )
    assert r.status_code == 201
    assert r.json()["nb_risques"] == 1
    brouillon = typed.version(annee=2028)
    r = auth_rai.post(
        "/api/v1/risk-maps/",
        {"annee": 2029, "libelle": "x", "source": str(brouillon.id)},
        format="json",
    )
    assert r.status_code == 422
    assert "source" in r.json()["errors"]


def test_annee_et_source_non_modifiables(auth_rai: APIClient) -> None:
    v = typed.version(annee=2030)
    r = auth_rai.patch(f"/api/v1/risk-maps/{v.id}/", {"annee": 2031}, format="json")
    assert r.status_code == 400
    assert "annee" in r.json()["errors"]


def test_validation_renseigne_signataire_et_nb_risques(auth_rai: APIClient, rai: User) -> None:
    v = typed.version(annee=2026)
    typed.risque(version=v)
    typed.risque(version=v)
    r = auth_rai.post(f"/api/v1/risk-maps/{v.id}/validate/")
    assert r.status_code == 200
    corps = r.json()
    assert corps["statut"] == "VALIDEE"
    assert corps["nb_risques"] == 2
    assert corps["validee_par"]["id"] == rai.pk
    assert corps["validee_par"]["username"] == rai.username
    assert corps["validee_par"]["nom_complet"] == "Awa Ouedraogo"
    assert corps["validee_le"]


def test_valider_cartographie_vide_422(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    r = auth_rai.post(f"/api/v1/risk-maps/{v.id}/validate/")
    assert r.status_code == 422
    assert r.json()["detail"] == "Une cartographie sans risque ne peut pas être validée."


def test_revalider_422(auth_rai: APIClient, rai: User) -> None:
    v = _validee(rai)
    r = auth_rai.post(f"/api/v1/risk-maps/{v.id}/validate/")
    assert r.status_code == 422
    assert r.json()["detail"] == MSG_FIGEE


def test_version_validee_ni_modifiable_ni_supprimable(auth_rai: APIClient, rai: User) -> None:
    v = _validee(rai)
    r = auth_rai.patch(f"/api/v1/risk-maps/{v.id}/", {"libelle": "Autre"}, format="json")
    assert r.status_code == 422
    assert r.json() == {"detail": MSG_FIGEE, "errors": {}}
    r = auth_rai.delete(f"/api/v1/risk-maps/{v.id}/")
    assert r.status_code == 422
    assert r.json()["detail"] == MSG_FIGEE
    assert CartographieVersion.objects.filter(pk=v.pk).exists()


def test_statut_non_ecrivable_par_l_api(auth_rai: APIClient) -> None:
    r = auth_rai.post(
        "/api/v1/risk-maps/",
        {"annee": 2027, "libelle": "x", "statut": StatutCartographie.VALIDEE},
        format="json",
    )
    assert r.status_code == 201
    assert r.json()["statut"] == "BROUILLON"


def test_supprimer_brouillon_204(auth_rai: APIClient) -> None:
    v = typed.version(annee=2027)
    assert auth_rai.delete(f"/api/v1/risk-maps/{v.id}/").status_code == 204
    assert auth_rai.get(f"/api/v1/risk-maps/{v.id}/").status_code == 404


def test_liste_filtres_et_tri(auth_rai: APIClient, rai: User) -> None:
    _validee(rai, annee=2026)
    typed.version(annee=2027)
    r = auth_rai.get("/api/v1/risk-maps/?statut=VALIDEE")
    assert [v["annee"] for v in r.json()["results"]] == [2026]
    r = auth_rai.get("/api/v1/risk-maps/?annee=2027")
    assert [v["annee"] for v in r.json()["results"]] == [2027]
    r = auth_rai.get("/api/v1/risk-maps/?ordering=annee")
    assert [v["annee"] for v in r.json()["results"]] == [2026, 2027]
    r = auth_rai.get("/api/v1/risk-maps/")
    assert [v["annee"] for v in r.json()["results"]] == [2027, 2026]


def test_liste_cartographies_requetes_bornees(
    auth_rai: APIClient, django_assert_max_num_queries: Any
) -> None:
    for i in range(10):
        v = typed.version(annee=2000 + i)
        typed.risque(version=v)
    with django_assert_max_num_queries(3):
        assert auth_rai.get("/api/v1/risk-maps/").status_code == 200


def test_matrix_renvoie_25_cellules(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    typed.risque(version=v, probabilite=3, impact=5)  # score 15 : ELEVE
    typed.risque(version=v, probabilite=1, impact=1)
    r = auth_rai.get(f"/api/v1/risk-maps/{v.id}/matrix/")
    assert r.status_code == 200
    corps = r.json()
    assert len(corps["cellules"]) == 25
    assert corps["total"] == 2
    assert corps["par_niveau"] == {"FAIBLE": 1, "MOYEN": 0, "ELEVE": 1}
    assert corps["version"]["annee"] == 2026
    cellule = next(c for c in corps["cellules"] if c["probabilite"] == 3 and c["impact"] == 5)
    assert cellule["nombre"] == 1
    assert cellule["niveau"] == "ELEVE"
    assert cellule["score"] == 15
    assert len(cellule["codes"]) == 1


def test_matrix_version_vide_25_cases_a_zero(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    corps = auth_rai.get(f"/api/v1/risk-maps/{v.id}/matrix/").json()
    assert len(corps["cellules"]) == 25
    assert corps["total"] == 0
    assert all(c["nombre"] == 0 for c in corps["cellules"])


def test_matrix_inconnue_404(auth_rai: APIClient) -> None:
    r = auth_rai.get("/api/v1/risk-maps/00000000-0000-0000-0000-000000000000/matrix/")
    assert r.status_code == 404


def test_compare_sans_with_400(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    r = auth_rai.get(f"/api/v1/risk-maps/{v.id}/compare/")
    assert r.status_code == 400
    assert "with" in r.json()["errors"]


def test_compare_with_invalide_400_et_inconnu_404(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    assert auth_rai.get(f"/api/v1/risk-maps/{v.id}/compare/?with=abc").status_code == 400
    inconnu = "00000000-0000-0000-0000-000000000000"
    assert auth_rai.get(f"/api/v1/risk-maps/{v.id}/compare/?with={inconnu}").status_code == 404


def test_compare_ajoutes_retires_modifies(auth_rai: APIClient, rai: User) -> None:
    ref = _validee(rai, annee=2026, libelle="Commun", probabilite=2, impact=2)
    r = auth_rai.post(
        "/api/v1/risk-maps/",
        {"annee": 2027, "libelle": "2027", "source": str(ref.id)},
        format="json",
    )
    cible_id = r.json()["id"]
    commun = ref.risques.get()
    cible_risque = auth_rai.get(f"/api/v1/risks/?version={cible_id}").json()["results"][0]
    auth_rai.patch(f"/api/v1/risks/{cible_risque['id']}/", {"probabilite": 5}, format="json")
    auth_rai.post(
        "/api/v1/risks/",
        {
            "version": cible_id,
            "processus": str(commun.processus_id),
            "libelle": "Nouveau",
            "probabilite": 1,
            "impact": 1,
        },
        format="json",
    )
    r = auth_rai.get(f"/api/v1/risk-maps/{ref.id}/compare/?with={cible_id}")
    assert r.status_code == 200
    corps = r.json()
    assert corps["reference"]["annee"] == 2026
    assert corps["cible"]["annee"] == 2027
    assert [x["libelle"] for x in corps["ajoutes"]] == ["Nouveau"]
    assert corps["retires"] == []
    assert set(corps["ajoutes"][0]) == {"id", "code", "libelle", "score", "niveau"}
    assert len(corps["modifies"]) == 1
    modif = corps["modifies"][0]
    assert modif["code"] == commun.code
    assert modif["changements"]["probabilite"] == ["2", "5"]
    # sens inverse : l'ajout devient un retrait
    inverse = auth_rai.get(f"/api/v1/risk-maps/{cible_id}/compare/?with={ref.id}").json()
    assert [x["libelle"] for x in inverse["retires"]] == ["Nouveau"]
