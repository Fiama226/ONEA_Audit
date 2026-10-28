"""Correctifs de la dernière vague du lot 2 (revue finale : I2, M2, M3, M5, M6, M9, T3 M4)."""

import pytest
from rest_framework.test import APIClient

from apps.referentiel.models import Processus
from apps.referentiel.services import (
    comparer_versions,
    creer_risque,
    creer_version,
    supprimer_risque,
    valider_version,
)
from apps.users.models import User
from tests.referentiel import typed

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- I2


def test_codes_uniques_entre_cartographies_sans_lignee(rai: User) -> None:
    p = typed.processus(code="ZZB")
    v2080 = typed.version(annee=2080)
    fraude = creer_risque(
        version=v2080, processus=p, libelle="Fraude", probabilite=5, impact=5, by=rai
    )
    assert fraude.code == "1-ZZB-R1"
    valider_version(v2080, by=rai)
    v2081 = typed.version(annee=2081)
    panne = creer_risque(
        version=v2081, processus=p, libelle="Panne", probabilite=1, impact=1, by=rai
    )
    assert panne.code == "2-ZZB-R2"
    comp = comparer_versions(v2080, v2081)
    assert [r.code for r in comp.ajoutes] == ["2-ZZB-R2"]
    assert [r.code for r in comp.retires] == ["1-ZZB-R1"]
    assert comp.modifies == []


def test_numerotation_inclut_les_risques_supprimes_d_autres_cartographies(rai: User) -> None:
    p = typed.processus(code="ZZC")
    v1 = typed.version(annee=2082)
    r1 = creer_risque(version=v1, processus=p, libelle="a", probabilite=1, impact=1, by=rai)
    supprimer_risque(r1, by=rai)
    v2 = typed.version(annee=2083)
    r2 = creer_risque(version=v2, processus=p, libelle="b", probabilite=1, impact=1, by=rai)
    assert r2.code == "2-ZZC-R2"


def test_copie_conserve_les_codes_puis_nouveau_risque_continue(rai: User) -> None:
    p = typed.processus(code="ZZD")
    src = typed.version(annee=2084)
    r = creer_risque(version=src, processus=p, libelle="a", probabilite=1, impact=1, by=rai)
    valider_version(src, by=rai)
    copie = creer_version(annee=2085, libelle="c", source=src, by=rai)
    assert [x.code for x in copie.risques.all()] == [r.code]
    autre = typed.version(annee=2086)
    n = creer_risque(version=autre, processus=p, libelle="n", probabilite=1, impact=1, by=rai)
    assert n.code == "2-ZZD-R2"


# --------------------------------------------------------------------------- M2, M6, M9, T3 M4


def test_tri_processus_par_famille(auth_rai: APIClient) -> None:
    typed.processus(code="AAA", famille="SUPPORT")
    typed.processus(code="BBB", famille="REALISATION")
    url = "/api/v1/processes/?ordering="
    asc = [p["famille"] for p in auth_rai.get(url + "famille").json()["results"]]
    desc = [p["famille"] for p in auth_rai.get(url + "-famille").json()["results"]]
    assert asc == sorted(asc)
    assert desc == asc[::-1]
    assert asc != desc


def test_tree_processus_inconnu_ou_supprime_404(auth_rai: APIClient, rai: User) -> None:
    inconnu = "00000000-0000-0000-0000-000000000000"
    r = auth_rai.get(f"/api/v1/auditable-objects/tree/?processus={inconnu}")
    assert r.status_code == 404
    assert r.json() == {"detail": "Non trouvé.", "errors": {}}
    p = typed.processus()
    p.soft_delete(rai)
    assert auth_rai.get(f"/api/v1/auditable-objects/tree/?processus={p.id}").status_code == 404


def test_processus_directions_refuse_un_departement(auth_rai: APIClient) -> None:
    d = typed.direction(code="DEX")
    dep = typed.direction(code="DEP1", type="DEPARTEMENT", parent=d)
    corps = {"code": "XYZ", "libelle": "x", "famille": "SUPPORT"}
    r = auth_rai.post("/api/v1/processes/", {**corps, "directions": [str(dep.id)]}, format="json")
    assert r.status_code == 400
    assert "directions" in r.json()["errors"]
    assert not Processus.objects.filter(code="XYZ").exists()
    r = auth_rai.post("/api/v1/processes/", {**corps, "directions": [str(d.id)]}, format="json")
    assert r.status_code == 201


def test_annee_hors_plage_400_et_bornes_dans_le_schema(auth_rai: APIClient) -> None:
    for annee in (1999, 2101):
        r = auth_rai.post("/api/v1/risk-maps/", {"annee": annee, "libelle": "x"}, format="json")
        assert r.status_code == 400
        assert "annee" in r.json()["errors"]
    schema = auth_rai.get("/api/schema/?format=json").json()
    prop = schema["components"]["schemas"]["CartographieVersion"]["properties"]["annee"]
    assert prop["minimum"] == 2000
    assert prop["maximum"] == 2100


# --------------------------------------------------------------------------- M3


def test_supprimer_processus_utilise_par_cartographie_validee_message_dedie(
    auth_rai: APIClient, rai: User
) -> None:
    v = typed.version(annee=2090)
    r = typed.risque(version=v)
    valider_version(v, by=rai)
    resp = auth_rai.delete(f"/api/v1/processes/{r.processus_id}/")
    assert resp.status_code == 422
    assert "cartographie validée" in resp.json()["detail"]
    assert "supprimez-les d'abord" not in resp.json()["detail"]


def test_supprimer_objet_utilise_par_cartographie_validee_message_dedie(
    auth_rai: APIClient, rai: User
) -> None:
    v = typed.version(annee=2091)
    o = typed.objet()
    typed.risque(version=v, processus=o.processus, objet_auditable=o)
    valider_version(v, by=rai)
    resp = auth_rai.delete(f"/api/v1/auditable-objects/{o.id}/")
    assert resp.status_code == 422
    assert "cartographie validée" in resp.json()["detail"]
    assert "supprimez-les d'abord" not in resp.json()["detail"]
