from typing import Any

import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.users.models import Role, User
from tests.testapp.models import Exemple

from ..factories import make_user

URL = "/api/v1/audit-log/"


@pytest.fixture
def rai_client(api_client: APIClient, rai: User) -> APIClient:
    api_client.force_authenticate(user=rai)
    return api_client


def _raw_entry(**kwargs: Any) -> LogEntry:
    defaults: dict[str, Any] = {
        "content_type": ContentType.objects.get_for_model(User),
        "object_pk": "1",
        "object_repr": "x",
        "action": LogEntry.Action.UPDATE,
        "changes": {},
    }
    return LogEntry.objects.create(**{**defaults, **kwargs})


def test_m2m_changes_are_passed_through(rai_client: APIClient, db: None) -> None:
    m2m = {"type": "m2m", "operation": "add", "objects": ["g1", "g2"]}
    _raw_entry(changes={"groups": m2m, "fonction": ["a", "b"]})
    changes = rai_client.get(URL).json()["results"][0]["changes"]
    assert changes == {"groups": m2m, "fonction": ["a", "b"]}


def test_unexpected_change_shapes_are_never_dropped(
    rai_client: APIClient, db: None, caplog: pytest.LogCaptureFixture
) -> None:
    _raw_entry(object_pk="2", changes={"weird": "scalar"})
    _raw_entry(object_pk="3", changes=["not", "a", "dict"])
    with caplog.at_level("WARNING"):
        results = rai_client.get(URL).json()["results"]
    by_pk = {r["object_id"]: r["changes"] for r in results}
    assert by_pk["2"] == {"weird": {"raw": "scalar"}}
    assert by_pk["3"] == {"raw": ["not", "a", "dict"]}
    assert "unexpected" in caplog.text.lower()


def test_unknown_action_code_does_not_crash(rai_client: APIClient, db: None) -> None:
    _raw_entry(action=9)
    assert rai_client.get(URL).json()["results"][0]["action"] == "unknown"


def test_hard_deleted_registered_model_records_before_values(
    rai_client: APIClient, db: None
) -> None:
    obj = Exemple.objects.create(nom="avant")
    obj.hard_delete()
    results = rai_client.get(URL, {"action": "delete", "model": "testapp.exemple"}).json()[
        "results"
    ]
    assert len(results) == 1
    changes = results[0]["changes"]
    assert changes["nom"] == ["avant", "None"]
    assert all(value[1] == "None" for value in changes.values())


def test_soft_deleted_model_is_an_update(rai_client: APIClient, rai: User) -> None:
    obj = Exemple.objects.create(nom="x")
    obj.soft_delete(rai)
    results = rai_client.get(URL, {"model": "testapp.exemple", "action": "update"}).json()[
        "results"
    ]
    assert "deleted_at" in results[0]["changes"]


def test_deleted_user_entry_never_exposes_password(rai_client: APIClient, db: None) -> None:
    victim = make_user(Role.AUDITE)
    victim.set_password("s3cret-pass-xyz")
    victim.save()
    pwd_hash = User.objects.get(pk=victim.pk).password
    victim.delete()
    results = rai_client.get(URL, {"action": "delete", "model": "users.user"}).json()["results"]
    assert len(results) == 1
    assert "password" not in results[0]["changes"]
    assert "last_login" not in results[0]["changes"]
    assert pwd_hash not in str(results)


def test_date_out_of_range_gives_400(rai_client: APIClient, db: None) -> None:
    response = rai_client.get(URL, {"date_to": "9999-12-31"})
    assert response.status_code == 400
    assert set(response.json()) == {"detail", "errors"}
    assert rai_client.get(URL, {"date_from": "0001-01-01"}).status_code in (200, 400)


@pytest.mark.parametrize("value", ["20260310", "10/03/2026", "03/10/2026", "2026-3-1x"])
def test_dates_accept_iso_only(rai_client: APIClient, db: None, value: str) -> None:
    assert rai_client.get(URL, {"date_from": value}).status_code == 400
    assert rai_client.get(URL, {"date_to": value}).status_code == 400


@pytest.mark.parametrize("value", ["1.5", "abc", "99999999999999999999", "-1"])
def test_actor_must_be_an_integer(rai_client: APIClient, db: None, value: str) -> None:
    assert rai_client.get(URL, {"actor": value}).status_code == 400


def test_object_id_normalises_uuids_only(rai_client: APIClient, db: None) -> None:
    obj = Exemple.objects.create(nom="u")
    found = rai_client.get(URL, {"object_id": str(obj.pk).upper()}).json()["results"]
    assert found
    _raw_entry(object_pk="ABC")
    assert rai_client.get(URL, {"object_id": "ABC"}).json()["results"]
    assert not rai_client.get(URL, {"object_id": "abc"}).json()["results"]
