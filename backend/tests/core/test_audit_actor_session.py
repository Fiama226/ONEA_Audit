import pytest
from auditlog.models import LogEntry
from rest_framework.test import APIClient

from apps.users.models import Role
from tests.testapp.models import Exemple

from ..connexion import connecter
from ..factories import make_user


@pytest.mark.django_db
def test_session_request_logs_actor_and_remote_addr(api_client: APIClient) -> None:
    """An API write is logged with the user DRF authenticated (resolved lazily)."""
    user = make_user(Role.RAI)
    r = connecter(api_client, user).post("/api/v1/_test/ecrire-exemple/", REMOTE_ADDR="10.1.2.3")
    assert r.status_code == 200
    entries = LogEntry.objects.get_for_model(Exemple)
    assert entries.count() == 2
    for entry in entries:
        assert entry.actor == user
        assert entry.remote_addr == "10.1.2.3"
