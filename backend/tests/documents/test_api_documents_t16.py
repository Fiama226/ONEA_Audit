# ruff: noqa: F401, F811
"""Lot 9 T16 : HEAD non journalisé, fichier de gabarit absent (409), accès, OpenAPI, requêtes."""

from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.documents.models import ConsultationDocument, DocumentVersion, GabaritDocument
from apps.documents.moteur.registre import TypeDocument
from apps.missions.models import Mission
from apps.users.models import User

from .api_fixtures import Utilisateurs, utilisateurs, version_prete_mission
from .conftest import chemin_fichier

pytestmark = pytest.mark.django_db

INTROUVABLE = "Le fichier du gabarit est introuvable sur le serveur : contactez l'administrateur."


# --- HEAD n'est pas une consultation -------------------------------------------------------------


def test_head_telechargement_version_non_journalise(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    url = f"/api/v1/document-versions/{version_prete_mission.pk}/download/?format=docx"
    api_client.force_authenticate(rai)
    r = api_client.head(url)
    assert r.status_code == 200
    assert ConsultationDocument.objects.count() == 0
    assert api_client.get(url).status_code == 200
    assert ConsultationDocument.objects.count() == 1


def test_head_fichier_gabarit_non_journalise(
    api_client: APIClient, gabarit_actif_test: GabaritDocument, admin: User
) -> None:
    url = f"/api/v1/templates/{gabarit_actif_test.pk}/file/"
    api_client.force_authenticate(admin)
    assert api_client.head(url).status_code == 200
    assert ConsultationDocument.objects.count() == 0
    assert api_client.get(url).status_code == 200
    assert ConsultationDocument.objects.count() == 1


# --- fichier de gabarit absent du disque : 409 ---------------------------------------------------


@pytest.fixture
def gabarit_sans_fichier(gabarit_actif_test: GabaritDocument) -> GabaritDocument:
    chemin_fichier(gabarit_actif_test.fichier.name).unlink()
    return gabarit_actif_test


def test_gabarit_sans_fichier_409_sur_fichier_apercu_activation(
    api_client: APIClient, gabarit_sans_fichier: GabaritDocument, admin: User
) -> None:
    base = f"/api/v1/templates/{gabarit_sans_fichier.pk}"
    api_client.force_authenticate(admin)
    for r in (
        api_client.get(f"{base}/file/"),
        api_client.get(f"{base}/preview/?format=docx"),
    ):
        assert r.status_code == 409, r.content
        assert r.json()["detail"] == INTROUVABLE
    assert ConsultationDocument.objects.count() == 0


def test_activation_d_un_depose_sans_fichier_409(
    api_client: APIClient, gabarit_sans_fichier: GabaritDocument, admin: User
) -> None:
    GabaritDocument.objects.filter(pk=gabarit_sans_fichier.pk).update(statut="DEPOSE")
    api_client.force_authenticate(admin)
    r = api_client.post(f"/api/v1/templates/{gabarit_sans_fichier.pk}/activate/")
    assert r.status_code == 409 and r.json()["detail"] == INTROUVABLE
    assert GabaritDocument.objects.get(pk=gabarit_sans_fichier.pk).statut == "DEPOSE"


def test_generation_refusee_409_sans_fichier_de_gabarit(
    api_client: APIClient,
    gabarit_sans_fichier: GabaritDocument,
    objet_test: Mission,
    rai: User,
) -> None:
    api_client.force_authenticate(rai)
    corps = {"type_document": "TEST_DOC", "objet": str(objet_test.pk)}
    r = api_client.post("/api/v1/documents/generate/", corps, format="json")
    assert r.status_code == 409 and r.json()["detail"] == INTROUVABLE
    assert DocumentVersion.all_objects.count() == 0  # aucune version vouée à l'échec


# --- accès ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("qui", ["chef", "audite_affecte", "auditeur_desaffecte"])
def test_auditeur_et_audite_403_sur_les_gabarits(
    api_client: APIClient,
    gabarit_actif_test: GabaritDocument,
    utilisateurs: Utilisateurs,
    qui: str,
) -> None:
    api_client.force_authenticate(utilisateurs[qui])
    base = f"/api/v1/templates/{gabarit_actif_test.pk}"
    assert api_client.get("/api/v1/templates/").status_code == 403
    assert api_client.get(f"{base}/").status_code == 403
    assert api_client.get(f"{base}/file/").status_code == 403
    assert api_client.get(f"{base}/preview/?format=docx").status_code == 403
    assert api_client.post(f"{base}/activate/").status_code == 403


def test_audite_avant_ordre_de_mission_404(
    api_client: APIClient,
    version_prete_mission: DocumentVersion,
    utilisateurs: Utilisateurs,
) -> None:
    Mission.objects.filter(pk=version_prete_mission.document.mission_id).update(
        ordre_mission_emis_le=None
    )
    api_client.force_authenticate(utilisateurs["audite_affecte"])
    doc, version = version_prete_mission.document_id, version_prete_mission.pk
    assert api_client.get("/api/v1/documents/").json()["count"] == 0
    assert api_client.get(f"/api/v1/documents/{doc}/").status_code == 404
    assert api_client.get(f"/api/v1/document-versions/{version}/").status_code == 404
    url = f"/api/v1/document-versions/{version}/download/?format=docx"
    assert api_client.get(url).status_code == 404
    mission = version_prete_mission.document.mission_id
    corps = {"type_document": "TEST_DOC", "objet": str(mission)}
    assert api_client.post("/api/v1/documents/generate/", corps, format="json").status_code == 404
    assert api_client.get(f"/api/v1/documents/available/?mission={mission}").status_code == 404
    assert ConsultationDocument.objects.count() == 0


# --- branche Content-Length ----------------------------------------------------------------------


def test_depot_refuse_sur_content_length_declare(
    api_client: APIClient,
    admin: User,
    type_test: TypeDocument,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.DOCUMENTS_MAX_GABARIT_MO = 1
    api_client.force_authenticate(admin)
    import apps.documents.views as vues

    lu: list[bool] = []
    monkeypatch.setattr(
        vues.serializers.GabaritDepotSerializer,
        "is_valid",
        lambda *a, **k: lu.append(True),
    )
    r = api_client.generic(
        "POST",
        "/api/v1/templates/",
        b"--x--",
        content_type="multipart/form-data; boundary=x",
        CONTENT_LENGTH=str(5 * 1024 * 1024),
    )
    assert r.status_code == 422 and "1 Mo" in r.json()["errors"]["fichier"][0]
    assert lu == []  # refusé avant l'analyse du corps


def test_depot_content_length_invalide_ou_modeste_n_est_pas_refuse_a_tort(
    api_client: APIClient, admin: User, type_test: TypeDocument, settings: Any
) -> None:
    settings.DOCUMENTS_MAX_GABARIT_MO = 1
    api_client.force_authenticate(admin)
    r = api_client.generic(
        "POST",
        "/api/v1/templates/",
        b"--x--",
        content_type="multipart/form-data; boundary=x",
        CONTENT_LENGTH="pas-un-nombre",
    )
    assert r.status_code == 400  # corps invalide, mais pas « trop gros »


# --- requêtes bornées -----------------------------------------------------------------------------


def _requetes(api_client: APIClient, url: str) -> int:
    with CaptureQueriesContext(connection) as c:
        assert api_client.get(url).status_code == 200
    return len(c)


def test_liste_documents_requetes_independantes_du_nombre_de_versions(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    api_client.force_authenticate(rai)
    mission = version_prete_mission.document.mission_id
    disponibles = f"/api/v1/documents/available/?mission={mission}"
    _requetes(api_client, "/api/v1/documents/")  # échauffement (types de contenu, caches)
    avant = _requetes(api_client, "/api/v1/documents/")
    avant_dispo = _requetes(api_client, disponibles)
    for n in (2, 3, 4):
        DocumentVersion.objects.create(
            document=version_prete_mission.document,
            numero_version=n,
            gabarit=version_prete_mission.gabarit,
            contexte={},
            empreinte_contexte=str(n) * 64,
            demandee_par=rai,
            created_by=rai,
        )
    assert _requetes(api_client, "/api/v1/documents/") == avant
    detail = f"/api/v1/documents/{version_prete_mission.document_id}/"
    assert _requetes(api_client, detail) <= 12
    assert _requetes(api_client, disponibles) == avant_dispo


# --- OpenAPI -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return dict(SchemaGenerator().get_schema(request=None, public=True))


def test_openapi_generation_repond_202_seulement(schema: dict[str, Any]) -> None:
    reponses = schema["paths"]["/api/v1/documents/generate/"]["post"]["responses"]
    assert "202" in reponses and "200" not in reponses


@pytest.mark.parametrize(
    ("chemin", "types"),
    [
        (
            "/api/v1/templates/{id}/file/",
            {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ),
        (
            "/api/v1/templates/{id}/preview/",
            {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/pdf",
            },
        ),
        (
            "/api/v1/document-versions/{id}/download/",
            {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/pdf",
            },
        ),
    ],
)
def test_openapi_reponses_binaires(schema: dict[str, Any], chemin: str, types: set[str]) -> None:
    contenu = schema["paths"][chemin]["get"]["responses"]["200"]["content"]
    assert set(contenu) == types
    for media in contenu.values():
        assert media["schema"] == {"type": "string", "format": "binary"}
