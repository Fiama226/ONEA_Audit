import pytest
from rest_framework.test import APIClient

from apps.referentiel.models import Direction, NatureObjet, Processus
from tests.referentiel import typed

pytestmark = pytest.mark.django_db


def test_creer_direction_et_departement(auth_rai: APIClient) -> None:
    r = auth_rai.post(
        "/api/v1/directions/",
        {"code": "DEX", "libelle": "Direction exploitation", "type": "DIRECTION"},
        format="json",
    )
    assert r.status_code == 201
    parent_id = r.json()["id"]
    assert r.json()["parent"] is None
    assert r.json()["parent_code"] is None
    r = auth_rai.post(
        "/api/v1/directions/",
        {"code": "DEX-1", "libelle": "Département", "type": "DEPARTEMENT", "parent": parent_id},
        format="json",
    )
    assert r.status_code == 201
    assert r.json()["parent_code"] == "DEX"


def test_code_direction_doublon_refuse_avec_erreur_sur_code(auth_rai: APIClient) -> None:
    typed.direction(code="DEX")
    r = auth_rai.post(
        "/api/v1/directions/", {"code": "DEX", "libelle": "Bis", "type": "DIRECTION"}, format="json"
    )
    assert r.status_code in (400, 422)
    assert r.json()["errors"]["code"] == ["Ce code est déjà utilisé."]
    assert Direction.objects.filter(code="DEX").count() == 1


def test_code_direction_avec_accent_400(auth_rai: APIClient) -> None:
    r = auth_rai.post(
        "/api/v1/directions/", {"code": "ÉST", "libelle": "x", "type": "DIRECTION"}, format="json"
    )
    assert r.status_code == 400
    assert "code" in r.json()["errors"]


def test_code_immuable_422(auth_rai: APIClient) -> None:
    d = typed.direction(code="DEX")
    r = auth_rai.patch(f"/api/v1/directions/{d.id}/", {"code": "AUTRE"}, format="json")
    assert r.status_code == 422
    assert r.json()["detail"] == "Le code ne peut pas être modifié après création."


def test_departement_sans_parent_422(auth_rai: APIClient) -> None:
    r = auth_rai.post(
        "/api/v1/directions/", {"code": "DEP", "libelle": "x", "type": "DEPARTEMENT"}, format="json"
    )
    assert r.status_code == 422
    assert r.json()["errors"]["parent"] == ["Un département doit être rattaché à une direction."]


def test_supprimer_direction_rattachee_422(auth_rai: APIClient) -> None:
    d = typed.direction()
    p = typed.processus()
    p.directions.add(d)
    r = auth_rai.delete(f"/api/v1/directions/{d.id}/")
    assert r.status_code == 422
    assert "rattachée" in r.json()["detail"]


def test_creer_processus_avec_directions(auth_rai: APIClient) -> None:
    d = typed.direction(code="DEX")
    r = auth_rai.post(
        "/api/v1/processes/",
        {
            "code": "FEP",
            "libelle": "Eau potable",
            "famille": "REALISATION",
            "directions": [str(d.id)],
        },
        format="json",
    )
    assert r.status_code == 201
    corps = r.json()
    assert corps["directions_detail"] == [{"id": str(d.id), "code": "DEX", "libelle": d.libelle}]
    assert "directions" not in corps
    r = auth_rai.patch(f"/api/v1/processes/{corps['id']}/", {"directions": []}, format="json")
    assert r.status_code == 200
    assert r.json()["directions_detail"] == []


def test_processus_code_minuscule_400(auth_rai: APIClient) -> None:
    r = auth_rai.post(
        "/api/v1/processes/", {"code": "fep", "libelle": "x", "famille": "SUPPORT"}, format="json"
    )
    assert r.status_code == 400
    assert "code" in r.json()["errors"]


def test_supprimer_processus_avec_risques_422(auth_rai: APIClient) -> None:
    p = typed.processus(code="FEP")
    typed.risque(processus=p)
    r = auth_rai.delete(f"/api/v1/processes/{p.id}/")
    assert r.status_code == 422
    assert r.json()["detail"].startswith("Ce processus porte des risques")
    assert Processus.objects.filter(pk=p.pk).exists()


def test_supprimer_processus_libre_204_et_disparait(auth_rai: APIClient) -> None:
    p = typed.processus()
    assert auth_rai.delete(f"/api/v1/processes/{p.id}/").status_code == 204
    assert auth_rai.get(f"/api/v1/processes/{p.id}/").status_code == 404
    assert Processus.all_objects.filter(pk=p.pk, deleted_at__isnull=False).exists()


def test_404_au_format_unique(auth_rai: APIClient) -> None:
    r = auth_rai.get("/api/v1/processes/00000000-0000-0000-0000-000000000000/")
    assert r.status_code == 404
    assert r.json() == {"detail": "Non trouvé.", "errors": {}}


def test_filtres_et_recherche_insensible_a_la_casse(auth_rai: APIClient) -> None:
    typed.processus(code="FEP", libelle="Fourniture d'Eau Potable", famille="REALISATION")
    typed.processus(code="GRH", libelle="Ressources humaines", famille="SUPPORT")
    r = auth_rai.get("/api/v1/processes/?q=eau")
    assert [p["code"] for p in r.json()["results"]] == ["FEP"]
    r = auth_rai.get("/api/v1/processes/?q=grh")
    assert [p["code"] for p in r.json()["results"]] == ["GRH"]
    r = auth_rai.get("/api/v1/processes/?famille=SUPPORT")
    assert [p["code"] for p in r.json()["results"]] == ["GRH"]
    r = auth_rai.get("/api/v1/processes/?famille=INCONNUE")
    assert r.status_code == 400
    assert "famille" in r.json()["errors"]


def test_recherche_traite_les_jokers_comme_du_texte(auth_rai: APIClient) -> None:
    typed.processus(code="FEP", libelle="Eau potable")
    assert auth_rai.get("/api/v1/processes/?q=%25").json()["count"] == 0


def test_filtre_processus_par_direction(auth_rai: APIClient) -> None:
    d = typed.direction()
    p = typed.processus(code="FEP")
    typed.processus(code="GRH")
    p.directions.add(d)
    r = auth_rai.get(f"/api/v1/processes/?direction={d.id}")
    assert [x["code"] for x in r.json()["results"]] == ["FEP"]


def test_tri_processus_et_directions(auth_rai: APIClient) -> None:
    typed.processus(code="AAA", ordre=2)
    typed.processus(code="BBB", ordre=1)
    codes = [p["code"] for p in auth_rai.get("/api/v1/processes/?ordering=-code").json()["results"]]
    assert codes == ["BBB", "AAA"]
    typed.direction(code="ZZZ")
    typed.direction(code="AAD")
    codes = [d["code"] for d in auth_rai.get("/api/v1/directions/?ordering=code").json()["results"]]
    assert codes == ["AAD", "ZZZ"]


def test_filtre_directions_par_type_et_parent(auth_rai: APIClient) -> None:
    d = typed.direction(code="DEX")
    typed.direction(code="DEP1", type="DEPARTEMENT", parent=d)
    typed.direction(code="OTHER")
    r = auth_rai.get(f"/api/v1/directions/?parent={d.id}")
    assert [x["code"] for x in r.json()["results"]] == ["DEP1"]
    r = auth_rai.get("/api/v1/directions/?type=DEPARTEMENT&q=dep")
    assert [x["code"] for x in r.json()["results"]] == ["DEP1"]


def test_tree_imbrique_operations(auth_rai: APIClient) -> None:
    p = typed.processus()
    dom = typed.objet(processus=p, libelle="Domaine A", ordre=1)
    typed.objet(processus=p, libelle="Op 2", nature=NatureObjet.OPERATION, parent=dom, ordre=2)
    typed.objet(processus=p, libelle="Op 1", nature=NatureObjet.OPERATION, parent=dom, ordre=1)
    typed.objet(libelle="Autre processus")
    r = auth_rai.get(f"/api/v1/auditable-objects/tree/?processus={p.id}")
    assert r.status_code == 200
    arbre = r.json()
    assert isinstance(arbre, list)
    assert [d["libelle"] for d in arbre] == ["Domaine A"]
    assert [o["libelle"] for o in arbre[0]["operations"]] == ["Op 1", "Op 2"]
    assert set(arbre[0]) == {"id", "libelle", "description", "ordre", "operations"}


def test_tree_sans_processus_400(auth_rai: APIClient) -> None:
    r = auth_rai.get("/api/v1/auditable-objects/tree/")
    assert r.status_code == 400
    assert "processus" in r.json()["errors"]


def test_objets_crud_et_regles(auth_rai: APIClient) -> None:
    p = typed.processus()
    r = auth_rai.post(
        "/api/v1/auditable-objects/",
        {"processus": str(p.id), "nature": "OPERATION", "libelle": "Orpheline"},
        format="json",
    )
    assert r.status_code == 422
    assert "parent" in r.json()["errors"]
    r = auth_rai.post(
        "/api/v1/auditable-objects/",
        {"processus": str(p.id), "nature": "DOMAINE", "libelle": "Dom"},
        format="json",
    )
    assert r.status_code == 201
    dom = r.json()["id"]
    r = auth_rai.post(
        "/api/v1/auditable-objects/",
        {"processus": str(p.id), "nature": "OPERATION", "libelle": "Op", "parent": dom},
        format="json",
    )
    assert r.status_code == 201
    assert auth_rai.delete(f"/api/v1/auditable-objects/{dom}/").status_code == 422
    r = auth_rai.get(f"/api/v1/auditable-objects/?parent={dom}&nature=OPERATION&q=OP")
    assert r.json()["count"] == 1
    r = auth_rai.patch(
        f"/api/v1/auditable-objects/{dom}/",
        {"processus": str(typed.processus().id)},
        format="json",
    )
    assert r.status_code == 422


def test_page_size_plafonne_a_200(auth_rai: APIClient) -> None:
    for i in range(205):
        typed.direction(code=f"D{i:03d}")
    r = auth_rai.get("/api/v1/directions/?page_size=1000")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 200
    assert r.json()["count"] == 205
    assert len(auth_rai.get("/api/v1/directions/").json()["results"]) == 25
    assert auth_rai.get("/api/v1/directions/?page=99").status_code == 404
