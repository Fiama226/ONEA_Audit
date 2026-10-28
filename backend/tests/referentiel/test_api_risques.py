from typing import Any

import pytest
import yaml
from rest_framework.test import APIClient

from apps.referentiel.models import Risque
from apps.referentiel.services import valider_version
from apps.users.models import User
from tests.referentiel import typed

pytestmark = pytest.mark.django_db

MSG_FIGEE = "La cartographie 2026 est validée : elle ne peut plus être modifiée."


def _body(v: Any, p: Any, **kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "version": str(v.id),
        "processus": str(p.id),
        "libelle": "Rupture d'approvisionnement",
        "probabilite": 3,
        "impact": 5,
    }
    body.update(kw)
    return body


def test_creer_risque_numerote_par_le_serveur(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    r = auth_rai.post("/api/v1/risks/", _body(v, p), format="json")
    assert r.status_code == 201
    corps = r.json()
    assert corps["code"] == "1-FEP-R1"
    assert (corps["numero"], corps["rang"]) == (1, 1)
    assert corps["score"] == 15
    assert corps["niveau"] == "ELEVE"
    assert corps["priorite"] == 1
    assert corps["version_annee"] == 2026
    assert corps["version_statut"] == "BROUILLON"
    assert corps["processus_code"] == "FEP"
    assert corps["objet_auditable_libelle"] is None
    r = auth_rai.post("/api/v1/risks/", _body(v, p), format="json")
    assert r.json()["code"] == "2-FEP-R2"


def test_code_et_score_non_ecrivables(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    r = auth_rai.post(
        "/api/v1/risks/",
        _body(v, p, code="99-XX-R9", score=1, niveau="FAIBLE", numero=99),
        format="json",
    )
    assert r.status_code == 201
    assert r.json()["code"] == "1-FEP-R1"
    assert r.json()["niveau"] == "ELEVE"


@pytest.mark.parametrize("valeur", [6, 0, -1, "abc", None, 2.5])
@pytest.mark.parametrize("champ", ["probabilite", "impact"])
def test_notes_hors_bornes_400(auth_rai: APIClient, champ: str, valeur: Any) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    r = auth_rai.post("/api/v1/risks/", _body(v, p, **{champ: valeur}), format="json")
    assert r.status_code == 400
    assert champ in r.json()["errors"]
    assert Risque.objects.count() == 0


def test_notes_manquantes_400(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    body = _body(v, p)
    del body["probabilite"]
    r = auth_rai.post("/api/v1/risks/", body, format="json")
    assert r.status_code == 400
    assert "probabilite" in r.json()["errors"]


def test_modifier_notes_hors_bornes_400(auth_rai: APIClient) -> None:
    risque = typed.risque()
    r = auth_rai.patch(f"/api/v1/risks/{risque.id}/", {"probabilite": 6}, format="json")
    assert r.status_code == 400
    assert "probabilite" in r.json()["errors"]


def test_modifier_risque_recalcule(auth_rai: APIClient) -> None:
    risque = typed.risque(probabilite=1, impact=1)
    r = auth_rai.patch(
        f"/api/v1/risks/{risque.id}/", {"probabilite": 5, "impact": 5}, format="json"
    )
    assert r.status_code == 200
    assert (r.json()["score"], r.json()["niveau"]) == (25, "ELEVE")


def test_modifier_risque_valide_422(auth_rai: APIClient, rai: User) -> None:
    v = typed.version(annee=2026)
    risque = typed.risque(version=v)
    valider_version(v, by=rai)
    r = auth_rai.patch(f"/api/v1/risks/{risque.id}/", {"impact": 5}, format="json")
    assert r.status_code == 422
    assert r.json() == {"detail": MSG_FIGEE, "errors": {}}
    risque.refresh_from_db()
    assert risque.impact == 3


def test_supprimer_risque_valide_422(auth_rai: APIClient, rai: User) -> None:
    v = typed.version(annee=2026)
    risque = typed.risque(version=v)
    valider_version(v, by=rai)
    r = auth_rai.delete(f"/api/v1/risks/{risque.id}/")
    assert r.status_code == 422
    assert r.json()["detail"] == MSG_FIGEE
    assert Risque.objects.filter(pk=risque.pk).exists()


def test_creer_risque_dans_version_validee_422(auth_rai: APIClient, rai: User) -> None:
    v = typed.version(annee=2026)
    typed.risque(version=v)
    valider_version(v, by=rai)
    p = typed.processus(code="FEP")
    r = auth_rai.post("/api/v1/risks/", _body(v, p), format="json")
    assert r.status_code == 422
    assert r.json()["detail"] == MSG_FIGEE


def test_deplacer_ou_changer_processus_refuse(auth_rai: APIClient) -> None:
    risque = typed.risque()
    autre = typed.version(annee=2040)
    r = auth_rai.patch(f"/api/v1/risks/{risque.id}/", {"version": str(autre.id)}, format="json")
    assert r.status_code == 400
    assert "version" in r.json()["errors"]
    r = auth_rai.patch(
        f"/api/v1/risks/{risque.id}/", {"processus": str(typed.processus().id)}, format="json"
    )
    assert r.status_code in (400, 422)
    assert "processus" in r.json()["errors"]
    # renvoyer les mêmes valeurs reste accepté
    r = auth_rai.patch(
        f"/api/v1/risks/{risque.id}/",
        {"version": str(risque.version_id), "processus": str(risque.processus_id), "impact": 4},
        format="json",
    )
    assert r.status_code == 200


def test_objet_d_un_autre_processus_422(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    objet = typed.objet()
    r = auth_rai.post("/api/v1/risks/", _body(v, p, objet_auditable=str(objet.id)), format="json")
    assert r.status_code == 422
    assert "objet_auditable" in r.json()["errors"]


def test_objet_auditable_libelle_expose(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    objet = typed.objet(processus=p, libelle="Captage")
    r = auth_rai.post("/api/v1/risks/", _body(v, p, objet_auditable=str(objet.id)), format="json")
    assert r.status_code == 201
    assert r.json()["objet_auditable_libelle"] == "Captage"


def test_reponse_et_priorite_valides(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    r = auth_rai.post("/api/v1/risks/", _body(v, p, reponse="TRAITER", priorite=3), format="json")
    assert r.status_code == 201
    assert (r.json()["reponse"], r.json()["priorite"]) == ("TRAITER", 3)
    r = auth_rai.post("/api/v1/risks/", _body(v, p, reponse="X"), format="json")
    assert r.status_code == 400
    r = auth_rai.post("/api/v1/risks/", _body(v, p, priorite=9), format="json")
    assert r.status_code == 400
    r = auth_rai.post("/api/v1/risks/", _body(v, p, reponse=""), format="json")
    assert r.status_code == 201


def test_libelle_unicode_conserve(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    texte = "Défaillance du réseau d'eau – Ouagadougou"
    r = auth_rai.post("/api/v1/risks/", _body(v, p, libelle=texte), format="json")
    assert r.json()["libelle"] == texte


def test_filtre_case_matrice(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    cible = typed.risque(version=v, probabilite=3, impact=5)
    typed.risque(version=v, probabilite=3, impact=4)
    typed.risque(version=v, probabilite=2, impact=5)
    r = auth_rai.get(f"/api/v1/risks/?version={v.id}&probabilite=3&impact=5")
    assert [x["id"] for x in r.json()["results"]] == [str(cible.id)]


def test_autres_filtres(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    objet = typed.objet(processus=p)
    a = typed.risque(
        version=v, processus=p, objet_auditable=objet, probabilite=5, impact=5, reponse="TRAITER"
    )
    typed.risque(version=v, probabilite=1, impact=1, priorite=3)

    def ids(qs: str) -> list[str]:
        return [x["id"] for x in auth_rai.get(f"/api/v1/risks/?{qs}").json()["results"]]

    assert ids(f"processus={p.id}") == [str(a.id)]
    assert ids(f"objet_auditable={objet.id}") == [str(a.id)]
    assert ids("niveau=ELEVE") == [str(a.id)]
    assert ids("reponse=TRAITER") == [str(a.id)]
    assert ids("priorite=3") != [str(a.id)]
    assert len(ids("priorite=2")) == 1
    assert auth_rai.get("/api/v1/risks/?niveau=INCONNU").status_code == 400
    assert auth_rai.get("/api/v1/risks/?version=pas-un-uuid").status_code == 400


def test_recherche_insensible_a_la_casse_sur_code_et_libelle(auth_rai: APIClient) -> None:
    p = typed.processus(code="FEP")
    typed.risque(processus=p, libelle="Fuite sur Conduite principale")
    typed.risque(libelle="Autre sujet")

    def n(q: str) -> int:
        return int(auth_rai.get(f"/api/v1/risks/?q={q}").json()["count"])

    assert n("conduite") == 1
    assert n("CONDUITE") == 1
    assert n("fep") == 1
    assert n("FEP-R") == 1


def test_tri_par_score_et_code(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    typed.risque(version=v, probabilite=1, impact=1)
    typed.risque(version=v, probabilite=5, impact=5)
    typed.risque(version=v, probabilite=2, impact=3)
    scores = [x["score"] for x in auth_rai.get("/api/v1/risks/?ordering=-score").json()["results"]]
    assert scores == [25, 6, 1]
    numeros = [x["numero"] for x in auth_rai.get("/api/v1/risks/").json()["results"]]
    assert numeros == sorted(numeros)


def test_liste_risques_requetes_bornees(
    auth_rai: APIClient, django_assert_max_num_queries: Any
) -> None:
    v = typed.version(annee=2026)
    for _ in range(30):
        typed.risque(version=v, objet_auditable=typed.objet())
    with django_assert_max_num_queries(3):
        r = auth_rai.get("/api/v1/risks/")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 25


def test_risque_supprime_absent_de_la_liste(auth_rai: APIClient) -> None:
    risque = typed.risque()
    assert auth_rai.delete(f"/api/v1/risks/{risque.id}/").status_code == 204
    assert auth_rai.get("/api/v1/risks/").json()["count"] == 0
    assert auth_rai.get(f"/api/v1/risks/{risque.id}/").status_code == 404


def test_numero_supprime_jamais_reattribue(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    premier = auth_rai.post("/api/v1/risks/", _body(v, p), format="json").json()
    auth_rai.delete(f"/api/v1/risks/{premier['id']}/")
    second = auth_rai.post("/api/v1/risks/", _body(v, p), format="json").json()
    assert second["code"] == "2-FEP-R2"


def test_page_size_risques_plafonne(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    for _ in range(3):
        typed.risque(version=v)
    r = auth_rai.get("/api/v1/risks/?page_size=2")
    assert len(r.json()["results"]) == 2
    assert r.json()["count"] == 3
    assert r.json()["next"]


def test_schema_expose_les_routes_referentiel(api_client: APIClient) -> None:
    r = api_client.get("/api/schema/")
    assert r.status_code == 200
    schema = yaml.safe_load(r.content)
    paths = schema["paths"]
    for chemin in (
        "/api/v1/risks/",
        "/api/v1/risks/{id}/",
        "/api/v1/risk-maps/{id}/matrix/",
        "/api/v1/risk-maps/{id}/compare/",
        "/api/v1/risk-maps/{id}/validate/",
        "/api/v1/auditable-objects/tree/",
        "/api/v1/directions/",
        "/api/v1/processes/",
    ):
        assert chemin in paths, chemin
    assert "put" not in paths["/api/v1/risks/{id}/"]
    composants = schema["components"]["schemas"]
    assert composants["Risque"]["properties"]["niveau"]["allOf"][0]["$ref"].endswith(
        "NiveauRisqueEnum"
    )
    for nom in (
        "TypeEntiteEnum",
        "FamilleProcessusEnum",
        "NatureObjetEnum",
        "StatutCartographieEnum",
        "NiveauRisqueEnum",
        "ReponseRisqueEnum",
        "PrioriteRisqueEnum",
    ):
        assert nom in composants, nom
    # les erreurs 422 sont documentées
    assert "422" in paths["/api/v1/risks/{id}/"]["patch"]["responses"]
    assert "400" in paths["/api/v1/risk-maps/{id}/compare/"]["get"]["responses"]
