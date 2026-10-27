import uuid
from typing import Any
from unittest import mock

import pytest
import requests
from django.core.exceptions import SuspiciousOperation
from rest_framework.test import APIClient

from apps.users.models import Role, User
from apps.users.oidc import OneaOIDCBackend

from ..factories import make_user

SESSION_EXPIRED = {"detail": "Session expirée ou jeton invalide.", "errors": {}}
SUB = "5b1c3a52-7c0e-4a3e-9d0b-1f6f6d0f2a11"


def claims(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sub": SUB,
        "email": "Rai@onea.bf",
        "preferred_username": "rai",
        "given_name": "Salif",
        "family_name": "Sawadogo",
        "roles": ["RAI"],
        "direction": "DAI",
        "fonction": "Responsable audit interne",
    }
    base.update(kwargs)
    return base


@pytest.fixture
def backend() -> OneaOIDCBackend:
    return OneaOIDCBackend()


# --- role mapping ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (["ADMIN", "RAI", "AUDITEUR", "DG", "AUDITE"], Role.ADMIN),
        (["AUDITE", "DG", "RAI"], Role.RAI),
        (["DG", "AUDITEUR"], Role.AUDITEUR),
        (["AUDITE", "DG"], Role.DG),
        (["AUDITE"], Role.AUDITE),
        ([], Role.AUDITE),
        (["offline_access", "uma_authorization", "default-roles-onea"], Role.AUDITE),
        (["offline_access", "AUDITEUR", "default-roles-onea"], Role.AUDITEUR),
        (["admin"], Role.AUDITE),  # names are case-sensitive: only exact realm roles count
        ("RAI", Role.RAI),  # a lone string is tolerated
        ("offline_access", Role.AUDITE),
        (None, Role.AUDITE),
        ([None, 3, {"a": 1}, "DG"], Role.DG),
        (42, Role.AUDITE),
    ],
)
def test_role_mapping(backend: OneaOIDCBackend, roles: Any, expected: Role) -> None:
    assert backend.get_role_from_claims({"roles": roles}) == expected


def test_default_role_is_audite_when_claim_missing(backend: OneaOIDCBackend) -> None:
    assert backend.get_role_from_claims({}) == Role.AUDITE


# --- user sync ------------------------------------------------------------------


@pytest.mark.django_db
def test_create_user_syncs_profile(backend: OneaOIDCBackend) -> None:
    user = backend.create_user(claims())
    user.refresh_from_db()
    assert user.keycloak_id == uuid.UUID(SUB)
    assert user.email == "Rai@onea.bf"
    assert user.first_name == "Salif"
    assert user.last_name == "Sawadogo"
    assert user.username == "rai"
    assert user.direction_code == "DAI"
    assert user.fonction == "Responsable audit interne"
    assert user.role == Role.RAI
    assert user.is_active
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_user_username_falls_back_to_email_local_part(backend: OneaOIDCBackend) -> None:
    user = backend.create_user(claims(preferred_username=None, email="awa.k@onea.bf"))
    assert user.username == "awa.k"


@pytest.mark.django_db
def test_create_user_username_collision_gets_suffix(backend: OneaOIDCBackend) -> None:
    make_user(Role.AUDITE, username="rai", email="other@onea.bf")
    user = backend.create_user(claims())
    assert user.username != "rai"
    assert user.username.startswith("rai")


@pytest.mark.django_db
def test_non_uuid_sub_leaves_keycloak_id_null(backend: OneaOIDCBackend) -> None:
    user = backend.create_user(claims(sub="not-a-uuid"))
    assert user.keycloak_id is None
    assert user.role == Role.RAI


@pytest.mark.django_db
def test_update_syncs_profile_and_role(backend: OneaOIDCBackend) -> None:
    existing = make_user(Role.ADMIN, direction_code="DG", fonction="x", email="rai@onea.bf")
    updated = backend.update_user(
        existing, claims(roles=["AUDITEUR"], direction="DEX", fonction="Auditeur", given_name="A")
    )
    existing.refresh_from_db()
    assert updated.pk == existing.pk
    assert existing.role == Role.AUDITEUR  # role removed in Keycloak takes effect
    assert existing.direction_code == "DEX"
    assert existing.fonction == "Auditeur"
    assert existing.first_name == "A"
    assert existing.keycloak_id == uuid.UUID(SUB)


@pytest.mark.django_db
def test_update_with_empty_roles_downgrades_to_audite(backend: OneaOIDCBackend) -> None:
    # Keycloak is the source of truth, even for a local ADMIN.
    existing = make_user(Role.ADMIN)
    backend.update_user(existing, claims(roles=[]))
    existing.refresh_from_db()
    assert existing.role == Role.AUDITE


# --- user lookup ----------------------------------------------------------------


@pytest.mark.django_db
def test_filter_matches_keycloak_id_first(backend: OneaOIDCBackend) -> None:
    by_id = make_user(keycloak_id=uuid.UUID(SUB), email="old@onea.bf")
    make_user(email="rai@onea.bf")
    assert list(backend.filter_users_by_claims(claims())) == [by_id]


@pytest.mark.django_db
def test_filter_falls_back_to_email_case_insensitive(backend: OneaOIDCBackend) -> None:
    local = make_user(email="RAI@ONEA.BF")
    assert list(backend.filter_users_by_claims(claims())) == [local]


@pytest.mark.django_db
def test_filter_never_matches_empty_email(backend: OneaOIDCBackend) -> None:
    make_user(email="")
    assert not backend.filter_users_by_claims(claims(email="")).exists()
    assert not backend.filter_users_by_claims(claims(email=None)).exists()
    no_email = claims()
    del no_email["email"]
    assert not backend.filter_users_by_claims(no_email).exists()


@pytest.mark.django_db
def test_email_does_not_hijack_account_bound_to_other_keycloak_id(
    backend: OneaOIDCBackend,
) -> None:
    make_user(email="rai@onea.bf", keycloak_id=uuid.uuid4())
    assert not backend.filter_users_by_claims(claims()).exists()


# --- DRF authentication class ---------------------------------------------------


def _bearer(client: APIClient, token: str = "tok") -> APIClient:  # noqa: S107
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
def test_valid_token_authenticates_and_creates_user(api_client: APIClient) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "RAI"
    assert body["direction_code"] == "DAI"
    assert User.objects.get(keycloak_id=uuid.UUID(SUB)).role == Role.RAI


@pytest.mark.django_db
def test_role_is_resynced_on_each_request(api_client: APIClient) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        assert _bearer(api_client).get("/api/v1/me/").json()["role"] == "RAI"
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims(roles=[])):
        assert _bearer(api_client).get("/api/v1/me/").json()["role"] == "AUDITE"


@pytest.mark.django_db
def test_role_cannot_be_forced_by_request(api_client: APIClient) -> None:
    api_client.credentials(HTTP_AUTHORIZATION="Bearer tok", HTTP_X_ROLE="ADMIN")
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims(roles=[])):
        r = api_client.get("/api/v1/me/?role=ADMIN")
    assert r.json()["role"] == "AUDITE"


@pytest.mark.django_db
def test_anonymous_401_french_body_and_bearer_challenge(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == 'Bearer realm="onea"'
    assert set(r.json()) == {"detail", "errors"}
    assert r.json()["errors"] == {}


def _http_error(status: int) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    resp.headers["www-authenticate"] = 'Bearer error="invalid_token", error_description="Token"'
    return requests.HTTPError(response=resp)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error",
    [
        SuspiciousOperation("bad"),
        _http_error(401),
        _http_error(500),
        _http_error(403),
        requests.ConnectionError("down"),
        requests.Timeout("slow"),
        requests.exceptions.JSONDecodeError("x", "", 0),
        ValueError("boom"),
        KeyError("kid"),
        RuntimeError("anything else"),
    ],
)
def test_invalid_token_never_500(api_client: APIClient, error: Exception) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", side_effect=error):
        r = _bearer(api_client, "expired").get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED
    assert r.headers["WWW-Authenticate"] == 'Bearer realm="onea"'


@pytest.mark.django_db
def test_userinfo_http_401_from_keycloak(api_client: APIClient) -> None:
    resp = requests.Response()
    resp.status_code = 401
    with mock.patch("mozilla_django_oidc.auth.requests.get", return_value=resp):
        r = _bearer(api_client, "foreign-realm").get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


@pytest.mark.django_db
@pytest.mark.parametrize("header", ["Bearer", "Bearer a b", "Bearer "])
def test_malformed_bearer_header_401(api_client: APIClient, header: str) -> None:
    api_client.credentials(HTTP_AUTHORIZATION=header)
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


@pytest.mark.django_db
def test_claims_without_sub_rejected(api_client: APIClient) -> None:
    bad = claims()
    del bad["sub"]
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=bad):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


@pytest.mark.django_db
def test_session_auth_still_works(api_client: APIClient, user: User) -> None:
    api_client.force_login(user)
    assert api_client.get("/api/v1/me/").status_code == 200
