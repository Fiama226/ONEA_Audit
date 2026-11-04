import base64
import json
import logging
import uuid
from typing import Any
from unittest import mock

import pytest
import requests
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.users.models import Role, User
from apps.users.oidc import OneaOIDCBackend

from ..factories import make_user

SESSION_EXPIRED = {"detail": "Session expirée ou jeton invalide.", "errors": {}}
UNAVAILABLE = {
    "detail": "Service d'authentification indisponible. Réessayez plus tard.",
    "errors": {},
}
SUB = "5b1c3a52-7c0e-4a3e-9d0b-1f6f6d0f2a11"


def claims(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sub": SUB,
        "email": "Rai@onea.bf",
        "email_verified": True,
        "preferred_username": "rai",
        "given_name": "Salif",
        "family_name": "Sawadogo",
        "roles": ["RAI"],
        "direction": "DAI",
        "fonction": "Responsable audit interne",
    }
    base.update(kwargs)
    return base


def make_token(**payload: Any) -> str:
    """Unsigned JWT-shaped token (signature is checked by Keycloak via userinfo)."""
    body = {"azp": "onea-frontend", **payload}
    body = {k: v for k, v in body.items() if v is not None}

    def enc(obj: Any) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    return f"{enc({'alg': 'RS256'})}.{enc(body)}.sig"


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
def test_create_user_race_on_keycloak_id_returns_winner(backend: OneaOIDCBackend) -> None:
    # Another request created the same identity between our lookup and our insert:
    # the unique constraint fires, we roll back and return the winner (no 500).
    winner = make_user(keycloak_id=uuid.UUID(SUB), username="winner", email="w@onea.bf")
    user = backend.create_user(claims())
    assert user.pk == winner.pk
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_create_user_race_on_username_retries_with_suffix(backend: OneaOIDCBackend) -> None:
    make_user(username="rai", email="other@onea.bf")
    real = backend._insert_user
    calls: list[str] = []

    def flaky(claims_: Any, username: str) -> User:
        calls.append(username)
        if len(calls) == 1:
            raise IntegrityError("duplicate key (username)")
        return real(claims_, username)

    with mock.patch.object(backend, "_insert_user", side_effect=flaky):
        user = backend.create_user(claims())
    assert len(calls) == 2
    assert calls[0] != calls[1]
    assert user.keycloak_id == uuid.UUID(SUB)


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
def test_update_with_empty_roles_downgrades_to_audite(
    backend: OneaOIDCBackend, caplog: pytest.LogCaptureFixture
) -> None:
    # Keycloak is the source of truth, even for a local ADMIN.
    existing = make_user(Role.ADMIN)
    with caplog.at_level(logging.WARNING, logger="apps.users.oidc"):
        backend.update_user(existing, claims(roles=[]))
    existing.refresh_from_db()
    assert existing.role == Role.AUDITE
    assert any("downgraded" in r.getMessage() for r in caplog.records)
    assert all(existing.email not in r.getMessage() for r in caplog.records)


@pytest.mark.django_db
def test_update_with_missing_roles_claim_is_treated_as_empty(
    backend: OneaOIDCBackend, caplog: pytest.LogCaptureFixture
) -> None:
    existing = make_user(Role.RAI)
    no_roles = claims()
    del no_roles["roles"]
    with caplog.at_level(logging.WARNING, logger="apps.users.oidc"):
        backend.update_user(existing, no_roles)
    existing.refresh_from_db()
    assert existing.role == Role.AUDITE
    assert any("downgraded" in r.getMessage() for r in caplog.records)


@pytest.mark.django_db
def test_update_does_not_overwrite_concurrent_admin_changes(backend: OneaOIDCBackend) -> None:
    stale = make_user(Role.AUDITEUR, email="rai@onea.bf")
    User.objects.filter(pk=stale.pk).update(is_active=False, matricule="M-42")
    backend.update_user(stale, claims(roles=["AUDITEUR"]))
    fresh = User.objects.get(pk=stale.pk)
    assert fresh.is_active is False
    assert fresh.matricule == "M-42"
    assert fresh.keycloak_id == uuid.UUID(SUB)


@pytest.mark.django_db
def test_update_without_changes_does_not_write(backend: OneaOIDCBackend) -> None:
    user = backend.create_user(claims())
    with mock.patch.object(User, "save") as save:
        backend.update_user(user, claims())
    save.assert_not_called()


@pytest.mark.django_db
def test_update_never_touches_privileged_flags(backend: OneaOIDCBackend) -> None:
    user = make_user(Role.AUDITEUR, email="rai@onea.bf", is_staff=True)
    backend.update_user(user, claims(is_staff=False, is_superuser=True, is_active=False))
    user.refresh_from_db()
    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.is_active is True


# --- user lookup ----------------------------------------------------------------


@pytest.mark.django_db
def test_filter_matches_keycloak_id_first(backend: OneaOIDCBackend) -> None:
    by_id = make_user(keycloak_id=uuid.UUID(SUB), email="old@onea.bf")
    make_user(email="rai@onea.bf")
    assert list(backend.filter_users_by_claims(claims())) == [by_id]


@pytest.mark.django_db
def test_filter_falls_back_to_verified_email_case_insensitive(backend: OneaOIDCBackend) -> None:
    local = make_user(email="RAI@ONEA.BF")
    assert list(backend.filter_users_by_claims(claims())) == [local]


@pytest.mark.django_db
@pytest.mark.parametrize("verified", [False, None, "true", 1])
def test_unverified_email_does_not_bind(backend: OneaOIDCBackend, verified: Any) -> None:
    make_user(email="rai@onea.bf")
    assert not backend.filter_users_by_claims(claims(email_verified=verified)).exists()


@pytest.mark.django_db
def test_missing_email_verified_does_not_bind(backend: OneaOIDCBackend) -> None:
    make_user(email="rai@onea.bf")
    c = claims()
    del c["email_verified"]
    assert not backend.filter_users_by_claims(c).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_staff_and_superuser_never_bound_by_email(backend: OneaOIDCBackend, flag: str) -> None:
    make_user(Role.ADMIN, email="rai@onea.bf", **{flag: True})
    assert not backend.filter_users_by_claims(claims()).exists()


@pytest.mark.django_db
def test_multiple_email_matches_do_not_bind(
    backend: OneaOIDCBackend, caplog: pytest.LogCaptureFixture
) -> None:
    make_user(email="rai@onea.bf")
    make_user(email="RAI@onea.bf")
    with caplog.at_level(logging.WARNING, logger="apps.users.oidc"):
        assert not backend.filter_users_by_claims(claims()).exists()
    assert any(r.levelno == logging.WARNING for r in caplog.records)


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


@pytest.mark.django_db
def test_verified_email_binds_end_to_end(backend: OneaOIDCBackend) -> None:
    local = make_user(Role.AUDITE, email="rai@onea.bf")
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        user = backend.get_or_create_user(make_token(), None, None)
    assert user is not None
    assert user.pk == local.pk
    local.refresh_from_db()
    assert local.keycloak_id == uuid.UUID(SUB)
    assert local.role == Role.RAI


@pytest.mark.django_db
def test_unverified_email_creates_separate_account_end_to_end(backend: OneaOIDCBackend) -> None:
    local = make_user(Role.ADMIN, email="rai@onea.bf")
    with mock.patch.object(
        OneaOIDCBackend, "get_userinfo", return_value=claims(email_verified=False, roles=[])
    ):
        user = backend.get_or_create_user(make_token(), None, None)
    assert user is not None
    assert user.pk != local.pk
    local.refresh_from_db()
    assert local.keycloak_id is None
    assert local.role == Role.ADMIN


@pytest.mark.django_db
def test_multiple_users_refusal_is_logged_as_warning(
    backend: OneaOIDCBackend, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()),
        mock.patch.object(
            OneaOIDCBackend,
            "filter_users_by_claims",
            return_value=[make_user(), make_user()],
        ),
        caplog.at_level(logging.WARNING, logger="apps.users.oidc"),
        pytest.raises(SuspiciousOperation),
    ):
        backend.get_or_create_user(make_token(), None, None)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# --- claim verification ---------------------------------------------------------


@pytest.mark.parametrize("sub", ["not-a-uuid", "", None, 12, "123"])
def test_verify_claims_rejects_non_uuid_sub(backend: OneaOIDCBackend, sub: Any) -> None:
    assert backend.verify_claims(claims(sub=sub)) is False


def test_verify_claims_accepts_uuid_sub(backend: OneaOIDCBackend) -> None:
    assert backend.verify_claims(claims()) is True


# --- DRF authentication class ---------------------------------------------------


def _bearer(client: APIClient, token: str | None = None) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token or make_token()}")
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
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_token()}", HTTP_X_ROLE="ADMIN")
    no_roles = claims()
    del no_roles["roles"]
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=no_roles):
        r = api_client.get("/api/v1/me/?role=ADMIN")
    assert r.status_code == 200
    assert r.json()["role"] == "AUDITE"


@pytest.mark.django_db
def test_anonymous_401_french_body_and_session_challenge(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    # The first authentication class (session) gives the challenge since the in-app login.
    assert r.headers["WWW-Authenticate"] == "Session"
    body = r.json()
    assert body["errors"] == {}
    assert body["detail"] == "Informations d'authentification non fournies."


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
        _http_error(403),
        requests.exceptions.JSONDecodeError("x", "", 0),
        requests.exceptions.TooManyRedirects("loop"),
        ValueError("boom"),
        KeyError("kid"),
        RuntimeError("anything else"),
    ],
)
def test_invalid_token_never_500(api_client: APIClient, error: Exception) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", side_effect=error):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED
    assert r.headers["WWW-Authenticate"] == "Session"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error",
    [
        requests.ConnectionError("down"),
        requests.Timeout("slow"),
        requests.exceptions.SSLError("tls"),
        _http_error(500),
        _http_error(503),
    ],
)
def test_keycloak_outage_is_503_not_logout(api_client: APIClient, error: Exception) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", side_effect=error):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 503
    assert r.json() == UNAVAILABLE


@pytest.mark.django_db
def test_unexpected_error_is_logged_with_traceback(
    api_client: APIClient, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        mock.patch.object(OneaOIDCBackend, "get_userinfo", side_effect=RuntimeError("x")),
        caplog.at_level(logging.ERROR, logger="apps.users.authentication"),
    ):
        r = _bearer(api_client, make_token(jti="secret-jti")).get("/api/v1/me/")
    assert r.status_code == 401
    records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert records
    assert records[0].exc_info is not None
    assert "secret-jti" not in caplog.text


@pytest.mark.django_db
def test_userinfo_http_401_from_keycloak(api_client: APIClient) -> None:
    resp = requests.Response()
    resp.status_code = 401
    with mock.patch("mozilla_django_oidc.auth.requests.get", return_value=resp):
        r = _bearer(api_client).get("/api/v1/me/")
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
@pytest.mark.parametrize("sub", ["not-a-uuid", None])
def test_claims_with_bad_sub_rejected(api_client: APIClient, sub: Any) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims(sub=sub)):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_session_auth_authenticates_the_api(api_client: APIClient, user: User) -> None:
    api_client.force_login(user)
    assert api_client.get("/api/v1/me/").status_code == 200


# --- audience (azp) -------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("azp", ["onea-frontend", "onea-dev-cli"])
def test_allowed_azp_ok(api_client: APIClient, azp: str) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client, make_token(azp=azp)).get("/api/v1/me/")
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("azp", ["admin-cli", "account-console", "", 12])
def test_other_client_token_rejected(api_client: APIClient, azp: Any) -> None:
    # A token minted for another client of the realm may carry a `roles` claim
    # (e.g. ADMIN) that must never reach the role mapping.
    with mock.patch.object(
        OneaOIDCBackend, "get_userinfo", return_value=claims(roles=["ADMIN"])
    ) as userinfo:
        r = _bearer(api_client, make_token(azp=azp)).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED
    assert User.objects.count() == 0
    userinfo.assert_not_called()


@pytest.mark.django_db
def test_missing_azp_rejected(api_client: APIClient) -> None:
    body = {"sub": SUB}
    enc = base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b"=").decode()
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client, f"e30.{enc}.sig").get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "token", ["opaque", "a.b", "a.!!!.c", "a.bm90LWpzb24.c", "a.W10.c", "a.IjEi.c"]
)
def test_malformed_token_rejected(api_client: APIClient, token: str) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client, token).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


# --- is_active ------------------------------------------------------------------


@pytest.mark.django_db
def test_inactive_user_rejected(api_client: APIClient) -> None:
    make_user(Role.RAI, keycloak_id=uuid.UUID(SUB), is_active=False)
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 403
    assert r.json() == {"detail": "Compte désactivé.", "errors": {}}
