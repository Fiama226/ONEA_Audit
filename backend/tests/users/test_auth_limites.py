"""Rate limits of the authentication endpoints (AUTH-04, AUTH-05, AUTH-06, AUTH-12).

- AUTH-05: CSRF is checked before any throttle counts the request (a cross-site page cannot
  burn the quota shared by a head office behind one NAT address); one bucket per endpoint;
  the change of password is limited per user, not per address.
- AUTH-04: per address, the wrong passwords and codes are capped across accounts, so that
  one address cannot keep many accounts locked; refusals stay uniform (429 + Retry-After).
- AUTH-12: an IPv6 address counts by its /64.
- AUTH-06: the Django admin login form goes through the same per-address limits.
"""

import logging
from typing import Any, cast

import pytest
from django.conf import settings
from django.test import Client, override_settings
from rest_framework.test import APIClient

from apps.users.auth_throttles import analyser_taux, cle_adresse
from apps.users.models import Role, User
from tests.connexion import connecter

from ..factories import make_user

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
LOGIN_OTP = "/api/v1/auth/login/otp/"
FORGOT = "/api/v1/auth/password/forgot/"
RESET = "/api/v1/auth/password/reset/"
CHANGE = "/api/v1/auth/password/change/"
OTP_OFF = "/api/v1/auth/otp/disable/"
CSRF = "/api/v1/auth/csrf/"
MDP = "Mot-de-passe-solide-2026"


def _taux(**taux: str) -> Any:
    actuels = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    return override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {**actuels, **taux},
        }
    )


def _login(client: APIClient, identifiant: str, mot_de_passe: str = MDP, **extra: Any) -> Any:
    return client.post(
        LOGIN, {"identifiant": identifiant, "mot_de_passe": mot_de_passe}, format="json", **extra
    )


@pytest.fixture
def agent() -> User:
    return make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)


# --- AUTH-05 ---------------------------------------------------------------------------------


def test_defaults_sized_for_a_head_office_nat() -> None:
    taux = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    assert taux["connexion"] == "60/min"
    assert taux["connexion_code"] == "30/min"
    assert taux["mot_de_passe_oublie_ip"] == "20/min"
    assert taux["reinitialisation"] == "20/min"
    assert taux["changement_mot_de_passe"] == "10/min"
    assert taux["echecs_connexion"] == "30/15min"
    assert taux["echecs_reinitialisation"] == "30/hour"
    assert taux["mot_de_passe_oublie"] == "5/hour"


def test_cross_site_requests_failing_csrf_do_not_burn_the_login_quota(agent: User) -> None:
    with _taux(connexion="3/min"):
        page_piegee = APIClient(enforce_csrf_checks=True)  # no token: a cross-site POST
        for _ in range(10):
            assert _login(page_piegee, "awa", "faux").status_code == 403
        collegue = APIClient(enforce_csrf_checks=True)
        jeton = {"HTTP_X_CSRFTOKEN": collegue.get(CSRF).json()["csrf_token"]}
        assert _login(collegue, "awa", **jeton).status_code == 200
    agent.refresh_from_db()
    assert agent.echecs_connexion == 0  # never even reached the password check


@pytest.mark.parametrize("url", [LOGIN_OTP, FORGOT, RESET])
def test_csrf_checked_before_the_throttle_on_every_anonymous_endpoint(url: str) -> None:
    with _taux(connexion_code="1/min", mot_de_passe_oublie_ip="1/min", reinitialisation="1/min"):
        client = APIClient(enforce_csrf_checks=True)
        for _ in range(4):
            assert client.post(url, {}, format="json").status_code == 403


def test_each_endpoint_has_its_own_bucket(agent: User) -> None:
    with _taux(
        connexion="2/min",
        connexion_code="2/min",
        mot_de_passe_oublie_ip="2/min",
        reinitialisation="2/min",
    ):
        for _ in range(2):
            _login(APIClient(), "awa", "faux")
        assert _login(APIClient(), "awa").status_code == 429
        # The login bucket is spent; the other endpoints of the same address still answer.
        assert APIClient().post(LOGIN_OTP, {"code": "123456"}, format="json").status_code == 401
        assert APIClient().post(FORGOT, {"identifiant": "x"}, format="json").status_code == 202
        corps = {
            "identifiant": "x",
            "code": "123456",
            "nouveau_mot_de_passe": "Phrase-tres-longue-77",
        }
        assert APIClient().post(RESET, corps, format="json").status_code == 400


@pytest.mark.parametrize(
    ("url", "portee"),
    [
        (LOGIN_OTP, "connexion_code"),
        (FORGOT, "mot_de_passe_oublie_ip"),
        (RESET, "reinitialisation"),
    ],
)
def test_each_anonymous_endpoint_is_limited_per_address(url: str, portee: str) -> None:
    corps = {"identifiant": "x", "code": "123456", "nouveau_mot_de_passe": "Phrase-tres-longue-77"}
    with _taux(**{portee: "2/min"}):
        for _ in range(2):
            assert APIClient().post(url, corps, format="json").status_code != 429
        refus = APIClient().post(url, corps, format="json")
        assert refus.status_code == 429 and "Retry-After" in refus
        autre = APIClient(REMOTE_ADDR="10.9.8.7")
        assert autre.post(url, corps, format="json").status_code != 429


def test_password_change_is_limited_per_user_not_per_address(agent: User) -> None:
    collegue = make_user(Role.AUDITEUR, username="ali", password=MDP)
    with _taux(changement_mot_de_passe="2/min"):
        client = connecter(APIClient(), agent)
        for _ in range(2):
            corps = {"ancien": "faux-mot-de-passe", "nouveau": "Phrase-tres-longue-77"}
            assert client.post(CHANGE, corps, format="json").status_code == 400
        assert client.post(CHANGE, corps, format="json").status_code == 429
        assert client.post(OTP_OFF, {"mot_de_passe": "x"}, format="json").status_code == 429
        # Same address, another agent: his own budget.
        autre = connecter(APIClient(), collegue)
        assert autre.post(CHANGE, corps, format="json").status_code == 400


# --- AUTH-04 ---------------------------------------------------------------------------------


def test_one_address_cannot_lock_many_accounts(caplog: pytest.LogCaptureFixture) -> None:
    comptes = [make_user(Role.AUDITEUR, username=f"agent{i}", password=MDP) for i in range(4)]
    with _taux(echecs_connexion="10/15min", connexion="1000/min"):
        attaquant = APIClient(REMOTE_ADDR="203.0.113.7")
        reponses = [
            _login(attaquant, compte.username, "faux").status_code
            for compte in comptes
            for _ in range(5)
        ]
        # 10 failures from the address: 2 accounts locked, then 429 before any check.
        assert reponses[:10] == [401] * 10 and set(reponses[10:]) == {429}
        verrouilles = User.objects.filter(verrouille_jusqu_a__isnull=False).count()
        assert verrouilles == 2
        refus = _login(attaquant, "agent3")
        assert refus.status_code == 429 and "Retry-After" in refus
        # The right password of an untouched account, from elsewhere, still works.
        assert _login(APIClient(REMOTE_ADDR="198.51.100.20"), "agent3").status_code == 200
    assert any(
        r.name == "onea.securite"
        and "plafond" in r.getMessage().lower()
        and "203.0.113.7" in r.getMessage()
        for r in caplog.records
    )


def test_successful_logins_do_not_count_as_failures(agent: User) -> None:
    with _taux(echecs_connexion="2/15min", connexion="1000/min"):
        for _ in range(5):
            assert _login(APIClient(), "awa").status_code == 200


def test_wrong_login_codes_count_too(agent: User) -> None:
    agent.otp_connexion_actif = True
    agent.save()
    with _taux(echecs_connexion="2/15min", connexion="1000/min", connexion_code="1000/min"):
        client = APIClient()
        assert _login(client, "awa").json()["etape"] == "OTP"
        assert client.post(LOGIN_OTP, {"code": "000001"}, format="json").status_code == 401
        assert client.post(LOGIN_OTP, {"code": "000002"}, format="json").status_code == 401
        assert client.post(LOGIN_OTP, {"code": "000003"}, format="json").status_code == 429
        assert _login(APIClient(), "awa").status_code == 429


def test_wrong_reset_codes_capped_per_address(agent: User) -> None:
    corps = {
        "identifiant": "awa",
        "code": "123456",
        "nouveau_mot_de_passe": "Phrase-tres-longue-77",
    }
    with _taux(echecs_reinitialisation="3/hour", reinitialisation="1000/min"):
        for _ in range(3):
            assert APIClient().post(RESET, corps, format="json").status_code == 400
        assert APIClient().post(RESET, corps, format="json").status_code == 429
        assert (
            APIClient(REMOTE_ADDR="10.1.1.1").post(RESET, corps, format="json").status_code == 400
        )


def test_failure_cap_fails_open_when_the_cache_is_down(
    agent: User, caplog: pytest.LogCaptureFixture
) -> None:
    from unittest import mock

    from django.core.cache import cache
    from redis.exceptions import ConnectionError as RedisConnectionError

    panne = mock.Mock(side_effect=RedisConnectionError("down"))
    with (
        _taux(echecs_connexion="1/15min"),
        mock.patch.object(cache, "get", panne),
        mock.patch.object(cache, "set", panne),
        mock.patch.object(cache, "get_many", panne),
        mock.patch.object(cache, "add", panne),
        mock.patch.object(cache, "incr", panne),
        caplog.at_level(logging.WARNING),
    ):
        for _ in range(3):
            assert _login(APIClient(), "awa", "faux").status_code == 401
    # The account lockout still applies (database), and the outage is logged.
    agent.refresh_from_db()
    assert agent.echecs_connexion == 3
    assert "cache indisponible" in caplog.text


# --- AUTH-12 ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("adresse", "cle"),
    [
        ("2001:db8:1:2:aaaa:bbbb:cccc:dddd", "2001:db8:1:2::/64"),
        ("2001:db8:1:2::1", "2001:db8:1:2::/64"),
        ("198.51.100.7", "198.51.100.7"),
        (None, "inconnue"),
    ],
)
def test_ipv6_counts_by_its_64(adresse: str | None, cle: str) -> None:
    requete = type("R", (), {"META": {"REMOTE_ADDR": adresse} if adresse else {}})()
    assert cle_adresse(requete) == cle


def test_ipv6_neighbours_share_one_bucket(agent: User) -> None:
    with _taux(connexion="2/min"):
        for suffixe in ("1", "2"):
            _login(APIClient(REMOTE_ADDR=f"2001:db8:5:6::{suffixe}"), "awa", "faux")
        assert _login(APIClient(REMOTE_ADDR="2001:db8:5:6::ffff"), "awa").status_code == 429
        assert _login(APIClient(REMOTE_ADDR="2001:db8:5:7::1"), "awa").status_code == 200


def test_rate_format_accepts_a_period_multiplier() -> None:
    assert analyser_taux("30/15min") == (30, 900)
    assert analyser_taux("20/min") == (20, 60)
    assert analyser_taux("5/hour") == (5, 3600)
    with pytest.raises(ValueError):
        analyser_taux("30/15")


# --- AUTH-06 ---------------------------------------------------------------------------------


def test_admin_login_form_goes_through_the_address_limits() -> None:
    staff = make_user(Role.ADMIN, username="chef", password=MDP, is_staff=True)
    with _taux(echecs_connexion="3/15min", connexion="1000/min"):
        client = Client(REMOTE_ADDR="203.0.113.9")
        for _ in range(3):
            r = client.post("/admin/login/", {"username": "inconnu", "password": "x"})
            assert r.status_code == 200  # the form again
        # Cap reached: even the right password is refused from this address, uniformly.
        r = client.post("/admin/login/", {"username": "chef", "password": MDP})
        assert r.status_code == 200
        assert "_auth_user_id" not in client.session
        staff.refresh_from_db()
        assert staff.echecs_connexion == 0  # refused before the password was even checked
        ailleurs = Client(REMOTE_ADDR="198.51.100.30")
        r = ailleurs.post("/admin/login/", {"username": "chef", "password": MDP})
        assert r.status_code == 302
