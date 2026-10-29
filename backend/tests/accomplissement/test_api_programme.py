import pytest
from rest_framework.test import APIClient

from apps.accomplissement.models import ProgrammeDeTravail, StatutTest, TestPrevu
from apps.analyse.models import ObjectifAudit
from apps.missions.models import Mission, StatutEtape
from tests.accomplissement.fixtures_api import Equipe, client_de
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db

# (utilisateur, lire, créer un test complémentaire, déposer une pièce, valider une fiche)
MATRICE = [
    ("rai", 200, 201, 201, 200),
    ("chef", 200, 201, 201, 403),
    ("superviseur", 200, 403, 403, 200),
    ("auditeur", 200, 403, 201, 403),
    ("autre", 200, 403, 403, 403),
    ("non_confirme", 200, 403, 403, 403),
    ("non_affecte", 404, 404, 404, 404),
    ("audite", 403, 403, 403, 403),
    ("admin", 403, 403, 403, 403),
    ("dg", 403, 403, 403, 403),
]


def _depot(equipe: Equipe) -> dict[str, object]:
    from tests.accomplissement.fixtures_fiches import pdf

    return {"fiche": str(equipe.fiche1.pk), "fichier": pdf(), "libelle": "Facture"}


@pytest.mark.parametrize(("qui", "lire", "creer", "deposer", "valider"), MATRICE)
def test_matrice_droits_accomplissement(
    equipe_api: Equipe, qui: str, lire: int, creer: int, deposer: int, valider: int
) -> None:
    e = equipe_api
    c = client_de(e.users[qui])
    m = str(e.mission.pk)
    assert c.get(f"/api/v1/work-programs/?mission={m}").status_code == lire
    r = c.post(
        "/api/v1/planned-tests/",
        {"programme": str(e.test1.programme_id), "libelle": "Complément", "nature": "QCI"},
        format="json",
    )
    assert r.status_code == creer, r.json()
    r = c.post("/api/v1/evidence/", _depot(e), format="multipart")
    assert r.status_code == deposer, r.json()
    r = c.post(f"/api/v1/test-sheets/{e.fiche2.pk}/validate/")
    assert r.status_code == valider, r.json()


def test_programme_cycle(mission_viii: Mission, chef, api_client: APIClient) -> None:  # type: ignore[no-untyped-def]
    api_client.force_authenticate(chef)
    objectif = ObjectifAudit.objects.get(mission=mission_viii, numero=1)
    r = api_client.post("/api/v1/work-programs/", {}, format="json")
    assert r.status_code == 400
    r = api_client.post(
        "/api/v1/work-programs/",
        {"mission": str(mission_viii.pk), "objectif": str(objectif.pk), "techniques": "Entretiens"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["objectif_detail"] == {
        "id": str(objectif.pk),
        "code": "OA-01",
        "libelle": objectif.libelle,
    }
    assert corps["nb_tests"] == 0
    assert "MODIFIER_CONTENU" in corps["actions_possibles"]
    pid = corps["id"]
    r = api_client.get("/api/v1/work-programs/")
    assert r.status_code == 400
    r = api_client.get(f"/api/v1/work-programs/?mission={mission_viii.pk}&objectif={objectif.pk}")
    assert r.json()["count"] == 1
    r = api_client.patch(f"/api/v1/work-programs/{pid}/", {"commentaire": "Ok"}, format="json")
    assert r.status_code == 200 and r.json()["commentaire"] == "Ok"
    # L'objectif est fixé à la création.
    autre = ObjectifAudit.objects.get(mission=mission_viii, numero=2)
    r = api_client.patch(
        f"/api/v1/work-programs/{pid}/", {"objectif": str(autre.pk)}, format="json"
    )
    assert r.status_code == 400
    assert api_client.delete(f"/api/v1/work-programs/{pid}/").status_code == 204
    assert not ProgrammeDeTravail.objects.filter(pk=pid).exists()


def test_synthese_et_instantanes(equipe_api: Equipe) -> None:
    e = equipe_api
    c = client_de(e.users["superviseur"])
    r = c.get(f"/api/v1/work-programs/summary/?mission={e.mission.pk}")
    assert r.status_code == 200
    assert set(r.json()) == {
        "objectifs",
        "auditeurs",
        "total_charge",
        "budget_jours",
        "depassement_budget",
        "tests_sans_auditeur",
    }
    assert c.get("/api/v1/work-programs/summary/").status_code == 400
    r = c.get(f"/api/v1/work-programs/snapshots/?mission={e.mission.pk}")
    assert r.status_code == 200
    assert (
        client_de(e.users["audite"])
        .get(f"/api/v1/work-programs/summary/?mission={e.mission.pk}")
        .status_code
        == 403
    )


def test_tests_prevus_complementaire_deduit_filtres_abandon(equipe_api: Equipe) -> None:
    e = equipe_api
    c = client_de(e.users["chef"])
    r = c.post(
        "/api/v1/planned-tests/",
        {"programme": str(e.test1.programme_id), "libelle": "Complément", "nature": "QCI"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["complementaire"] is True
    assert r.json()["code"] == "T-03"
    nouveau = r.json()["id"]
    m = e.mission.pk
    liste = c.get(f"/api/v1/planned-tests/?mission={m}&complementaire=true").json()
    assert [t["id"] for t in liste["results"]] == [nouveau]
    assert c.get(f"/api/v1/planned-tests/?mission={m}&mine=true").json()["count"] == 0
    mien = client_de(e.users["auditeur"]).get(f"/api/v1/planned-tests/?mission={m}&mine=true")
    assert [t["id"] for t in mien.json()["results"]] == [str(e.test1.pk)]
    detail = mien.json()["results"][0]
    assert detail["fiche"] == {"id": str(e.fiche1.pk), "statut": "BROUILLON", "conclusion": ""}
    assert detail["auditeur_detail"]["id"] == e.users["auditeur"].pk
    # Abandon : motif obligatoire (422), puis abandonné.
    r = c.post(f"/api/v1/planned-tests/{nouveau}/abandon/", {"motif": "   "}, format="json")
    assert r.status_code == 400
    r = c.post(f"/api/v1/planned-tests/{nouveau}/abandon/", {"motif": "Sans objet"}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "ABANDONNE"
    assert TestPrevu.objects.get(pk=nouveau).statut == StatutTest.ABANDONNE
    assert c.get(f"/api/v1/planned-tests/?mission={m}&statut=ABANDONNE").json()["count"] == 1
    assert c.get(f"/api/v1/planned-tests/?mission={m}&ordering=-code").json()["count"] == 3


def test_actions_possibles_concorde_avec_les_routes(equipe_api: Equipe) -> None:
    e = equipe_api
    for qui in ("rai", "chef", "superviseur", "auditeur", "autre", "non_confirme"):
        c = client_de(e.users[qui])
        for test in (e.test1, e.test2):
            actions = c.get(f"/api/v1/planned-tests/{test.pk}/").json()["actions_possibles"]
            r = c.patch(f"/api/v1/planned-tests/{test.pk}/", {"procedure": "P"}, format="json")
            assert (r.status_code == 200) == ("MODIFIER" in actions), (qui, r.json())
        for fiche in (e.fiche1, e.fiche2):
            actions = c.get(f"/api/v1/test-sheets/{fiche.pk}/").json()["actions_possibles"]
            r = c.patch(
                f"/api/v1/test-sheets/{fiche.pk}/", {"travaux_realises": "x"}, format="json"
            )
            assert (r.status_code == 200) == ("MODIFIER" in actions), (qui, r.json())


@pytest.mark.parametrize("figee", ["suspendue", "viii_close", "xii_close"])
def test_api_gel_422_routes_lot6(equipe_api: Equipe, figee: str) -> None:
    e = equipe_api
    if figee == "suspendue":
        Mission.objects.filter(pk=e.mission.pk).update(statut="SUSPENDUE")
    elif figee == "viii_close":
        forcer_etapes(e.mission, {8: StatutEtape.VALIDEE})
    else:
        forcer_etapes(e.mission, {12: StatutEtape.VALIDEE})
    c = client_de(e.users["rai"])
    if figee == "viii_close":
        r = c.patch(
            f"/api/v1/work-programs/{e.test1.programme_id}/",
            {"commentaire": "x"},
            format="json",
        )
    elif figee == "xii_close":
        r = c.patch(f"/api/v1/test-sheets/{e.fiche1.pk}/", {"resultat": "x"}, format="json")
    else:
        r = c.patch(f"/api/v1/test-sheets/{e.fiche1.pk}/", {"resultat": "x"}, format="json")
    assert r.status_code == 422, r.json()
    assert set(r.json()) == {"detail", "errors"}
