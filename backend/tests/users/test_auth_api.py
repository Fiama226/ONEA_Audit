"""API authentication is Keycloak bearer only; the Django session is reserved to /admin."""

from typing import Any
from unittest import mock

import pytest
import requests
from django.http import HttpResponse
from django.test import Client
from drf_spectacular.settings import spectacular_settings
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.test import APIClient

from apps.core.middleware import PasDeCacheApiMiddleware
from apps.users.models import User
from apps.users.oidc import OneaOIDCBackend

from ..documents.api_fixtures import depot
from .test_oidc import SESSION_EXPIRED, _bearer, claims, make_token

TEMPLATES = "/api/v1/templates/"


@pytest.fixture
def session_client(admin: User) -> Client:
    """Plain Django client holding a valid ADMIN session cookie (CSRF not enforced)."""
    admin.is_staff = True  # the Django admin / IsAdminUser need staff, not the ADMIN role
    admin.is_superuser = True
    admin.save()
    client = Client()
    client.force_login(admin)
    return client


def _userinfo_401() -> requests.HTTPError:
    return requests.HTTPError(response=mock.Mock(status_code=401))


def test_session_cookie_alone_does_not_authenticate_api_read(session_client: Client) -> None:
    r = session_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}


def test_session_cookie_without_bearer_cannot_upload_template(session_client: Client) -> None:
    with mock.patch.object(MultiPartParser, "parse") as parse:
        r = session_client.post(TEMPLATES, depot())
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}
    parse.assert_not_called()


def test_session_cookie_with_csrf_check_cannot_write(admin: User) -> None:
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin)
    with mock.patch.object(MultiPartParser, "parse") as parse:
        r = client.post(TEMPLATES, depot(), format="multipart")
    assert r.status_code == 401
    parse.assert_not_called()


def test_non_admin_token_cannot_upload_template_and_body_is_not_parsed(
    api_client: APIClient, db: None
) -> None:
    with (
        mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims(roles=["AUDITEUR"])),
        mock.patch.object(MultiPartParser, "parse") as parse,
    ):
        r = _bearer(api_client).post(TEMPLATES, depot(), format="multipart")
    assert r.status_code == 403
    parse.assert_not_called()


def test_missing_token_is_401_in_project_format(api_client: APIClient, db: None) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}
    assert r["WWW-Authenticate"].startswith("Bearer")


def test_expired_token_is_401_in_project_format(api_client: APIClient, db: None) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", side_effect=_userinfo_401()):
        r = _bearer(api_client).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


@pytest.mark.parametrize("azp", ["other-client", "admin-cli", None])
def test_wrong_audience_token_is_401(api_client: APIClient, db: None, azp: str | None) -> None:
    token = make_token(azp=azp) if azp else "a.b.c"
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client, token).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


def test_foreign_issuer_token_is_401(api_client: APIClient, db: None) -> None:
    """A token from another issuer is refused by Keycloak's userinfo (401)."""
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", side_effect=_userinfo_401()):
        r = _bearer(api_client, make_token(iss="https://evil.example/realms/x")).get("/api/v1/me/")
    assert r.status_code == 401
    assert r.json() == SESSION_EXPIRED


def test_valid_bearer_still_authenticates(api_client: APIClient, db: None) -> None:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        assert _bearer(api_client).get("/api/v1/me/").status_code == 200


def test_django_admin_session_still_works_for_admin(session_client: Client) -> None:
    assert session_client.get("/admin/").status_code == 200


# --- API documentation: ADMIN session or ADMIN bearer, nobody else ----------------


@pytest.fixture
def docs_restricted(monkeypatch: pytest.MonkeyPatch) -> None:
    # production value of SERVE_PERMISSIONS (drf-spectacular has no settings reload hook)
    monkeypatch.setattr(spectacular_settings, "SERVE_PERMISSIONS", [IsAdminUser])


@pytest.mark.usefixtures("docs_restricted")
def test_docs_admin_session_is_200(session_client: Client) -> None:
    assert session_client.get("/api/docs/").status_code == 200
    assert session_client.get("/api/schema/").status_code == 200


@pytest.mark.usefixtures("docs_restricted")
def test_docs_non_admin_token_is_403(api_client: APIClient, db: None) -> None:
    with mock.patch.object(
        OneaOIDCBackend, "get_userinfo", return_value=claims(roles=["AUDITEUR"])
    ):
        assert _bearer(api_client).get("/api/docs/").status_code == 403


@pytest.mark.usefixtures("docs_restricted")
def test_docs_anonymous_is_401(api_client: APIClient, db: None) -> None:
    assert api_client.get("/api/docs/").status_code == 401


# --- response caching ---------------------------------------------------------------


def test_api_responses_are_no_store_private(auth_client: APIClient) -> None:
    r = auth_client.get("/api/v1/me/")
    assert r.status_code == 200
    assert r["Cache-Control"] == "no-store, private"


def test_api_errors_are_no_store_private(api_client: APIClient, db: None) -> None:
    assert api_client.get("/api/v1/me/")["Cache-Control"] == "no-store, private"


def test_download_keeps_its_own_cache_control(rf: Any) -> None:
    own = HttpResponse(b"x", headers={"Cache-Control": "private, no-store"})
    out = PasDeCacheApiMiddleware(lambda _r: own)(rf.get("/api/v1/templates/1/file/"))
    assert out["Cache-Control"] == "private, no-store"


def test_non_api_paths_are_untouched(rf: Any) -> None:
    out = PasDeCacheApiMiddleware(lambda _r: HttpResponse("x"))(rf.get("/admin/"))
    assert "Cache-Control" not in out
