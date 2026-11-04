"""Low-severity hardening of the in-app authentication (security review AUTH-07..AUTH-11).

- AUTH-08: a request marked as background polling (``X-Onea-Arriere-Plan: 1``) does not
  keep a session alive past the 30 min idle limit;
- AUTH-09: the Django admin cannot change a password behind the counted re-check;
- AUTH-11: new usernames are ASCII only (no look-alike accounts);
- locks: the account rows are locked ``FOR NO KEY UPDATE`` (no clash with the ``FOR KEY
  SHARE`` of a concurrent insert referencing the account).
AUTH-07 (production email backend) is tested with the production settings
(``tests/test_prod_settings.py``).
"""

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.users import auth_services
from apps.users.models import ObjetOtp, Role, User
from apps.users.provisioning import CSV_IDENTIFIANT_INVALIDE, importer_csv

from ..factories import make_user

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
SESSION = "/api/v1/auth/session/"
MDP = "Mot-de-passe-solide-2026"
ARRIERE_PLAN = {"X-Onea-Arriere-Plan": "1"}


@pytest.fixture
def agent() -> User:
    return make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)


def _connecte() -> APIClient:
    client = APIClient()
    r = client.post(LOGIN, {"identifiant": "awa", "mot_de_passe": MDP}, format="json")
    assert r.status_code == 200
    return client


def _vieillir(client: APIClient, minutes: int) -> None:
    session = client.session
    session["onea_activite_le"] = session["onea_activite_le"] - minutes * 60
    session.save()


# --- AUTH-08 -------------------------------------------------------------------------------


def test_background_polling_does_not_keep_the_session_alive(agent: User) -> None:
    client = _connecte()
    _vieillir(client, 20)
    # The notification counter polled by an open tab: answered, but not an activity.
    assert client.get(SESSION, headers=ARRIERE_PLAN).status_code == 200
    _vieillir(client, 11)  # 31 min since the last real activity
    assert client.get(SESSION, headers=ARRIERE_PLAN).status_code == 401
    assert client.get(SESSION).status_code == 401


def test_a_real_request_still_counts_as_activity(agent: User) -> None:
    client = _connecte()
    _vieillir(client, 20)
    assert client.get(SESSION).status_code == 200
    _vieillir(client, 11)
    assert client.get(SESSION, headers=ARRIERE_PLAN).status_code == 200


# --- AUTH-09 -------------------------------------------------------------------------------


def test_admin_password_change_page_is_closed(agent: User) -> None:
    agent.is_staff = True
    agent.is_superuser = True
    agent.save()
    client = Client()
    r = client.post("/admin/login/?next=/admin/", {"username": "awa", "password": MDP})
    assert r.status_code == 302
    assert client.get("/admin/").status_code == 200
    for methode in ("get", "post"):
        corps: dict[str, Any] = (
            {
                "old_password": "faux",
                "new_password1": "Encore-une-phrase-88",
                "new_password2": "Encore-une-phrase-88",
            }
            if methode == "post"
            else {}
        )
        r = getattr(client, methode)("/admin/password_change/", corps)
        assert r.status_code == 404, methode
    agent.refresh_from_db()
    assert agent.check_password(MDP)


# --- AUTH-11 -------------------------------------------------------------------------------


@pytest.mark.parametrize("identifiant", ["dɡ", "ｄｇ", "aïcha", "аdmin"])
def test_new_usernames_are_ascii_only(admin: User, identifiant: str) -> None:
    client = APIClient()
    client.force_authenticate(admin)
    r = client.post(
        "/api/v1/user-accounts/",
        {"username": identifiant, "role": "AUDITE", "envoyer_courriel": False},
        format="json",
    )
    assert r.status_code == 400 and "username" in r.json()["errors"]
    rapport = importer_csv(
        f"identifiant;role\n{identifiant};AUDITE\n".encode(),
        by=admin,
        dry_run=True,
        envoyer_courriel=False,
    )
    assert [ligne.motif for ligne in rapport.ignores] == [CSV_IDENTIFIANT_INVALIDE]
    assert not User.objects.filter(username=identifiant).exists()


def test_ascii_usernames_with_dots_and_dashes_are_fine(admin: User) -> None:
    client = APIClient()
    client.force_authenticate(admin)
    corps = {"username": "awa.ouedraogo-2_b", "role": "AUDITE", "envoyer_courriel": False}
    assert client.post("/api/v1/user-accounts/", corps, format="json").status_code == 201


# --- locks -----------------------------------------------------------------------------------


def _verrous_compte(capture: CaptureQueriesContext) -> list[str]:
    return [
        q["sql"]
        for q in capture.captured_queries
        if '"users_user"' in q["sql"] and "FOR " in q["sql"] and "UPDATE" in q["sql"]
    ]


def test_account_rows_are_locked_for_no_key_update(agent: User) -> None:
    with CaptureQueriesContext(connection) as capture:
        auth_services.authentifier("awa", MDP)
        auth_services.authentifier("awa", "faux")
        auth_services.emettre_otp(agent, ObjetOtp.LOGIN)
        code = auth_services.emettre_otp(agent, ObjetOtp.RESET)
        auth_services.reinitialiser_mot_de_passe("awa", code, "Nouvelle-phrase-secrete-77")
        auth_services.changer_mot_de_passe(
            agent, "Nouvelle-phrase-secrete-77", "Encore-une-autre-phrase-88"
        )
        auth_services.quota_codes_reinitialisation(agent.pk)
    verrous = _verrous_compte(capture)
    assert len(verrous) >= 6
    assert all("FOR NO KEY UPDATE" in sql for sql in verrous), verrous


def test_admin_bootstrap_locks_for_no_key_update() -> None:
    make_user(Role.ADMIN, username="admin", email="admin@onea.bf", password=MDP)
    with CaptureQueriesContext(connection) as capture:
        call_command("creer_administrateur", identifiant="admin", stdout=StringIO())
    verrous = _verrous_compte(capture)
    assert verrous and all("FOR NO KEY UPDATE" in sql for sql in verrous), verrous
