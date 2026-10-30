import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from auditlog.models import LogEntry
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.gardes_sql import maintenance
from apps.users.models import Role, User

from ..factories import make_user

URL = "/api/v1/audit-log/"
OUAGA = ZoneInfo("Africa/Ouagadougou")


def _login(client: APIClient, user: User) -> APIClient:
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def rai_client(api_client: APIClient, rai: User) -> APIClient:
    return _login(api_client, rai)


@pytest.fixture
def modified_user(db: None) -> User:
    target = make_user(Role.AUDITE)
    target.fonction = "Chef de service"
    target.save()
    return target


def test_rai_lists_entries_with_changes(rai_client: APIClient, modified_user: User) -> None:
    response = rai_client.get(URL, {"action": "update"})
    assert response.status_code == 200
    item = response.json()["results"][0]
    assert set(item) == {
        "id",
        "timestamp",
        "actor",
        "action",
        "model",
        "object_id",
        "object_repr",
        "changes",
    }
    assert item["action"] == "update"
    assert item["model"] == "users.user"
    assert item["object_id"] == str(modified_user.pk)
    assert item["changes"]["fonction"] == ["Auditeur interne", "Chef de service"]


def test_actor_is_serialised(rai_client: APIClient, rai: User, modified_user: User) -> None:
    with maintenance():
        LogEntry.objects.filter(action=LogEntry.Action.UPDATE).update(actor=rai)
    results = rai_client.get(URL).json()["results"]
    actors = [r["actor"] for r in results]
    assert {"id": rai.pk, "username": rai.username} in actors
    assert None in actors


def test_create_entry_has_action_create(rai_client: APIClient, modified_user: User) -> None:
    actions = {r["action"] for r in rai_client.get(URL).json()["results"]}
    assert {"create", "update"} <= actions


def test_delete_entry_is_handled(rai_client: APIClient, modified_user: User) -> None:
    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(User),
        object_pk="999",
        object_repr="gone",
        action=LogEntry.Action.DELETE,
        changes={},
    )
    results = rai_client.get(URL, {"action": "delete"}).json()["results"]
    assert len(results) == 1
    assert results[0]["action"] == "delete"
    assert results[0]["object_id"] == "999"
    assert results[0]["changes"] == {}


def test_admin_allowed(api_client: APIClient, admin: User) -> None:
    assert _login(api_client, admin).get(URL).status_code == 200


@pytest.mark.parametrize("fixture_name", ["user", "audite", "dg"])
def test_other_roles_forbidden(
    api_client: APIClient, request: pytest.FixtureRequest, fixture_name: str
) -> None:
    who = request.getfixturevalue(fixture_name)
    response = _login(api_client, who).get(URL)
    assert response.status_code == 403
    assert set(response.json()) == {"detail", "errors"}


def test_anonymous_unauthorized(api_client: APIClient, db: None) -> None:
    assert api_client.get(URL).status_code == 401


def test_filter_by_model(rai_client: APIClient, modified_user: User) -> None:
    group = ContentType.objects.get_for_model(Group)
    LogEntry.objects.create(
        content_type=group,
        object_pk="1",
        object_repr="g",
        action=LogEntry.Action.CREATE,
        changes={},
    )
    users = rai_client.get(URL, {"model": "users.user"}).json()["results"]
    assert users
    assert {r["model"] for r in users} == {"users.user"}
    others = rai_client.get(URL, {"model": "auth.group"}).json()["results"]
    assert {r["model"] for r in others} == {"auth.group"}


def test_filter_by_action(rai_client: APIClient, modified_user: User) -> None:
    results = rai_client.get(URL, {"action": "create"}).json()["results"]
    assert results
    assert {r["action"] for r in results} == {"create"}


def test_filter_by_object_id_and_actor(
    rai_client: APIClient, modified_user: User, rai: User
) -> None:
    results = rai_client.get(URL, {"object_id": str(modified_user.pk)}).json()["results"]
    assert results
    assert {r["object_id"] for r in results} == {str(modified_user.pk)}
    with maintenance():
        LogEntry.objects.filter(object_pk=str(modified_user.pk)).update(actor=rai)
    by_actor = rai_client.get(URL, {"actor": rai.pk}).json()["results"]
    assert by_actor
    assert all(r["actor"]["id"] == rai.pk for r in by_actor)


def test_date_to_includes_whole_day(rai_client: APIClient, modified_user: User) -> None:
    with maintenance():
        LogEntry.objects.all().update(timestamp=dt.datetime(2026, 3, 1, 12, 0, tzinfo=OUAGA))
    entries = list(LogEntry.objects.order_by("pk"))
    assert len(entries) >= 3
    late, next_day, early = entries[0], entries[1], entries[2]
    with maintenance():
        LogEntry.objects.filter(pk=late.pk).update(
            timestamp=dt.datetime(2026, 3, 10, 23, 30, tzinfo=OUAGA)
        )
    with maintenance():
        LogEntry.objects.filter(pk=next_day.pk).update(
            timestamp=dt.datetime(2026, 3, 11, 0, 5, tzinfo=OUAGA)
        )
    with maintenance():
        LogEntry.objects.filter(pk=early.pk).update(
            timestamp=dt.datetime(2026, 3, 9, 23, 55, tzinfo=OUAGA)
        )
    ids = {
        r["id"]
        for r in rai_client.get(URL, {"date_from": "2026-03-10", "date_to": "2026-03-10"}).json()[
            "results"
        ]
    }
    assert ids == {late.pk}


@pytest.mark.parametrize(
    "params",
    [
        {"model": "nope"},
        {"model": "users.ghost"},
        {"date_from": "not-a-date"},
        {"date_to": "2026-13-45"},
        {"action": "explode"},
        {"actor": "abc"},
    ],
)
def test_bad_filter_gives_400(
    rai_client: APIClient, modified_user: User, params: dict[str, str]
) -> None:
    response = rai_client.get(URL, params)
    assert response.status_code == 400
    body = response.json()
    assert set(body) == {"detail", "errors"}
    assert body["errors"]


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_not_allowed(rai_client: APIClient, modified_user: User, method: str) -> None:
    entry = LogEntry.objects.first()
    assert entry is not None
    before = LogEntry.objects.count()
    for url in (URL, f"{URL}{entry.pk}/"):
        assert getattr(rai_client, method)(url, {}, format="json").status_code == 405
    assert LogEntry.objects.count() == before


def test_page_uses_at_most_three_queries(rai_client: APIClient, rai: User) -> None:
    for _ in range(5):
        target = make_user(Role.AUDITE)
        with maintenance():
            LogEntry.objects.filter(object_pk=str(target.pk)).update(actor=rai)
    with CaptureQueriesContext(connection) as ctx:
        response = rai_client.get(URL)
    assert response.status_code == 200
    assert len(response.json()["results"]) >= 5
    assert len(ctx.captured_queries) <= 3


def test_password_never_exposed(rai_client: APIClient, modified_user: User) -> None:
    modified_user.set_password("another-secret-123")
    modified_user.save()
    modified_user.refresh_from_db()
    body: Any = rai_client.get(URL).json()
    text = str(body)
    assert modified_user.password not in text
    assert "pbkdf2" not in text
    assert "md5$" not in text
    for item in body["results"]:
        assert "password" not in (item["changes"] or {})
