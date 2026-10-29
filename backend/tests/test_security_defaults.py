from typing import Any

import pytest
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient


@api_view(["GET"])
def probe(request: Request) -> Response:
    # No permission_classes: relies on the project-wide default.
    return Response({"ok": True})


urlpatterns = [path("probe/", probe)]


@pytest.mark.urls("tests.test_security_defaults")
def test_view_without_explicit_permissions_rejects_anonymous(api_client: APIClient) -> None:
    assert api_client.get("/probe/").status_code in (401, 403)


def test_schema_is_anonymous_under_test_settings(api_client: APIClient) -> None:
    assert api_client.get("/api/schema/").status_code == 200


def test_health_stays_anonymous(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/health/").status_code == 200


def test_default_cache_is_usable() -> None:
    from django.core.cache import caches

    cache = caches["default"]
    cache.set("t5-probe", {"a": 1}, 5)
    assert cache.get("t5-probe") == {"a": 1}


def test_api_default_authentication_is_bearer_only() -> None:
    from django.conf import settings

    auth = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    assert auth == ["apps.users.authentication.OIDCBearerAuthentication"]


def test_session_cookie_policy_defaults() -> None:
    from django.conf import settings

    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_COOKIE_AGE == 8 * 3600
    assert settings.SESSION_COOKIE_HTTPONLY is True


def test_logging_is_configured() -> None:
    from django.conf import settings

    logging_conf: Any = settings.LOGGING
    assert logging_conf["root"]["level"] == "INFO"
    assert "console" in logging_conf["root"]["handlers"]
    assert logging_conf["loggers"]["django.request"]["level"] == "ERROR"
