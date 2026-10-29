from rest_framework.test import APIClient


def test_schema_expose_les_routes_analyse(api_client: APIClient, db: None) -> None:
    chemins = api_client.get("/api/schema/?format=json").json()["paths"]
    for chemin in (
        "/api/v1/analysis-questionnaires/",
        "/api/v1/analysis-questions/{id}/",
        "/api/v1/process-descriptions/",
        "/api/v1/segregation-grids/",
        "/api/v1/marc-lines/initialize/",
        "/api/v1/strengths-weaknesses/",
        "/api/v1/audit-frameworks/{id}/",
        "/api/v1/audit-frameworks/{id}/opinions/",
        "/api/v1/audit-frameworks/{id}/snapshot/",
        "/api/v1/audit-objectives/initialize/",
        "/api/v1/orientation-reports/{id}/",
    ):
        assert chemin in chemins, chemin
