from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from tests.factories import QuestionFactory, QuestionnaireFactory

from .fixtures_api import Equipe, equipe_complete, equipe_en_iii  # noqa: F401


def test_questionnaire_cycle(api_client: APIClient, equipe_en_iii: Equipe) -> None:  # noqa: F811
    m, users = equipe_en_iii
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/analysis-questionnaires/",
        {"mission": str(m.id), "type": "PRISE_CONNAISSANCE"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["nb_questions"] > 0
    assert corps["nb_repondues"] == 0
    assert corps["etape_close"] is False
    qid = corps["id"]
    # Doublon : 422 posé sur le champ.
    r = api_client.post(
        "/api/v1/analysis-questionnaires/",
        {"mission": str(m.id), "type": "PRISE_CONNAISSANCE"},
        format="json",
    )
    assert r.status_code == 422
    assert "type" in r.json()["errors"]
    # Type inconnu : 400 (le sérialiseur borne les valeurs).
    r = api_client.post(
        "/api/v1/analysis-questionnaires/", {"mission": str(m.id), "type": "X"}, format="json"
    )
    assert r.status_code == 400
    # Le type ne change pas.
    r = api_client.patch(f"/api/v1/analysis-questionnaires/{qid}/", {"type": "QCI"}, format="json")
    assert r.status_code == 400
    r = api_client.patch(
        f"/api/v1/analysis-questionnaires/{qid}/", {"titre": "Mon titre"}, format="json"
    )
    assert r.status_code == 200
    assert r.json()["titre"] == "Mon titre"
    r = api_client.get(f"/api/v1/analysis-questionnaires/?mission={m.id}&type=PRISE_CONNAISSANCE")
    assert r.json()["count"] == 1
    assert api_client.delete(f"/api/v1/analysis-questionnaires/{qid}/").status_code == 204


def test_questions_cycle_et_liste_non_paginee(
    api_client: APIClient,
    equipe_en_iii: Equipe,  # noqa: F811
) -> None:
    m, users = equipe_en_iii
    questionnaire = QuestionnaireFactory(mission=m)
    api_client.force_authenticate(users["auditeur_confirme"])
    r = api_client.post(
        "/api/v1/analysis-questions/",
        {"questionnaire": str(questionnaire.id), "theme": "T", "libelle": "Pourquoi ?"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    qid = r.json()["id"]
    assert r.json()["repondue"] is False
    r = api_client.patch(
        f"/api/v1/analysis-questions/{qid}/",
        {"appreciation": "OUI", "reponse": "Parce que."},
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert r.json()["repondue"] is True
    r = api_client.patch(
        f"/api/v1/analysis-questions/{qid}/", {"questionnaire": str(m.id)}, format="json"
    )
    assert r.status_code == 400
    r = api_client.get(f"/api/v1/analysis-questions/?questionnaire={questionnaire.id}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert [x["id"] for x in r.json()] == [qid]
    assert api_client.delete(f"/api/v1/analysis-questions/{qid}/").status_code == 204


def test_description_upsert_et_filtre(api_client: APIClient, equipe_en_iii: Equipe) -> None:  # noqa: F811
    m, users = equipe_en_iii
    processus = m.processus.first()
    assert processus is not None
    api_client.force_authenticate(users["chef"])
    corps = {
        "mission": str(m.id),
        "processus": str(processus.id),
        "typologie": "SUPPORT",
        "categories_objectifs": ["OPERATIONNELS", "CONFORMITE"],
        "description": "Achats.",
    }
    r = api_client.post("/api/v1/process-descriptions/", corps, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["processus_code"] == processus.code
    assert r.json()["categories_objectifs"] == ["OPERATIONNELS", "CONFORMITE"]
    r2 = api_client.post(
        "/api/v1/process-descriptions/", {**corps, "description": "Achats v2."}, format="json"
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == r.json()["id"]
    assert r2.json()["description"] == "Achats v2."
    r = api_client.get(f"/api/v1/process-descriptions/?mission={m.id}&processus={processus.id}")
    assert r.json()["count"] == 1
    r = api_client.post(
        "/api/v1/process-descriptions/",
        {**corps, "categories_objectifs": ["INCONNU"]},
        format="json",
    )
    assert r.status_code == 400


def test_grille_cycle_et_analyse(api_client: APIClient, equipe_en_iii: Equipe) -> None:  # noqa: F811
    m, users = equipe_en_iii
    processus = m.processus.first()
    assert processus is not None
    api_client.force_authenticate(users["chef"])
    corps = {
        "mission": str(m.id),
        "processus": str(processus.id),
        "taches": ["Saisir", "Valider"],
        "acteurs": ["Agent"],
        "cellules": [{"tache": 0, "acteur": 0, "roles": ["EXECUTE", "AUTORISE"]}],
    }
    r = api_client.post("/api/v1/segregation-grids/", corps, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["analyse"]["taches_sans_acteur"] == ["Valider"]
    assert r.json()["analyse"]["cumuls"] == [
        {"tache": "Saisir", "acteur": "Agent", "roles": ["AUTORISE", "EXECUTE"]}
    ]
    gid = r.json()["id"]
    r = api_client.patch(
        f"/api/v1/segregation-grids/{gid}/", {"commentaire": "Revu."}, format="json"
    )
    assert r.status_code == 200
    assert r.json()["taches"] == ["Saisir", "Valider"]
    assert r.json()["commentaire"] == "Revu."


def test_grille_invalide_422_sur_le_champ(api_client: APIClient, equipe_en_iii: Equipe) -> None:  # noqa: F811
    m, users = equipe_en_iii
    processus = m.processus.first()
    assert processus is not None
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/segregation-grids/",
        {
            "mission": str(m.id),
            "processus": str(processus.id),
            "taches": ["A"],
            "acteurs": ["B"],
            "cellules": [{"tache": 5, "acteur": 0, "roles": ["EXECUTE"]}],
        },
        format="json",
    )
    assert r.status_code == 422
    assert "cellules" in r.json()["errors"]


def test_travaux_iii_fermes_apres_terminaison_422(
    api_client: APIClient,
    equipe_en_iii: Equipe,  # noqa: F811
) -> None:
    from apps.missions.models import EtapeMission, StatutEtape

    m, users = equipe_en_iii
    questionnaire = QuestionnaireFactory(mission=m)
    question = QuestionFactory(questionnaire=questionnaire)
    EtapeMission.objects.filter(mission=m, numero=3).update(statut=StatutEtape.TERMINEE)
    api_client.force_authenticate(users["chef"])
    r = api_client.patch(
        f"/api/v1/analysis-questions/{question.id}/", {"theme": "Z"}, format="json"
    )
    assert r.status_code == 422
    assert "III" in r.json()["detail"]
    r = api_client.get(f"/api/v1/analysis-questionnaires/?mission={m.id}")
    assert r.json()["results"][0]["etape_close"] is True


def test_listes_requetes_bornees_etape_iii(api_client: APIClient, equipe_en_iii: Equipe) -> None:  # noqa: F811
    m, users = equipe_en_iii
    questionnaire = QuestionnaireFactory(mission=m)
    for _ in range(4):
        QuestionFactory(questionnaire=questionnaire)
    api_client.force_authenticate(users["rai"])
    with CaptureQueriesContext(connection) as q:
        r = api_client.get(f"/api/v1/analysis-questions/?questionnaire={questionnaire.id}")
    assert r.status_code == 200
    assert len(q) <= 3, [x["sql"] for x in q.captured_queries]
    with CaptureQueriesContext(connection) as q:
        r = api_client.get(f"/api/v1/analysis-questionnaires/?mission={m.id}")
    assert r.status_code == 200
    assert len(q) <= 5, [x["sql"] for x in q.captured_queries]
