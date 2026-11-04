"""Forgotten password (code by email), password change, optional login OTP."""

import logging
import re
from datetime import timedelta
from typing import Any, cast
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.conf import settings
from django.contrib.auth import hashers
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import auth_services
from apps.users.models import CodeOtp, ObjetOtp, Role, User
from apps.users.serializers import MeSerializer

from ..factories import make_user

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
LOGIN_OTP = "/api/v1/auth/login/otp/"
SESSION = "/api/v1/auth/session/"
FORGOT = "/api/v1/auth/password/forgot/"
RESET = "/api/v1/auth/password/reset/"
CHANGE = "/api/v1/auth/password/change/"
OTP_ON = "/api/v1/auth/otp/enable/"
OTP_OFF = "/api/v1/auth/otp/disable/"
MDP = "Mot-de-passe-solide-2026"
NOUVEAU = "Nouvelle-phrase-secrete-77"
CODE_INVALIDE = {"detail": "Code invalide ou expiré.", "errors": {}}
SANS_SMTP = {"EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": ""}


@pytest.fixture
def agent() -> User:
    return make_user(
        Role.AUDITEUR, username="awa.ouedraogo", email="Awa.Ouedraogo@onea.bf", password=MDP
    )


def _login(client: APIClient, identifiant: str = "awa.ouedraogo", mot_de_passe: str = MDP) -> Any:
    return client.post(
        LOGIN, {"identifiant": identifiant, "mot_de_passe": mot_de_passe}, format="json"
    )


def _connecte(identifiant: str = "awa.ouedraogo", mot_de_passe: str = MDP) -> APIClient:
    client = APIClient()
    assert _login(client, identifiant, mot_de_passe).status_code == 200
    return client


def _forgot(identifiant: str, client: APIClient | None = None) -> Any:
    return (client or APIClient()).post(FORGOT, {"identifiant": identifiant}, format="json")


def _reset(identifiant: str, code: str, nouveau: str = NOUVEAU) -> Any:
    return APIClient().post(
        RESET,
        {"identifiant": identifiant, "code": code, "nouveau_mot_de_passe": nouveau},
        format="json",
    )


def _change(client: APIClient, ancien: str = MDP, nouveau: str = NOUVEAU) -> Any:
    return client.post(CHANGE, {"ancien": ancien, "nouveau": nouveau}, format="json")


def _code_du_courriel() -> str:
    trouve = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert trouve is not None
    return trouve.group(1)


def _faux(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def _taux(**taux: str) -> Any:
    actuels = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    rates = {**actuels, **taux}
    return override_settings(
        REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}
    )


def _entetes(reponse: Any) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((k, v) for k, v in reponse.headers.items() if k != "X-Correlation-ID"))


# --- forgotten password ------------------------------------------------------------


def test_forgot_identical_for_unknown_disabled_and_active(agent: User) -> None:
    make_user(username="desactive", email="desactive@onea.bf", password=MDP, is_active=False)
    verrouille = make_user(username="verrouille", email="verrouille@onea.bf", password=MDP)
    verrouille.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    verrouille.save()

    reponses = [
        _forgot("inconnu"),
        _forgot("inconnu@onea.bf"),
        _forgot("desactive"),
        _forgot("desactive@onea.bf"),
        _forgot("verrouille"),
        _forgot("awa.ouedraogo"),
        _forgot("awa.ouedraogo@onea.bf"),
    ]
    attendu = reponses[0].json()
    assert set(attendu) == {"detail"}
    assert "code" in attendu["detail"]
    for r in reponses:
        assert r.status_code == 202
        assert r.json() == attendu
        assert settings.SESSION_COOKIE_NAME not in r.cookies
    assert len({_entetes(r) for r in reponses}) == 1


def test_forgot_does_the_same_work_whatever_the_account(
    agent: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The email goes out from a task: the request only finds the account and queues it."""
    make_user(username="desactive", password=MDP, is_active=False)
    from apps.users.tasks import envoyer_code_reinitialisation

    file = mock.Mock()
    monkeypatch.setattr(envoyer_code_reinitialisation, "delay", file)
    for identifiant in ("inconnu", "desactive", "awa.ouedraogo"):
        assert _forgot(identifiant).status_code == 202
    assert file.call_count == 3  # queued for every request, known or not
    assert len(mail.outbox) == 0  # nothing sent from the request itself


def test_forgot_sends_code_only_to_active_account(agent: User) -> None:
    desactive = make_user(
        username="desactive", email="desactive@onea.bf", password=MDP, is_active=False
    )
    for identifiant in ("inconnu", "inconnu@onea.bf", "desactive", "desactive@onea.bf"):
        _forgot(identifiant)
    assert len(mail.outbox) == 0
    assert not CodeOtp.objects.filter(user=desactive).exists()

    _forgot("AWA.OUEDRAOGO@onea.bf")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["Awa.Ouedraogo@onea.bf"]
    assert "réinitialisation" in mail.outbox[0].subject
    code = _code_du_courriel()
    stocke = CodeOtp.objects.get(user=agent, objet=ObjetOtp.RESET, utilise_le__isnull=True)
    assert code not in stocke.code_hash


def test_forgot_locked_account_gets_a_code(agent: User) -> None:
    agent.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    agent.save()
    _forgot("awa.ouedraogo")
    assert len(mail.outbox) == 1


def test_forgot_sends_nothing_without_email_configured(agent: User) -> None:
    with override_settings(**SANS_SMTP):
        r = _forgot("awa.ouedraogo")
    assert r.status_code == 202
    assert len(mail.outbox) == 0


def test_forgot_is_throttled_per_identifier_without_storing_it(agent: User) -> None:
    with _taux(mot_de_passe_oublie="2/hour"):
        for _ in range(2):
            client = APIClient(REMOTE_ADDR="10.0.0.1")
            assert _forgot("awa.ouedraogo@onea.bf", client).status_code == 202
        # Another address and another letter case: still the same identifier.
        r = _forgot(" AWA.Ouedraogo@ONEA.bf ", APIClient(REMOTE_ADDR="10.0.0.2"))
        assert r.status_code == 429
        assert "Retry-After" in r
        # Unknown identifiers are throttled exactly the same way (no enumeration).
        for _ in range(2):
            assert _forgot("personne@onea.bf").status_code == 202
        assert _forgot("personne@onea.bf").status_code == 429
        # Other identifiers are not affected.
        assert _forgot("awa.ouedraogo").status_code == 202

    from apps.users.auth_throttles import MotDePasseOublieParIdentifiantThrottle

    vue = mock.Mock()
    requete = mock.Mock(data={"identifiant": "awa.ouedraogo@onea.bf"})
    cle = MotDePasseOublieParIdentifiantThrottle().get_cache_key(requete, vue)
    assert cle is not None
    assert "awa" not in cle.lower() and "onea" not in cle.lower()


def test_forgot_is_throttled_per_ip(agent: User) -> None:
    with _taux(connexion="2/min"):
        assert _forgot("a1").status_code == 202
        assert _forgot("a2").status_code == 202
        assert _forgot("a3").status_code == 429
        assert _forgot("a3", APIClient(REMOTE_ADDR="10.9.8.7")).status_code == 202


def test_forgot_caps_codes_per_account_silently(agent: User) -> None:
    with _taux(mot_de_passe_oublie="100/hour", connexion="100/min"):
        for _ in range(auth_services.CODES_REINITIALISATION_MAX + 2):
            assert _forgot("awa.ouedraogo").status_code == 202
    assert len(mail.outbox) == auth_services.CODES_REINITIALISATION_MAX


def test_forgot_requires_csrf(agent: User) -> None:
    client = APIClient(enforce_csrf_checks=True)
    assert _forgot("awa.ouedraogo", client).status_code == 403
    assert len(mail.outbox) == 0


# --- reset with the code -----------------------------------------------------------


def test_reset_with_code_changes_password_and_kills_sessions(agent: User) -> None:
    autre = make_user(username="autre", password=MDP)
    poste_1, poste_2, autre_client = _connecte(), _connecte(), _connecte("autre")
    agent.refresh_from_db()
    agent.doit_changer_mot_de_passe = True
    agent.mot_de_passe_expire_le = timezone.now() + timedelta(hours=1)
    agent.echecs_connexion = 3
    agent.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    agent.save()

    _forgot("awa.ouedraogo")
    code = _code_du_courriel()
    r = _reset("awa.ouedraogo", code)
    assert r.status_code == 204

    agent.refresh_from_db()
    assert agent.check_password(NOUVEAU)
    assert agent.doit_changer_mot_de_passe is False
    assert agent.mot_de_passe_expire_le is None
    assert agent.echecs_connexion == 0
    assert agent.verrouille_jusqu_a is None
    assert agent.is_active is True

    # Every session of the agent is gone (rows deleted), the other account's is kept.
    for client in (poste_1, poste_2):
        assert client.get(SESSION).status_code == 401
    assert Session.objects.count() == 1
    assert autre_client.get(SESSION).status_code == 200
    assert autre.is_active

    # Old password refused, new one accepted; the code is single use.
    assert _login(APIClient()).status_code == 401
    assert _login(APIClient(), mot_de_passe=NOUVEAU).json()["etape"] == "OK"
    assert _reset("awa.ouedraogo", code, "Encore-une-autre-phrase-88").json() == CODE_INVALIDE


def test_reset_by_email_identifier(agent: User) -> None:
    _forgot("awa.ouedraogo@onea.bf")
    assert _reset("AWA.OUEDRAOGO@ONEA.BF", _code_du_courriel()).status_code == 204
    agent.refresh_from_db()
    assert agent.check_password(NOUVEAU)


def test_reset_wrong_code_five_times_locks_code(agent: User) -> None:
    _forgot("awa.ouedraogo")
    code = _code_du_courriel()
    for _ in range(5):
        r = _reset("awa.ouedraogo", _faux(code))
        assert r.status_code == 400
        assert r.json() == CODE_INVALIDE
    r = _reset("awa.ouedraogo", code)
    assert r.status_code == 400
    assert r.json() == CODE_INVALIDE
    agent.refresh_from_db()
    assert agent.check_password(MDP)
    # Code checks are not login failures: no lock of the account from this route.
    assert agent.echecs_connexion == 0
    assert agent.verrouille_jusqu_a is None


def test_reset_rejects_weak_password(agent: User) -> None:
    _forgot("awa.ouedraogo")
    code = _code_du_courriel()
    for faible in ("court-2026", "123456789012345", "password1234", "awa.ouedraogo1"):
        r = _reset("awa.ouedraogo", code, faible)
        assert r.status_code == 400, faible
        assert set(r.json()["errors"]) == {"nouveau_mot_de_passe"}, faible
    agent.refresh_from_db()
    assert agent.check_password(MDP)
    # A refused password does not burn the code.
    assert _reset("awa.ouedraogo", code).status_code == 204


def test_reset_weak_password_answer_does_not_depend_on_the_account(agent: User) -> None:
    """The account-specific (similarity) check only runs once the code is right."""
    sur_compte = _reset("awa.ouedraogo", "123456", "awa.ouedraogo1")
    inconnu = _reset("personne", "123456", "awa.ouedraogo1")
    assert sur_compte.status_code == inconnu.status_code == 400
    assert sur_compte.json() == inconnu.json() == CODE_INVALIDE


def test_reset_uniform_failure_whatever_the_reason(agent: User) -> None:
    desactive = make_user(username="desactive", email="d@onea.bf", password=MDP)
    code_desactive = auth_services.emettre_otp(desactive, ObjetOtp.RESET)
    desactive.is_active = False
    desactive.save()
    expire = make_user(username="expire", password=MDP)
    code_expire = auth_services.emettre_otp(expire, ObjetOtp.RESET)
    CodeOtp.objects.filter(user=expire).update(expire_le=timezone.now() - timedelta(seconds=1))
    sans_code = make_user(username="sans.code", password=MDP)
    code_connexion = auth_services.emettre_otp(sans_code, ObjetOtp.LOGIN)

    _forgot("awa.ouedraogo")
    code = _code_du_courriel()
    reponses = [
        _reset("inconnu", code),
        _reset("inconnu@onea.bf", code),
        _reset("awa.ouedraogo", _faux(code)),
        _reset("desactive", code_desactive),  # a valid code issued before the disabling
        _reset("expire", code_expire),
        _reset("sans.code", code_connexion),  # a LOGIN code is not a RESET code
    ]
    for r in reponses:
        assert r.status_code == 400
        assert r.json() == CODE_INVALIDE
    assert len({_entetes(r) for r in reponses}) == 1

    desactive.refresh_from_db()
    assert desactive.is_active is False
    assert desactive.check_password(MDP)
    expire.refresh_from_db()
    assert expire.check_password(MDP)


@pytest.mark.parametrize("cas", ["inconnu", "desactive", "sans_code", "mauvais_code"])
def test_reset_failure_costs_one_hash(
    agent: User, monkeypatch: pytest.MonkeyPatch, cas: str
) -> None:
    make_user(username="desactive", password=MDP, is_active=False)
    if cas == "mauvais_code":
        code = auth_services.emettre_otp(agent, ObjetOtp.RESET)
    identifiant = {"inconnu": "personne", "desactive": "desactive"}.get(cas, "awa.ouedraogo")
    saisi = _faux(code) if cas == "mauvais_code" else "123456"
    hachages = mock.Mock(wraps=hashers.make_password)
    verifications = mock.Mock(wraps=hashers.check_password)
    monkeypatch.setattr(auth_services, "make_password", hachages)
    monkeypatch.setattr(auth_services, "check_password", verifications)
    assert auth_services.reinitialiser_mot_de_passe(identifiant, saisi, NOUVEAU) is None
    assert hachages.call_count + verifications.call_count == 1


def test_reset_cancels_a_pending_login_code(agent: User) -> None:
    agent.otp_connexion_actif = True
    agent.save()
    attaquant = APIClient()
    assert _login(attaquant).json()["etape"] == "OTP"
    code_connexion = _code_du_courriel()

    _forgot("awa.ouedraogo")
    assert _reset("awa.ouedraogo", _code_du_courriel()).status_code == 204
    # The password step was passed with the old password: that pending login is over.
    assert attaquant.post(LOGIN_OTP, {"code": code_connexion}, format="json").status_code == 401


def test_reset_is_throttled_per_ip(agent: User) -> None:
    with _taux(connexion="2/min"):
        assert _reset("x", "123456").status_code == 400
        assert _reset("x", "123456").status_code == 400
        assert _reset("x", "123456").status_code == 429


# --- password change ---------------------------------------------------------------


def test_change_requires_old_password(agent: User) -> None:
    client = _connecte()
    r = _change(client, ancien="pas-le-bon-mot-de-passe")
    assert r.status_code == 400
    assert set(r.json()["errors"]) == {"ancien"}
    agent.refresh_from_db()
    assert agent.check_password(MDP)
    assert agent.echecs_connexion == 1  # a wrong current password counts as a failed login

    meme = _change(client, nouveau=MDP)
    assert meme.status_code == 400
    assert set(meme.json()["errors"]) == {"nouveau"}
    faible = _change(client, nouveau="123456789012345")
    assert faible.status_code == 400
    assert set(faible.json()["errors"]) == {"nouveau"}
    agent.refresh_from_db()
    assert agent.check_password(MDP)

    ok = _change(client)
    assert ok.status_code == 200
    agent.refresh_from_db()
    assert ok.json() == {"etape": "OK", "me": MeSerializer(agent).data}
    assert agent.check_password(NOUVEAU)
    assert agent.echecs_connexion == 0


def test_change_anonymous_is_401() -> None:
    assert _change(APIClient()).status_code == 401


def test_change_wrong_old_password_five_times_locks_the_account(agent: User) -> None:
    client = _connecte()
    for _ in range(5):
        assert _change(client, ancien="pas-le-bon-mot-de-passe").status_code == 400
    agent.refresh_from_db()
    assert agent.verrouille_jusqu_a is not None
    # Locked: even the right current password is refused.
    assert _change(client).status_code == 400
    agent.refresh_from_db()
    assert agent.check_password(MDP)


def test_change_keeps_current_session_and_ends_the_others(agent: User) -> None:
    client, autre_poste = _connecte(), _connecte()
    avant = client.session.session_key
    debut = client.session["onea_connexion_le"]
    expiration = client.session.get_expiry_date()
    assert _change(client).status_code == 200

    # The current session goes on under a new key, with its login stamp and fixed expiry.
    assert client.get(SESSION).status_code == 200
    assert client.get("/api/v1/me/").status_code == 200
    assert client.session.session_key != avant
    assert client.session["onea_connexion_le"] == debut
    assert client.session.get_expiry_date() == expiration
    # Every other session of the agent is gone.
    assert autre_poste.get(SESSION).status_code == 401
    assert Session.objects.count() == 1


def test_forced_change_then_full_access(agent: User) -> None:
    agent.doit_changer_mot_de_passe = True
    agent.mot_de_passe_expire_le = timezone.now() + timedelta(hours=72)
    agent.save()
    client = APIClient()
    assert _login(client).json()["etape"] == "CHANGER_MOT_DE_PASSE"
    assert client.get("/api/v1/me/").status_code == 403

    r = _change(client)
    assert r.status_code == 200
    assert r.json()["etape"] == "OK"
    agent.refresh_from_db()
    assert agent.doit_changer_mot_de_passe is False
    assert agent.mot_de_passe_expire_le is None
    assert client.get("/api/v1/me/").status_code == 200
    assert client.get(SESSION).json()["etape"] == "OK"


def test_change_requires_csrf(agent: User) -> None:
    client = APIClient(enforce_csrf_checks=True)
    jeton = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    assert (
        client.post(
            LOGIN,
            {"identifiant": "awa.ouedraogo", "mot_de_passe": MDP},
            format="json",
            HTTP_X_CSRFTOKEN=jeton,
        ).status_code
        == 200
    )
    assert _change(client).status_code == 403
    nouveau = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    r = client.post(
        CHANGE, {"ancien": MDP, "nouveau": NOUVEAU}, format="json", HTTP_X_CSRFTOKEN=nouveau
    )
    assert r.status_code == 200


# --- login OTP option --------------------------------------------------------------


def test_otp_enable_refused_without_email(agent: User) -> None:
    client = _connecte()
    with override_settings(**SANS_SMTP):
        r = client.post(OTP_ON)
    assert r.status_code == 409
    assert r.json() == {"detail": "Envoi de courriels non configuré", "errors": {}}
    agent.refresh_from_db()
    assert agent.otp_connexion_actif is False


def test_otp_enable_refused_when_account_has_no_email() -> None:
    sans = make_user(username="sans.courriel", email="", password=MDP)
    r = _connecte("sans.courriel").post(OTP_ON)
    assert r.status_code == 409
    sans.refresh_from_db()
    assert sans.otp_connexion_actif is False


def test_otp_enable_and_disable_by_owner(agent: User) -> None:
    client = _connecte()
    r = client.post(OTP_ON)
    assert r.status_code == 200
    assert r.json() == {"otp_connexion_actif": True}
    agent.refresh_from_db()
    assert agent.otp_connexion_actif is True
    entree = LogEntry.objects.get_for_object(agent).order_by("-timestamp").first()
    assert entree is not None
    assert entree.actor == agent
    assert "otp_connexion_actif" in entree.changes_dict

    r = client.post(OTP_OFF)
    assert r.status_code == 200
    assert r.json() == {"otp_connexion_actif": False}
    agent.refresh_from_db()
    assert agent.otp_connexion_actif is False
    # Disabling stays possible without email (the way out of a blocked OTP).
    with override_settings(**SANS_SMTP):
        assert client.post(OTP_OFF).status_code == 200


def test_otp_endpoints_anonymous_401() -> None:
    assert APIClient().post(OTP_ON).status_code == 401
    assert APIClient().post(OTP_OFF).status_code == 401


def test_login_requires_otp_when_enabled(agent: User) -> None:
    client = _connecte()
    assert client.post(OTP_ON).status_code == 200
    client.post("/api/v1/auth/logout/")

    r = _login(client)
    assert r.status_code == 200
    assert r.json() == {"etape": "OTP", "me": None}
    assert client.get("/api/v1/me/").status_code == 401
    ok = client.post(LOGIN_OTP, {"code": _code_du_courriel()}, format="json")
    assert ok.status_code == 200
    assert ok.json()["etape"] == "OK"
    assert client.get("/api/v1/me/").status_code == 200


def test_otp_cannot_be_enabled_by_admin_for_other_user(agent: User) -> None:
    make_user(Role.ADMIN, username="chef", email="chef@onea.bf", password=MDP)
    admin = _connecte("chef")
    for corps in ({"user": agent.pk}, {"id": agent.pk}, {"username": "awa.ouedraogo"}):
        assert admin.post(OTP_ON, corps, format="json").status_code == 200
    agent.refresh_from_db()
    assert agent.otp_connexion_actif is False  # only the caller's own account changed
    assert User.objects.get(username="chef").otp_connexion_actif is True
    # No route takes a target account.
    for chemin in (f"/api/v1/auth/otp/enable/{agent.pk}/", f"/api/v1/users/{agent.pk}/otp/"):
        assert admin.post(chemin).status_code in (404, 405), chemin
    with pytest.raises(NoReverseMatch):
        reverse("auth-otp-enable", args=[agent.pk])


# --- security log ------------------------------------------------------------------


def test_password_events_are_logged_without_secrets(
    agent: User, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="onea.securite"):
        _forgot("awa.ouedraogo")
        code = _code_du_courriel()
        _reset("awa.ouedraogo", _faux(code))
        _reset("awa.ouedraogo", code)
        client = _connecte(mot_de_passe=NOUVEAU)
        _change(client, ancien=NOUVEAU, nouveau="Troisieme-phrase-secrete-99")
        client.post(OTP_ON)
        client.post(OTP_OFF)
    messages = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    texte = "\n".join(messages)
    for secret in (MDP, NOUVEAU, "Troisieme-phrase-secrete-99", code, "awa.ouedraogo"):
        assert secret not in texte
    assert f"compte={agent.pk}" in texte
    assert any("réinitialis" in m for m in messages)
    assert any("changé" in m for m in messages)
    assert any("activé" in m for m in messages)
    assert any("désactivé" in m for m in messages)
