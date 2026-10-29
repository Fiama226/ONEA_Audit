# ruff: noqa: F401, F811
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.documents.models import DocumentVersion, GabaritDocument
from apps.documents.moteur.registre import TypeDocument
from apps.missions.models import Mission
from apps.users.models import User

from .api_fixtures import Utilisateurs, octets, utilisateurs, version_prete_mission
from .conftest import chemin_fichier

pytestmark = pytest.mark.django_db

GENERER = "/api/v1/documents/generate/"


def test_generate_202_puis_polling_prete(
    api_client: APIClient,
    rai: User,
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    pdf_factice: bytes,
    django_capture_on_commit_callbacks: Any,
) -> None:
    api_client.force_authenticate(rai)
    with django_capture_on_commit_callbacks(execute=True):
        r = api_client.post(
            GENERER, {"type_document": "TEST_DOC", "objet": str(objet_test.pk)}, format="json"
        )
    assert r.status_code == 202, r.content
    assert r.json()["statut"] == "EN_ATTENTE" and r.json()["numero_version"] == 1
    assert "contexte" not in r.json()
    corps = api_client.get(f"/api/v1/document-versions/{r.json()['id']}/").json()
    assert corps["statut"] == "PRETE" and corps["statut_pdf"] == "PRET"
    assert len(corps["empreinte_docx"]) == 64 and corps["taille_pdf"] > 0
    assert corps["gabarit"]["version"] == 1 and corps["demandee_par"]["id"] == rai.id
    doc = api_client.get(f"/api/v1/documents/{corps['document']}/").json()
    assert doc["numero"] == "DAI/2026/M01/TD-01" and len(doc["versions"]) == 1
    assert doc["derniere_version"]["id"] == corps["id"] and doc["objet_id"] == str(objet_test.pk)


def test_generate_deja_a_jour_422(
    api_client: APIClient,
    rai: User,
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    pdf_factice: bytes,
    django_capture_on_commit_callbacks: Any,
) -> None:
    api_client.force_authenticate(rai)
    corps = {"type_document": "TEST_DOC", "objet": str(objet_test.pk)}
    with django_capture_on_commit_callbacks(execute=True):
        assert api_client.post(GENERER, corps, format="json").status_code == 202
    r = api_client.post(GENERER, corps, format="json")
    assert r.status_code == 422 and "déjà à jour" in r.json()["detail"]
    assert DocumentVersion.all_objects.count() == 1


def test_generate_corps_invalide(api_client: APIClient, rai: User, type_test: TypeDocument) -> None:
    api_client.force_authenticate(rai)
    r = api_client.post(GENERER, {"type_document": "TEST_DOC"}, format="json")
    assert r.status_code == 400 and "objet" in r.json()["errors"]
    inconnu = {"type_document": "NOPE", "objet": "00000000-0000-4000-8000-000000000000"}
    r = api_client.post(GENERER, inconnu, format="json")
    assert r.status_code == 400 and "type_document" in r.json()["errors"]
    absent = {"type_document": "TEST_DOC", "objet": "00000000-0000-4000-8000-000000000000"}
    assert api_client.post(GENERER, absent, format="json").status_code == 404


def test_available_par_role(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
) -> None:
    mission = version_prete_mission.document.mission_id
    url = f"/api/v1/documents/available/?mission={mission}"
    api_client.force_authenticate(utilisateurs["rai"])
    ligne = api_client.get(url).json()[0]
    assert ligne["type_document"] == "TEST_DOC" and ligne["libelle"] == "Document de test"
    assert ligne["peut_generer"] is True and ligne["raison"] is None and ligne["en_cours"] is False
    assert ligne["document"]["numero"].endswith("TD-01")
    assert ligne["objet_id"] == str(mission)
    api_client.force_authenticate(utilisateurs["chef"])
    ligne = api_client.get(url).json()[0]
    assert ligne["peut_generer"] is False and ligne["raison"]
    api_client.force_authenticate(utilisateurs["auditeur_desaffecte"])
    assert api_client.get(url).status_code == 404
    api_client.force_authenticate(utilisateurs["admin"])
    assert api_client.get(url).status_code == 403
    api_client.force_authenticate(utilisateurs["rai"])
    assert api_client.get("/api/v1/documents/available/").status_code == 400


def test_available_mission_figee_raison(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    Mission.objects.filter(pk=version_prete_mission.document.mission_id).update(statut="SUSPENDUE")
    api_client.force_authenticate(rai)
    url = f"/api/v1/documents/available/?mission={version_prete_mission.document.mission_id}"
    ligne = api_client.get(url).json()[0]
    assert ligne["peut_generer"] is False
    assert "aucun document ne peut être généré" in ligne["raison"]


def test_download_en_tetes(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    api_client.force_authenticate(rai)
    base = f"/api/v1/document-versions/{version_prete_mission.pk}/download/"
    r = api_client.get(base + "?format=docx")
    assert r.status_code == 200
    assert r["Content-Disposition"].startswith("attachment;")
    assert "DAI-2026-M01-TD-01_v1.docx" in r["Content-Disposition"]
    assert r["Cache-Control"] == "private, no-store" and r["X-Content-Type-Options"] == "nosniff"
    assert r["Content-Type"].startswith("application/vnd.openxmlformats")
    assert octets(r)[:2] == b"PK"
    assert api_client.get(base + "?format=odt").status_code == 400
    assert api_client.get(base + "?format=pdf").status_code == 422  # no PDF yet


def test_download_409_fichier_altere(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    chemin_fichier(version_prete_mission.fichier_docx.name).write_bytes(b"altere")
    api_client.force_authenticate(rai)
    url = f"/api/v1/document-versions/{version_prete_mission.pk}/download/?format=docx"
    r = api_client.get(url)
    assert r.status_code == 409
    assert set(r.json()) == {"detail", "errors"} and "altéré" in r.json()["detail"]


def test_retry_pdf(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
    pdf_factice: bytes,
    django_capture_on_commit_callbacks: Any,
) -> None:
    DocumentVersion.all_objects.filter(pk=version_prete_mission.pk).update(
        statut_pdf="ECHEC", erreur_pdf="panne"
    )
    detail = f"/api/v1/document-versions/{version_prete_mission.pk}/"
    url = detail + "retry-pdf/"
    api_client.force_authenticate(utilisateurs["chef"])
    assert api_client.post(url).status_code == 403
    api_client.force_authenticate(utilisateurs["rai"])
    assert api_client.get(detail).json()["peut_relancer_pdf"] is True
    with django_capture_on_commit_callbacks(execute=True):
        r = api_client.post(url)
    assert r.status_code == 200
    assert api_client.get(detail).json()["statut_pdf"] == "PRET"
    assert api_client.post(url).status_code == 422


def test_filtres_documents(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    api_client.force_authenticate(rai)
    m = version_prete_mission.document.mission_id
    base = "/api/v1/documents/"
    assert api_client.get(f"{base}?mission={m}").json()["count"] == 1
    assert api_client.get(f"{base}?type_document=AUTRE").json()["count"] == 0
    assert api_client.get(f"{base}?q=td-01").json()["count"] == 1
    assert api_client.get(f"{base}?q=zzz").json()["count"] == 0
    ligne = api_client.get(base).json()["results"][0]
    assert ligne["nombre_versions"] == 1 and ligne["derniere_version"]["numero_version"] == 1
    assert ligne["mission"]["reference"] == "DAI/2026/M01"


def test_listes_requetes_bornees(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    rai: User,
    django_assert_max_num_queries: Any,
) -> None:
    api_client.force_authenticate(rai)
    with django_assert_max_num_queries(5):
        assert api_client.get("/api/v1/documents/").status_code == 200
