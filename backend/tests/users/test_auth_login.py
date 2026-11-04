"""In-app session login: uniform errors, lockout, session lifetime, CSRF, forced change."""

import logging
import re
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core import mail
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.middleware import MotDePasseAChangerMiddleware
from apps.users import auth_services
from apps.users.auth_services import authentifier
from apps.users.models import Role, User
from apps.users.oidc import OneaOIDCBackend
from apps.users.serializers import MeSerializer

from ..factories import make_user
from .test_oidc import _bearer, claims

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
LOGIN_OTP = "/api/v1/auth/login/otp/"
LOGOUT = "/api/v1/auth/logout/"
SESSION = "/api/v1/auth/session/"
CSRF = "/api/v1/auth/csrf/"
MDP = "Mot-de-passe-solide-2026"
ECHEC = {"detail": "Identifiant ou mot de passe incorrect.", "errors": {}}


@pytest.fixture
def agent() -> User:
    return make_user(
        Role.AUDITEUR, username="awa.ouedraogo", email="Awa.Ouedraogo@onea.bf", password=MDP
    )


def _login(client: APIClient, identifiant: str, mot_de_passe: str = MDP) -> Any:
    return client.post(
        LOGIN, {"identifiant": identifiant, "mot_de_passe": mot_de_passe}, format="json"
    )


def _vieillir_session(client: APIClient, **decalages: timedelta) -> None:
    """Move the session timestamps back in time (no time-travel library in the project)."""
    session = client.session
    for cle, decalage in decalages.items():
        session[cle] = session[cle] - decalage.total_seconds()
    session.save()


# --- login -------------------------------------------------------------------------


def test_login_ok_sets_session_cookie(agent: User) -> None:
    client = APIClient()
    r = _login(client, "awa.ouedraogo")
    assert r.status_code == 200
    assert r.json() == {"etape": "OK", "me": MeSerializer(agent).data}
    cookie = r.cookies[settings.SESSION_COOKIE_NAME]
    assert cookie.value
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    assert Session.objects.count() == 1
    # The session now authenticates the API, with the same `me` contract as /me/.
    assert client.get("/api/v1/me/").json() == r.json()["me"]
    session = client.get(SESSION)
    assert session.status_code == 200
    assert session.json() == {"etape": "OK", "me": MeSerializer(agent).data}
    agent.refresh_from_db()
    assert agent.premiere_connexion_le is not None
    assert agent.last_login is not None


def test_session_endpoint_anonymous_is_401() -> None:
    r = APIClient().get(SESSION)
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}


def test_unknown_wrong_password_and_locked_give_identical_response(agent: User) -> None:
    verrouille = make_user(username="verrouille", password=MDP)
    verrouille.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    verrouille.save()
    make_user(username="desactive", password=MDP, is_active=False)
    expire = make_user(username="expire", password=MDP)
    expire.doit_changer_mot_de_passe = True
    expire.mot_de_passe_expire_le = timezone.now() - timedelta(minutes=1)
    expire.save()

    reponses = [
        _login(APIClient(), "inconnu"),
        _login(APIClient(), "inconnu@onea.bf"),
        _login(APIClient(), "awa.ouedraogo", "mauvais-mot-de-passe"),
        _login(APIClient(), "verrouille"),
        _login(APIClient(), "desactive"),
        _login(APIClient(), "expire"),
    ]
    for r in reponses:
        assert r.status_code == 401
        assert r.json() == ECHEC
        assert settings.SESSION_COOKIE_NAME not in r.cookies
    # Same headers too, except the per-request correlation id.
    entetes = [
        tuple(sorted((k, v) for k, v in r.headers.items() if k != "X-Correlation-ID"))
        for r in reponses
    ]
    assert len(set(entetes)) == 1
    assert Session.objects.count() == 0


def test_unknown_account_still_hashes_a_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timing: an unknown account costs one hash, like a real password check."""
    espion = mock.Mock(wraps=auth_services.make_password)
    monkeypatch.setattr(auth_services, "make_password", espion)
    assert authentifier("personne", MDP).etape is None
    espion.assert_called_once()


def test_unusable_password_account_still_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    compte = make_user(username="sans.mdp")
    compte.set_unusable_password()
    compte.save()
    espion = mock.Mock(wraps=auth_services.make_password)
    monkeypatch.setattr(auth_services, "make_password", espion)
    assert authentifier("sans.mdp", MDP).etape is None
    espion.assert_called_once()


def test_lock_after_5_failures_for_15_minutes(agent: User) -> None:
    client = APIClient()
    for _ in range(4):
        assert _login(client, "awa.ouedraogo", "faux").status_code == 401
    agent.refresh_from_db()
    assert agent.echecs_connexion == 4
    assert agent.verrouille_jusqu_a is None

    avant = timezone.now()
    assert _login(client, "awa.ouedraogo", "faux").json() == ECHEC
    agent.refresh_from_db()
    assert agent.verrouille_jusqu_a is not None
    duree = agent.verrouille_jusqu_a - avant
    assert timedelta(minutes=14, seconds=55) < duree <= timedelta(minutes=15, seconds=5)

    # Locked: even the right password is refused, with the same answer, lock not extended.
    fin = agent.verrouille_jusqu_a
    r = _login(client, "awa.ouedraogo")
    assert r.status_code == 401
    assert r.json() == ECHEC
    agent.refresh_from_db()
    assert agent.verrouille_jusqu_a == fin

    # 15 minutes later the account opens again and the counters are reset.
    agent.verrouille_jusqu_a = timezone.now() - timedelta(seconds=1)
    agent.save()
    assert _login(client, "awa.ouedraogo").status_code == 200
    agent.refresh_from_db()
    assert agent.echecs_connexion == 0
    assert agent.verrouille_jusqu_a is None


def test_successful_login_resets_failure_counter(agent: User) -> None:
    for _ in range(4):
        _login(APIClient(), "awa.ouedraogo", "faux")
    assert _login(APIClient(), "awa.ouedraogo").status_code == 200
    agent.refresh_from_db()
    assert agent.echecs_connexion == 0
    # 4 new failures do not lock: the count restarted from zero.
    for _ in range(4):
        _login(APIClient(), "awa.ouedraogo", "faux")
    agent.refresh_from_db()
    assert agent.verrouille_jusqu_a is None


def test_failed_login_by_email_counts_on_the_account(agent: User) -> None:
    entrees = LogEntry.objects.get_for_object(agent).count()
    _login(APIClient(), "awa.ouedraogo@onea.bf", "faux")
    agent.refresh_from_db()
    assert agent.echecs_connexion == 1
    # The counter is a technical field: no audit-trail entry per failed attempt.
    assert LogEntry.objects.get_for_object(agent).count() == entrees


def test_disabled_account_cannot_login(agent: User) -> None:
    agent.is_active = False
    agent.desactive_le = timezone.now()
    agent.save()
    r = _login(APIClient(), "awa.ouedraogo")
    assert r.status_code == 401
    assert r.json() == ECHEC


def test_disabled_account_session_rejected_on_next_request(agent: User) -> None:
    client = APIClient()
    assert _login(client, "awa.ouedraogo").status_code == 200
    assert client.get("/api/v1/me/").status_code == 200
    agent.is_active = False
    agent.desactive_le = timezone.now()
    agent.save()
    assert client.get("/api/v1/me/").status_code == 401
    assert client.get(SESSION).status_code == 401


def test_temp_password_expired_blocks_login(agent: User) -> None:
    agent.doit_changer_mot_de_passe = True
    agent.mot_de_passe_expire_le = timezone.now() - timedelta(seconds=1)
    agent.save()
    r = _login(APIClient(), "awa.ouedraogo")
    assert r.status_code == 401
    assert r.json() == ECHEC
    agent.refresh_from_db()
    assert agent.echecs_connexion == 0  # the right password is not a "failure"

    agent.mot_de_passe_expire_le = timezone.now() + timedelta(hours=1)
    agent.save()
    assert _login(APIClient(), "awa.ouedraogo").json()["etape"] == "CHANGER_MOT_DE_PASSE"


def test_must_change_password_only_allows_change_endpoint(agent: User) -> None:
    agent.doit_changer_mot_de_passe = True
    agent.save()
    client = APIClient()
    r = _login(client, "awa.ouedraogo")
    assert r.status_code == 200
    assert r.json() == {"etape": "CHANGER_MOT_DE_PASSE", "me": MeSerializer(agent).data}

    for chemin in ("/api/v1/me/", "/api/v1/missions/", "/api/v1/users/", "/api/v1/audit-log/"):
        bloque = client.get(chemin)
        assert bloque.status_code == 403, chemin
        assert bloque.json() == {
            "detail": "Vous devez changer votre mot de passe avant de continuer.",
            "errors": {},
        }
    assert (
        client.post("/api/v1/me/tutoriel/", {"action": "terminer", "version": 1}).status_code == 403
    )

    assert client.get(SESSION).json()["etape"] == "CHANGER_MOT_DE_PASSE"
    assert client.get(CSRF).status_code == 200
    assert client.post(LOGOUT).status_code == 204
    assert client.get(SESSION).status_code == 401


def test_must_change_middleware_lets_the_change_endpoint_through(agent: User) -> None:
    agent.doit_changer_mot_de_passe = True
    vue = mock.Mock(return_value=HttpResponse(status=200))
    middleware = MotDePasseAChangerMiddleware(vue)
    for chemin, attendu in (
        ("/api/v1/auth/password/change/", 200),
        ("/api/v1/auth/logout/", 200),
        ("/api/v1/auth/session/", 200),
        ("/api/v1/auth/csrf/", 200),
        ("/api/v1/auth/password/change/x/", 403),
        ("/admin/", 403),
    ):
        requete = RequestFactory().post(chemin)
        requete.session = {"_auth_user_id": str(agent.pk)}  # type: ignore[assignment]
        requete.user = agent
        assert middleware(requete).status_code == attendu, chemin


def test_login_with_email_or_username(agent: User) -> None:
    assert _login(APIClient(), "awa.ouedraogo").status_code == 200
    assert _login(APIClient(), "awa.ouedraogo@onea.bf").status_code == 200
    assert _login(APIClient(), "AWA.OUEDRAOGO@ONEA.BF").status_code == 200
    # An email shared by two accounts is ambiguous: refused, never the "first" account.
    make_user(username="homonyme", email="awa.ouedraogo@ONEA.bf", password=MDP)
    assert _login(APIClient(), "awa.ouedraogo@onea.bf").json() == ECHEC
    assert _login(APIClient(), "homonyme").status_code == 200


def test_empty_email_never_matches_accounts_without_email() -> None:
    make_user(username="sans.courriel", email="", password=MDP)
    assert _login(APIClient(), "", MDP).status_code == 400
    assert _login(APIClient(), "@", MDP).json() == ECHEC


# --- session lifetime --------------------------------------------------------------


def test_idle_30_minutes_expires_session(agent: User) -> None:
    client = APIClient()
    assert _login(client, "awa.ouedraogo").status_code == 200
    _vieillir_session(client, onea_activite_le=timedelta(minutes=29))
    assert client.get(SESSION).status_code == 200  # activity refreshes the idle timer

    _vieillir_session(client, onea_activite_le=timedelta(minutes=31))
    r = client.get(SESSION)
    assert r.status_code == 401
    assert client.get("/api/v1/me/").status_code == 401
    assert Session.objects.count() == 0


def test_absolute_8_hours_even_when_active(agent: User) -> None:
    client = APIClient()
    assert _login(client, "awa.ouedraogo").status_code == 200
    debut = client.session.get_expiry_date()
    assert timedelta(hours=7, minutes=59) < debut - timezone.now() <= timedelta(hours=8)
    # Activity never pushes the absolute expiry further.
    _vieillir_session(client, onea_activite_le=timedelta(minutes=5))
    assert client.get(SESSION).status_code == 200
    assert client.session.get_expiry_date() == debut

    _vieillir_session(
        client, onea_connexion_le=timedelta(hours=8, seconds=1), onea_activite_le=timedelta(0)
    )
    assert client.get(SESSION).status_code == 401


def test_logout_ends_session(agent: User) -> None:
    client = APIClient()
    _login(client, "awa.ouedraogo")
    assert client.post(LOGOUT).status_code == 204
    assert client.get("/api/v1/me/").status_code == 401
    assert Session.objects.count() == 0


# --- CSRF --------------------------------------------------------------------------


def test_csrf_required_on_post(agent: User) -> None:
    client = APIClient(enforce_csrf_checks=True)
    refus = _login(client, "awa.ouedraogo")
    assert refus.status_code == 403
    assert refus.json()["detail"] == "Jeton CSRF absent ou invalide : rechargez la page."

    jeton = client.get(CSRF)
    assert jeton.status_code == 200
    assert settings.CSRF_COOKIE_NAME in jeton.cookies
    entete = {"HTTP_X_CSRFTOKEN": jeton.json()["csrf_token"]}
    ok = client.post(
        LOGIN, {"identifiant": "awa.ouedraogo", "mot_de_passe": MDP}, format="json", **entete
    )
    assert ok.status_code == 200

    # Authenticated by the session: every unsafe method needs the (rotated) token.
    assert client.post(LOGOUT).status_code == 403
    assert (
        client.post("/api/v1/me/tutoriel/", {"action": "terminer", "version": 1}).status_code == 403
    )
    nouveau = {"HTTP_X_CSRFTOKEN": client.get(CSRF).json()["csrf_token"]}
    assert client.post(LOGOUT, **nouveau).status_code == 204


def test_bearer_requests_need_no_csrf(api_client: APIClient) -> None:
    client = APIClient(enforce_csrf_checks=True)
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims()):
        r = _bearer(client).post(
            "/api/v1/me/tutoriel/", {"action": "terminer", "version": 1}, format="json"
        )
    assert r.status_code == 200


# --- throttling, logging -----------------------------------------------------------


def test_login_is_throttled_per_ip(agent: User) -> None:
    taux = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "connexion": "3/min"}
    with override_settings(
        REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": taux}
    ):
        for _ in range(3):
            assert _login(APIClient(), "inconnu").status_code == 401
        r = _login(APIClient(), "awa.ouedraogo")
        assert r.status_code == 429
        assert "Retry-After" in r
        autre_ip = APIClient(REMOTE_ADDR="10.9.8.7")
        assert _login(autre_ip, "awa.ouedraogo").status_code == 200


def test_login_rate_is_configured() -> None:
    assert re.fullmatch(
        r"\d+/(sec|min|hour|day)", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["connexion"]
    )


def test_failed_login_is_logged_without_password(
    agent: User, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "Mon-Secret-Tres-Prive-42"  # noqa: S105 - test value
    with caplog.at_level(logging.INFO, logger="onea.securite"):
        _login(APIClient(), "awa.ouedraogo", secret)
        _login(APIClient(), secret, secret)  # password typed in the login field
    enregistrements = [r for r in caplog.records if r.name == "onea.securite"]
    assert len(enregistrements) == 2
    assert all(r.levelno == logging.WARNING for r in enregistrements)
    assert secret not in caplog.text
    assert MDP not in caplog.text
    assert str(agent.pk) in enregistrements[0].getMessage()


# --- OTP step ----------------------------------------------------------------------


def _code_du_courriel() -> str:
    trouve = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert trouve is not None
    return trouve.group(1)


def test_otp_step_when_enabled(agent: User) -> None:
    agent.otp_connexion_actif = True
    agent.save()
    client = APIClient()
    r = _login(client, "awa.ouedraogo")
    assert r.status_code == 200
    assert r.json() == {"etape": "OTP", "me": None}
    assert len(mail.outbox) == 1
    # Password alone does not authenticate.
    assert client.get(SESSION).status_code == 401
    assert client.get("/api/v1/me/").status_code == 401

    code = _code_du_courriel()
    faux = "000000" if code != "000000" else "111111"
    mauvais = client.post(LOGIN_OTP, {"code": faux}, format="json")
    assert mauvais.status_code == 401
    assert mauvais.json() == {"detail": "Code invalide ou expiré.", "errors": {}}

    ok = client.post(LOGIN_OTP, {"code": code}, format="json")
    assert ok.status_code == 200
    assert ok.json() == {"etape": "OK", "me": MeSerializer(agent).data}
    assert client.get("/api/v1/me/").status_code == 200
    # The code is single use.
    assert client.post(LOGIN_OTP, {"code": code}, format="json").status_code == 401


def test_otp_without_pending_login_is_401() -> None:
    r = APIClient().post(LOGIN_OTP, {"code": "123456"}, format="json")
    assert r.status_code == 401
    assert r.json() == {"detail": "Code invalide ou expiré.", "errors": {}}
