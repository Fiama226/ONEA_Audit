from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.programmation.models import ProgrammeAnnuel
from apps.users.models import Role
from tests.factories import make_user

from .factories import ligne, programme


@pytest.fixture
def rai_client(api_client: APIClient, db: None) -> APIClient:
    api_client.force_authenticate(make_user(Role.RAI))
    return api_client


def test_creer_puis_lire_programme(rai_client: APIClient) -> None:
    r = rai_client.post("/api/v1/audit-plans/", {"annee": 2026}, format="json")
    assert r.status_code == 201
    corps = r.json()
    assert corps["statut"] == "BROUILLON"
    assert corps["nb_lignes"] == 0
    assert corps["charge_totale_jours"] == "0.0"
    assert corps["valide_par"] is None
    assert rai_client.get(f"/api/v1/audit-plans/{corps['id']}/").json()["annee"] == 2026


def test_annee_en_double_422(rai_client: APIClient) -> None:
    programme(annee=2026)
    r = rai_client.post("/api/v1/audit-plans/", {"annee": 2026}, format="json")
    assert r.status_code == 422
    assert "annee" in r.json()["errors"]


def test_programme_annee_non_modifiable_422(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    r = rai_client.patch(f"/api/v1/audit-plans/{p.id}/", {"annee": 2027}, format="json")
    assert r.status_code == 422
    assert "annee" in r.json()["errors"]


def test_modifier_libelle(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    r = rai_client.patch(f"/api/v1/audit-plans/{p.id}/", {"libelle": "Nouveau"}, format="json")
    assert r.status_code == 200
    assert r.json()["libelle"] == "Nouveau"


def test_valider_puis_gel(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    ligne(programme=p, charge_prevue_jours="12.5")
    r = rai_client.post(f"/api/v1/audit-plans/{p.id}/validate/")
    assert r.status_code == 200
    corps = r.json()
    assert corps["statut"] == "VALIDE"
    assert corps["valide_par"]["username"]
    assert corps["nb_lignes"] == 1
    assert corps["charge_totale_jours"] == "12.5"
    r2 = rai_client.patch(f"/api/v1/audit-plans/{p.id}/", {"libelle": "x"}, format="json")
    assert r2.status_code == 422
    assert "validé" in r2.json()["detail"]


def test_valider_programme_vide_422(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    assert rai_client.post(f"/api/v1/audit-plans/{p.id}/validate/").status_code == 422


def test_supprimer_programme_valide_422(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    ligne(programme=p)
    rai_client.post(f"/api/v1/audit-plans/{p.id}/validate/")
    r = rai_client.delete(f"/api/v1/audit-plans/{p.id}/")
    assert r.status_code == 422
    assert "validé" in r.json()["detail"]


def test_supprimer_programme_brouillon_204(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    assert rai_client.delete(f"/api/v1/audit-plans/{p.id}/").status_code == 204
    assert not ProgrammeAnnuel.objects.filter(pk=p.pk).exists()
    assert rai_client.get(f"/api/v1/audit-plans/{p.id}/").status_code == 404


def test_filtres_programmes(rai_client: APIClient) -> None:
    programme(annee=2025)
    programme(annee=2026)
    r = rai_client.get("/api/v1/audit-plans/?annee=2026")
    assert [x["annee"] for x in r.json()["results"]] == [2026]
    r = rai_client.get("/api/v1/audit-plans/?statut=VALIDE")
    assert r.json()["results"] == []


def test_synthese(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    ligne(programme=p, type="CONSEIL", charge_prevue_jours="2.0")
    r = rai_client.get(f"/api/v1/audit-plans/{p.id}/summary/")
    assert r.status_code == 200
    assert r.json() == {
        "nb_lignes": 1,
        "charge_totale_jours": "2.0",
        "par_type": {"ASSURANCE": 0, "CONSEIL": 1},
        "par_trimestre": {"1": 1, "2": 0, "3": 0, "4": 0},
    }


def test_liste_programmes_requetes_bornees(
    rai_client: APIClient, django_assert_max_num_queries: Any
) -> None:
    for annee in range(2001, 2021):
        ligne(programme=programme(annee=annee))
    with django_assert_max_num_queries(4):
        r = rai_client.get("/api/v1/audit-plans/?page_size=200")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 20
