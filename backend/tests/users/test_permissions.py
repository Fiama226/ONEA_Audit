import pytest
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.permissions import IsAdmin, IsRAI, IsRAIOrAdmin, ReadOnlyForDG


@api_view(["GET"])
@permission_classes([IsRAI])
def rai_only(request: Request) -> Response:
    return Response({"ok": True})


@api_view(["GET", "POST"])
@permission_classes([ReadOnlyForDG])
def dg_readonly(request: Request) -> Response:
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_only(request: Request) -> Response:
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([IsRAIOrAdmin])
def rai_or_admin(request: Request) -> Response:
    return Response({"ok": True})


urlpatterns = [
    path("_test/rai-only/", rai_only),
    path("_test/dg/", dg_readonly),
    path("_test/admin-only/", admin_only),
    path("_test/rai-or-admin/", rai_or_admin),
]

pytestmark = pytest.mark.urls("tests.users.test_permissions")


def _as(client: APIClient, u: User) -> APIClient:
    client.force_authenticate(user=u)
    return client


def test_has_role_permission_denies_wrong_role(api_client: APIClient, user: User) -> None:
    assert _as(api_client, user).get("/_test/rai-only/").status_code == 403


def test_has_role_permission_allows_role(api_client: APIClient, rai: User) -> None:
    assert _as(api_client, rai).get("/_test/rai-only/").status_code == 200


def test_has_role_denies_anonymous(api_client: APIClient) -> None:
    assert api_client.get("/_test/rai-only/").status_code == 401


def test_admin_only(api_client: APIClient, admin: User, rai: User) -> None:
    assert _as(api_client, rai).get("/_test/admin-only/").status_code == 403
    assert _as(api_client, admin).get("/_test/admin-only/").status_code == 200


def test_rai_or_admin(api_client: APIClient, admin: User, rai: User, audite: User) -> None:
    assert _as(api_client, rai).get("/_test/rai-or-admin/").status_code == 200
    assert _as(api_client, admin).get("/_test/rai-or-admin/").status_code == 200
    assert _as(api_client, audite).get("/_test/rai-or-admin/").status_code == 403


def test_dg_is_read_only(api_client: APIClient, dg: User, user: User) -> None:
    assert _as(api_client, dg).get("/_test/dg/").status_code == 200
    assert _as(api_client, dg).post("/_test/dg/").status_code == 403
    assert _as(api_client, user).post("/_test/dg/").status_code == 200


def test_has_role_method(rai: User) -> None:
    assert rai.has_role("RAI", "ADMIN")
    assert not rai.has_role("DG")
