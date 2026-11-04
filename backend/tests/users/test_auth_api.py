"""API authentication: the in-app session only (CSRF on writes), no bearer tokens."""

from typing import Any
from unittest import mock

import pytest
from django.http import HttpResponse
from django.test import Client
from drf_spectacular.settings import spectacular_settings
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.test import APIClient

from apps.core.middleware import PasDeCacheApiMiddleware
from apps.users.models import Role, User

from ..connexion import connecter
from ..documents.api_fixtures import depot
from ..factories import make_user

TEMPLATES = "/api/v1/templates/"


def _connecter(client: Client, user: User) -> None:
    """Open a real API session (POST /auth/login/); force_login sessions are not API ones."""
    r = client.post(
        "/api/v1/auth/login/",
        {"identifiant": user.username, "mot_de_passe": "pass-test-12345"},
        content_type="application/json",
    )
    assert r.status_code == 200


@pytest.fixture
def session_client(admin: User) -> Client:
    """Plain Django client holding a valid ADMIN session cookie (CSRF not enforced)."""
    admin.is_staff = True  # the Django admin / IsAdminUser need staff, not the ADMIN role
    admin.is_superuser = True
    admin.save()
    client = Client()
    _connecter(client, admin)
    return client


def test_session_cookie_authenticates_api_read(session_client: Client) -> None:
    assert session_client.get("/api/v1/me/").status_code == 200


def test_anonymous_cannot_upload_template_and_body_is_not_parsed(db: None) -> None:
    with mock.patch.object(MultiPartParser, "parse") as parse:
        r = Client().post(TEMPLATES, depot())
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}
    parse.assert_not_called()


def test_session_write_without_csrf_token_is_refused(admin: User) -> None:
    client = APIClient()
    _connecter(client, admin)
    client.handler.enforce_csrf_checks = True
    # Django's CSRF check reads request.POST (form token) before the header, so the body of
    # an authenticated session is parsed before the refusal; anonymous bodies never are.
    r = client.post(TEMPLATES, depot(), format="multipart")
    assert r.status_code == 403
    assert r.json()["detail"] == "Jeton CSRF absent ou invalide : rechargez la page."


def test_non_admin_session_cannot_upload_template_and_body_is_not_parsed(
    api_client: APIClient, db: None
) -> None:
    connecter(api_client, make_user(Role.AUDITEUR))
    with mock.patch.object(MultiPartParser, "parse") as parse:
        r = api_client.post(TEMPLATES, depot(), format="multipart")
    assert r.status_code == 403
    parse.assert_not_called()


def test_missing_session_is_401_in_project_format(api_client: APIClient, db: None) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}
    assert r["WWW-Authenticate"] == "Session"


def test_bearer_header_is_ignored(api_client: APIClient, db: None) -> None:
    """No token authentication any more: an Authorization header is just ignored."""
    r = api_client.get("/api/v1/me/", HTTP_AUTHORIZATION="Bearer a.b.c")
    assert r.status_code == 401
    assert r["WWW-Authenticate"] == "Session"


def test_django_admin_session_still_works_for_admin(session_client: Client) -> None:
    assert session_client.get("/admin/").status_code == 200


# --- API documentation: ADMIN session, nobody else ---------------------------------


@pytest.fixture
def docs_restricted(monkeypatch: pytest.MonkeyPatch) -> None:
    # production value of SERVE_PERMISSIONS (drf-spectacular has no settings reload hook)
    monkeypatch.setattr(spectacular_settings, "SERVE_PERMISSIONS", [IsAdminUser])


@pytest.mark.usefixtures("docs_restricted")
def test_docs_admin_session_is_200(session_client: Client) -> None:
    assert session_client.get("/api/docs/").status_code == 200
    assert session_client.get("/api/schema/").status_code == 200


@pytest.mark.usefixtures("docs_restricted")
def test_docs_non_admin_session_is_403(api_client: APIClient, db: None) -> None:
    connecter(api_client, make_user(Role.AUDITEUR))
    assert api_client.get("/api/docs/").status_code == 403


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
