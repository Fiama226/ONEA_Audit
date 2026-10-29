from typing import Any

import pytest
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_schema_expose_les_routes_documents() -> None:
    generateur = SchemaGenerator()  # type: ignore[no-untyped-call]
    schema: dict[str, Any] = dict(generateur.get_schema(request=None, public=True))  # type: ignore[no-untyped-call]
    attendus = {
        "/api/v1/document-types/",
        "/api/v1/templates/",
        "/api/v1/templates/{id}/",
        "/api/v1/templates/{id}/activate/",
        "/api/v1/templates/{id}/file/",
        "/api/v1/templates/{id}/preview/",
        "/api/v1/numbering-formats/",
        "/api/v1/numbering-formats/{type_document}/",
        "/api/v1/numbering-formats/preview/",
        "/api/v1/documents/",
        "/api/v1/documents/{id}/",
        "/api/v1/documents/available/",
        "/api/v1/documents/generate/",
        "/api/v1/document-versions/{id}/",
        "/api/v1/document-versions/{id}/download/",
        "/api/v1/document-versions/{id}/retry-pdf/",
        "/api/v1/document-versions/{id}/consultations/",
    }
    assert attendus <= set(schema["paths"])
    composants = schema["components"]["schemas"]
    for nom in (
        "ChampContrat",
        "TypeDocument",
        "GabaritResume",
        "GabaritDocument",
        "FormatNumerotation",
        "DocumentListe",
        "Document",
        "DocumentVersion",
        "DocumentDisponible",
        "GenerationRequest",
        "Consultation",
        "StatutGabaritEnum",
        "StatutGenerationEnum",
        "StatutPdfEnum",
        "PorteeNumerotationEnum",
        "FormatFichierEnum",
        "TypeChampEnum",
    ):
        assert nom in composants, nom
    assert "contexte" not in composants["DocumentVersion"]["properties"]
    assert "put" not in schema["paths"]["/api/v1/templates/{id}/"]


def test_erreurs_au_format_unique(api_client: APIClient, rai: User, dg: User) -> None:
    api_client.force_authenticate(dg)
    for url in ("/api/v1/documents/", "/api/v1/templates/"):
        r = api_client.get(url)
        assert r.status_code == 403 and set(r.json()) == {"detail", "errors"}
    api_client.force_authenticate(rai)
    r = api_client.get("/api/v1/templates/00000000-0000-4000-8000-000000000000/")
    assert r.status_code == 404 and r.json() == {"detail": "Non trouvé.", "errors": {}}
