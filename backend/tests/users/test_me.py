from rest_framework.test import APIClient

from apps.users.models import User


def test_me_returns_profile(auth_client: APIClient, user: User) -> None:
    r = auth_client.get("/api/v1/me/")
    assert r.status_code == 200
    assert r.json() == {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": "Awa",
        "last_name": "Ouedraogo",
        "role": "AUDITEUR",
        "direction_code": "DAI",
        "fonction": "Auditeur interne",
    }


def test_me_anonymous_401(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_me_is_read_only(auth_client: APIClient) -> None:
    assert auth_client.post("/api/v1/me/", {"role": "ADMIN"}, format="json").status_code == 405


def test_schema_exposes_me_component(api_client: APIClient) -> None:
    schema = api_client.get("/api/schema/?format=json").json()
    assert "Me" in schema["components"]["schemas"]
