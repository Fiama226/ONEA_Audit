from unittest import mock

import pytest
from auditlog.models import LogEntry
from rest_framework.test import APIClient

from apps.users.models import Role
from apps.users.oidc import OneaOIDCBackend
from tests.testapp.models import Exemple
from tests.users.test_oidc import SUB, _bearer, claims

from ..factories import make_user


@pytest.mark.django_db
def test_bearer_request_logs_actor_and_remote_addr(api_client: APIClient) -> None:
    import uuid

    user = make_user(Role.RAI, keycloak_id=uuid.UUID(SUB))
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(api_client).post("/api/v1/_test/ecrire-exemple/", REMOTE_ADDR="10.1.2.3")
    assert r.status_code == 200
    entries = LogEntry.objects.get_for_model(Exemple)
    assert entries.count() == 2
    for entry in entries:
        assert entry.actor == user
        assert entry.remote_addr == "10.1.2.3"
