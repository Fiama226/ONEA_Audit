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
