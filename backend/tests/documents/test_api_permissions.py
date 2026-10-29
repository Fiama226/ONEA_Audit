# ruff: noqa: F401, F811
import pytest
from rest_framework.test import APIClient

from apps.documents.models import DocumentVersion
from apps.missions.models import Mission

from .api_fixtures import Utilisateurs, utilisateurs, version_prete_mission

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("qui", "lister", "telecharger", "generer"),
    [
        ("rai", 200, 200, 202),
        ("chef", 200, 200, 403),
        ("auditeur_desaffecte", 200, 404, 404),
        ("audite_affecte", 200, 200, 403),
        ("admin", 403, 403, 403),
        ("dg", 403, 403, 403),
    ],
)
def test_matrice_droits_documents(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
    qui: str,
    lister: int,
    telecharger: int,
    generer: int,
) -> None:
    api_client.force_authenticate(utilisateurs[qui])
    assert api_client.get("/api/v1/documents/").status_code == lister
    url = f"/api/v1/document-versions/{version_prete_mission.pk}/download/?format=docx"
    assert api_client.get(url).status_code == telecharger
    mission = Mission.objects.get(pk=version_prete_mission.document.mission_id)
    corps = {"type_document": "TEST_DOC", "objet": str(mission.pk)}
    r = api_client.post("/api/v1/documents/generate/", corps, format="json")
    assert r.status_code == generer


def test_non_authentifie_401(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/documents/").status_code == 401
    assert api_client.get("/api/v1/templates/").status_code == 401


def test_auditeur_desaffecte_ne_voit_rien(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
) -> None:
    api_client.force_authenticate(utilisateurs["auditeur_desaffecte"])
    assert api_client.get("/api/v1/documents/").json()["count"] == 0
    doc = version_prete_mission.document_id
    assert api_client.get(f"/api/v1/documents/{doc}/").status_code == 404
    v = version_prete_mission.pk
    assert api_client.get(f"/api/v1/document-versions/{v}/").status_code == 404


def test_consultations_rai_seul(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
) -> None:
    url = f"/api/v1/document-versions/{version_prete_mission.pk}/consultations/"
    api_client.force_authenticate(utilisateurs["rai"])
    api_client.get(f"/api/v1/document-versions/{version_prete_mission.pk}/download/?format=docx")
    r = api_client.get(url)
    assert r.status_code == 200 and r.json()["count"] == 1
    assert set(r.json()["results"][0]) == {"utilisateur", "le", "format", "adresse_ip"}
    for qui in ("chef", "audite_affecte", "admin"):
        api_client.force_authenticate(utilisateurs[qui])
        assert api_client.get(url).status_code == 403


def test_aucune_route_hors_api(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
) -> None:
    """The stored file is only reachable through `download`."""
    api_client.force_authenticate(utilisateurs["rai"])
    cle = version_prete_mission.fichier_docx.name
    for chemin in (f"/media/{cle}", f"/documents/{cle}", f"/files/{cle}", f"/{cle}"):
        assert api_client.get(chemin).status_code == 404
    corps = api_client.get(f"/api/v1/document-versions/{version_prete_mission.pk}/").json()
    assert "fichier_docx" not in corps and "contexte" not in corps
