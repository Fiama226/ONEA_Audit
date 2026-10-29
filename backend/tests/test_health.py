from rest_framework.test import APIClient

from config import __version__


def test_health_returns_ok(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/health/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_health_expose_stockage_documents(api_client: APIClient) -> None:
    body = api_client.get("/api/v1/health/").json()
    assert body["status"] == "ok"
    assert body["stockage_documents"] in {"ok", "faible", "indisponible"}
