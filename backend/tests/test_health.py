from rest_framework.test import APIClient


def test_health_returns_ok(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/health/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
