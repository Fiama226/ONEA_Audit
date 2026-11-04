"""Second security round on the in-app authentication (re-review findings N1-N9).

- N1: the per-address failure caps count wrong secrets only (and unknown accounts), never the
  refusal of a right secret (locked, disabled, expired temporary password, blocked reset);
- N2: the authentication emails go through their own Celery queue (`auth`);
- N3: every way a queued temporary password can be lost logs an ERROR with the operator's
  instruction; the queueing waits for the commit of an enclosing transaction;
- N4: the per-address failure counter is updated atomically;
- N5: the new tunables are validated at start-up;
- N6: the login codes mailed to an account are capped, and a code superseded by a newer one
  is refused without counting as a wrong attempt;
- N8: the per-address cap logs once per window;
- N9: `dummymail://` never counts as an active email sending, whatever its host.
"""

import logging
import threading
from datetime import timedelta
from typing import Any, cast
from unittest import mock

import pytest
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import auth_services, envois, services, tasks
from apps.users.auth_throttles import EchecsConnexionParIpThrottle
from apps.users.models import CodeOtp, EnvoiMotDePasse, NatureEnvoi, ObjetOtp, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
LOGIN_OTP = "/api/v1/auth/login/otp/"
RESET = "/api/v1/auth/password/reset/"
MDP = "Mot-de-passe-solide-2026"
NOUVEAU = "Nouvelle-phrase-secrete-77"


def _taux(**taux: str) -> Any:
    actuels = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    return override_settings(
        REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {**actuels, **taux}}
    )


def _login(client: APIClient, identifiant: str, mot_de_passe: str = MDP) -> Any:
    return client.post(
        LOGIN, {"identifiant": identifiant, "mot_de_passe": mot_de_passe}, format="json"
    )


def _reset(client: APIClient, identifiant: str, code: str) -> Any:
    corps = {"identifiant": identifiant, "code": code, "nouveau_mot_de_passe": NOUVEAU}
    return client.post(RESET, corps, format="json")


# --- N1 / D1 / D3 ----------------------------------------------------------------------------
# Counting policy of the per-address failure caps:
# - wrong secret on a usable account: every refusal counts;
# - unusable account (locked, disabled, expired temporary password, blocked reset): counted
#   ONCE per (address, account, window), whether the secret was right or wrong (D1: no
#   password oracle through the counter);
# - unknown identifier: every refusal counts, but at most 5 per (address, identifier, window).

SIEGE = "198.51.100.1"


def _echecs(adresse: str, portee: str = "connexion") -> int:
    from apps.users.auth_throttles import (
        EchecsConnexionParIpThrottle,
        EchecsReinitialisationParIpThrottle,
    )

    classe = (
        EchecsConnexionParIpThrottle
        if portee == "connexion"
        else (EchecsReinitialisationParIpThrottle)
    )
    requete = type("R", (), {"META": {"REMOTE_ADDR": adresse}})()
    return classe().nombre_echecs(requete)


def _inutilisable(etat: str, username: str) -> User:
    compte = make_user(Role.AUDITEUR, username=username, email=f"{username}@onea.bf", password=MDP)
    if etat == "verrouille":
        compte.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    elif etat == "desactive":
        compte.is_active = False
    else:
        compte.mot_de_passe_expire_le = timezone.now() - timedelta(minutes=1)
    compte.save()
    return compte


@pytest.mark.parametrize("etat", ["verrouille", "desactive", "mot_de_passe_expire"])
def test_counting_on_an_unusable_account_does_not_depend_on_the_password(etat: str) -> None:
    _inutilisable(etat, "awa")
    with _taux(echecs_connexion="1000/15min", connexion="100000/min"):
        for _ in range(4):
            assert _login(APIClient(REMOTE_ADDR="203.0.113.1"), "awa").status_code == 401
            assert _login(APIClient(REMOTE_ADDR="203.0.113.2"), "awa", "faux").status_code == 401
        # Right or wrong password: the same evolution, one unit for the account.
        assert _echecs("203.0.113.1") == _echecs("203.0.113.2") == 1


def test_password_oracle_through_the_counter_is_closed() -> None:
    """Fill the address counter to cap - 1, try a candidate on a locked account, then probe:
    the probe gets the same answer whether the candidate was the password or not."""
    _inutilisable("verrouille", "awa")
    resultats = {}
    for n, candidat in enumerate((MDP, "pas-le-bon")):
        adresse = f"203.0.113.{10 + n}"
        with _taux(echecs_connexion="6/15min", connexion="100000/min"):
            for i in range(5):  # 5 distinct unknown identifiers, one unit each
                assert _login(APIClient(REMOTE_ADDR=adresse), f"inconnu{i}", "x").status_code == 401
            _login(APIClient(REMOTE_ADDR=adresse), "awa", candidat)
            sonde = _login(APIClient(REMOTE_ADDR=adresse), "inconnu-sonde", "x").status_code
            resultats[candidat] = (sonde, _echecs(adresse))
    assert resultats[MDP] == resultats["pas-le-bon"] == (429, 6)


def test_head_office_retrying_locked_accounts_costs_one_unit_per_account() -> None:
    """An outside address locks 6 accounts; their owners, behind the head-office NAT, keep
    typing their password: 6 units in all, so the site's other agents still log in."""
    agents = [make_user(Role.AUDITEUR, username=f"agent{i}", password=MDP) for i in range(7)]
    with _taux(echecs_connexion="30/15min", connexion="100000/min"):
        dehors = APIClient(REMOTE_ADDR="203.0.113.50")
        for agent in agents[:6]:
            for _ in range(5):
                assert _login(dehors, agent.username, "faux").status_code == 401
        assert User.objects.filter(verrouille_jusqu_a__isnull=False).count() == 6
        for _ in range(10):
            for agent in agents[:6]:
                mot_de_passe = MDP if agent.pk % 2 else "une-faute-de-frappe"
                r = _login(APIClient(REMOTE_ADDR=SIEGE), agent.username, mot_de_passe)
                assert r.status_code == 401  # locked, uniform
        assert _echecs(SIEGE) == 6
        assert _login(APIClient(REMOTE_ADDR=SIEGE), "agent6").status_code == 200


def test_unknown_identifiers_count_up_to_five_each() -> None:
    with _taux(echecs_connexion="1000/15min", connexion="100000/min"):
        for _ in range(8):
            _login(APIClient(REMOTE_ADDR=SIEGE), "personne", "x")
        assert _echecs(SIEGE) == 5
        _login(APIClient(REMOTE_ADDR=SIEGE), "PERSONNE ", "x")  # same identifier, normalized
        assert _echecs(SIEGE) == 5
        _login(APIClient(REMOTE_ADDR=SIEGE), "quelqu.un", "x")
        assert _echecs(SIEGE) == 6


def test_wrong_passwords_on_usable_accounts_count_each() -> None:
    make_user(Role.AUDITEUR, username="ali", password=MDP)
    with _taux(echecs_connexion="1000/15min", connexion="100000/min"):
        for _ in range(3):
            assert _login(APIClient(REMOTE_ADDR=SIEGE), "ali", "faux").status_code == 401
        assert _echecs(SIEGE) == 3


def test_login_code_on_unusable_account_counted_once() -> None:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    compte.otp_connexion_actif = True
    compte.save()
    with _taux(echecs_connexion="1000/15min", connexion="100000/min", connexion_code="100000/min"):
        client = APIClient(REMOTE_ADDR=SIEGE)
        assert _login(client, "awa").json()["etape"] == "OTP"
        User.objects.filter(pk=compte.pk).update(
            verrouille_jusqu_a=timezone.now() + timedelta(minutes=10)
        )
        for code in ("000001", "000002", "000003"):
            assert client.post(LOGIN_OTP, {"code": code}, format="json").status_code == 401
        assert _echecs(SIEGE) == 1


@pytest.mark.parametrize("etat", ["desactive", "bloque"])
def test_reset_on_unusable_account_counted_the_same_whatever_the_code(etat: str) -> None:
    """D3: a disabled or blocked account counts the same, right code or not (round 4: like
    any reset refusal, at most 5 per typed identifier and address)."""
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    code = auth_services.emettre_otp(compte, ObjetOtp.RESET)
    if etat == "desactive":
        User.objects.filter(pk=compte.pk).update(is_active=False)
    else:
        User.objects.filter(pk=compte.pk).update(
            echecs_reinitialisation=settings.AUTH_REINITIALISATION_ECHECS_MAX,
            echecs_reinitialisation_depuis=timezone.now(),
        )
    with _taux(echecs_reinitialisation="1000/hour", reinitialisation="100000/min"):
        for _ in range(3):
            assert _reset(APIClient(REMOTE_ADDR="203.0.113.1"), "awa", code).status_code == 400
            assert _reset(APIClient(REMOTE_ADDR="203.0.113.2"), "awa", "000000").status_code == 400
        assert _echecs("203.0.113.1", "reset") == _echecs("203.0.113.2", "reset") == 3


def test_admin_login_on_a_locked_account_counted_once() -> None:
    from django.test import Client

    verrouille = make_user(Role.ADMIN, username="chef", password=MDP, is_staff=True)
    verrouille.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    verrouille.save()
    make_user(Role.ADMIN, username="adjoint", password=MDP, is_staff=True)
    with _taux(echecs_connexion="2/15min", connexion="100000/min"):
        client = Client(REMOTE_ADDR="198.51.100.2")
        for _ in range(4):
            r = client.post("/admin/login/", {"username": "chef", "password": MDP})
            assert r.status_code == 200  # the form again: refused
            assert "_auth_user_id" not in client.session
        assert _echecs("198.51.100.2") == 1
        r = client.post("/admin/login/", {"username": "adjoint", "password": MDP})
        assert r.status_code == 302


# --- N2 --------------------------------------------------------------------------------------


def test_auth_email_tasks_have_their_own_queue() -> None:
    routes = settings.CELERY_TASK_ROUTES
    for nom in (
        "users.envoyer_code_connexion",
        "users.envoyer_code_reinitialisation",
        "users.envoyer_mot_de_passe_temporaire",
    ):
        assert routes[nom] == {"queue": "auth"}, nom
    assert settings.CELERY_FILE_AUTHENTIFICATION == "auth"


# --- N3 --------------------------------------------------------------------------------------


@pytest.fixture
def file_mot_de_passe() -> Any:
    with mock.patch.object(tasks.envoyer_mot_de_passe_temporaire, "delay") as delay:
        yield delay


def _erreurs(caplog: pytest.LogCaptureFixture, compte: User) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "onea.securite"
        and r.levelname == "ERROR"
        and f"compte={compte.pk}" in r.getMessage()
        and "réinitialisez" in r.getMessage().lower()
    ]


def _en_file(admin: User, compte: User) -> str:
    services.reinitialiser_mot_de_passe(compte, par=admin)
    return str(EnvoiMotDePasse.objects.get(user=compte).pk)


@pytest.mark.parametrize("perte", ["absente", "expiree", "inactif", "illisible"])
def test_every_lost_password_logs_an_error(
    admin: User, file_mot_de_passe: Any, caplog: pytest.LogCaptureFixture, perte: str
) -> None:
    compte = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    envoi_id = _en_file(admin, compte)
    if perte == "absente":
        EnvoiMotDePasse.objects.all().delete()
    elif perte == "expiree":
        EnvoiMotDePasse.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
    elif perte == "inactif":
        User.objects.filter(pk=compte.pk).update(is_active=False)
    else:
        EnvoiMotDePasse.objects.update(contenu=b"pas-un-jeton-fernet")
    with caplog.at_level(logging.INFO):
        assert tasks.envoyer_mot_de_passe_temporaire(envoi_id, compte.pk) is False
    assert len(_erreurs(caplog, compte)) == 1
    assert mail.outbox == []


def test_payload_carries_the_account_id_but_no_secret(admin: User, file_mot_de_passe: Any) -> None:
    compte = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    mdp, _ = services.reinitialiser_mot_de_passe(compte, par=admin, envoyer_courriel=True)
    assert mdp == ""
    envoi = EnvoiMotDePasse.objects.get(user=compte)
    file_mot_de_passe.assert_called_once_with(str(envoi.pk), compte.pk)


def test_queueing_waits_for_the_enclosing_commit(
    file_mot_de_passe: Any, django_capture_on_commit_callbacks: Any
) -> None:
    compte = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    with django_capture_on_commit_callbacks(execute=True) as rappels:
        with transaction.atomic():
            assert envois.mettre_en_file_mot_de_passe(compte, MDP, NatureEnvoi.BIENVENUE)
            file_mot_de_passe.assert_not_called()  # the worker could not see the row yet
    assert len(rappels) == 1
    file_mot_de_passe.assert_called_once()


def test_broker_failure_after_commit_logs_an_error_and_drops_the_row(
    file_mot_de_passe: Any,
    django_capture_on_commit_callbacks: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    file_mot_de_passe.side_effect = OSError("broker down")
    compte = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    with django_capture_on_commit_callbacks(execute=True), transaction.atomic():
        envois.mettre_en_file_mot_de_passe(compte, MDP, NatureEnvoi.BIENVENUE)
    assert not EnvoiMotDePasse.objects.exists()
    assert len(_erreurs(caplog, compte)) == 1


# --- N4 / N8 ---------------------------------------------------------------------------------


def test_failure_counter_is_atomic_under_concurrency() -> None:
    requete = type("R", (), {"META": {"REMOTE_ADDR": "203.0.113.77"}})()
    with _taux(echecs_connexion="1000/15min"):
        limite = EchecsConnexionParIpThrottle()

        def frapper() -> None:
            for _ in range(25):
                limite.enregistrer_echec(requete)

        fils = [threading.Thread(target=frapper) for _ in range(8)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        assert limite.nombre_echecs(requete) == 200


def test_cap_warning_logged_once_per_window(caplog: pytest.LogCaptureFixture) -> None:
    make_user(Role.AUDITEUR, username="ali", password=MDP)
    with (
        _taux(echecs_connexion="1/15min", connexion="100000/min"),
        caplog.at_level(logging.WARNING),
    ):
        _login(APIClient(), "ali", "faux")
        for _ in range(6):
            assert _login(APIClient(), "ali").status_code == 429
    plafonds = [r for r in caplog.records if "Plafond d'échecs atteint" in r.getMessage()]
    assert len(plafonds) == 1


# --- N6 --------------------------------------------------------------------------------------


@pytest.fixture
def agent_otp() -> User:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    compte.otp_connexion_actif = True
    compte.save()
    return compte


def test_login_codes_mailed_to_an_account_are_capped(agent_otp: User) -> None:
    plafond = settings.AUTH_CODES_CONNEXION_MAX
    assert plafond == 10
    with _taux(connexion="100000/min"):
        for _ in range(plafond + 3):
            assert _login(APIClient(), "awa").json()["etape"] == "OTP"
    assert len(mail.outbox) == plafond
    # The window over, codes are mailed again.
    User.objects.filter(pk=agent_otp.pk).update(
        codes_connexion_depuis=timezone.now() - timedelta(minutes=16)
    )
    _login(APIClient(), "awa")
    assert len(mail.outbox) == plafond + 1


def test_login_code_cap_does_not_depend_on_the_cache(agent_otp: User) -> None:
    for _ in range(settings.AUTH_CODES_CONNEXION_MAX + 2):
        cache.clear()
        tasks.envoyer_code_connexion(agent_otp.pk)
    assert len(mail.outbox) == settings.AUTH_CODES_CONNEXION_MAX


def test_superseded_login_code_is_refused_without_counting(agent_otp: User) -> None:
    client = APIClient()
    _login(client, "awa")
    ancien = auth_services.emettre_otp(agent_otp, ObjetOtp.LOGIN)
    nouveau = auth_services.emettre_otp(agent_otp, ObjetOtp.LOGIN)  # a second login
    if ancien == nouveau:  # one chance in a million
        return
    r = client.post(LOGIN_OTP, {"code": ancien}, format="json")
    assert r.status_code == 401
    agent_otp.refresh_from_db()
    assert agent_otp.echecs_connexion == 0
    actif = CodeOtp.objects.get(user=agent_otp, objet=ObjetOtp.LOGIN, utilise_le__isnull=True)
    assert actif.essais == 0
    assert client.post(LOGIN_OTP, {"code": nouveau}, format="json").status_code == 200


def test_superseded_reset_code_does_not_count_towards_the_cap() -> None:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    ancien = auth_services.emettre_otp(compte, ObjetOtp.RESET)
    nouveau = auth_services.emettre_otp(compte, ObjetOtp.RESET)
    if ancien == nouveau:
        return
    assert auth_services.reinitialiser_mot_de_passe("awa", ancien, NOUVEAU) is None
    compte.refresh_from_db()
    assert compte.echecs_reinitialisation == 0
    assert auth_services.reinitialiser_mot_de_passe("awa", nouveau, NOUVEAU) is not None


def test_a_wrong_code_still_counts(agent_otp: User) -> None:
    client = APIClient()
    _login(client, "awa")
    code = auth_services.emettre_otp(agent_otp, ObjetOtp.LOGIN)
    faux = f"{(int(code) + 1) % 1_000_000:06d}"
    assert client.post(LOGIN_OTP, {"code": faux}, format="json").status_code == 401
    agent_otp.refresh_from_db()
    assert agent_otp.echecs_connexion == 1


# --- N9 --------------------------------------------------------------------------------------


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend", EMAIL_HOST="relais.onea.bf"
)
def test_dummy_backend_never_counts_as_sending() -> None:
    assert auth_services.envoi_courriel_actif() is False


# --- D2 --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cas", ["inconnu", "desactive", "bloque", "sans_code", "mauvais_code", "code_remplace"]
)
def test_every_reset_refusal_costs_the_same_number_of_hashes(
    monkeypatch: pytest.MonkeyPatch, cas: str
) -> None:
    from django.contrib.auth import hashers

    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    saisi = "123456"
    if cas in ("mauvais_code", "code_remplace", "bloque", "desactive"):
        ancien = auth_services.emettre_otp(compte, ObjetOtp.RESET)
        actuel = auth_services.emettre_otp(compte, ObjetOtp.RESET)
        if ancien == actuel:
            return  # one chance in a million
        saisi = ancien if cas == "code_remplace" else f"{(int(actuel) + 1) % 1_000_000:06d}"
        if saisi == ancien and cas == "mauvais_code":
            saisi = f"{(int(actuel) + 2) % 1_000_000:06d}"
    if cas == "desactive":
        User.objects.filter(pk=compte.pk).update(is_active=False)
    if cas == "bloque":
        User.objects.filter(pk=compte.pk).update(
            echecs_reinitialisation=settings.AUTH_REINITIALISATION_ECHECS_MAX,
            echecs_reinitialisation_depuis=timezone.now(),
        )
    hachages = mock.Mock(wraps=hashers.make_password)
    verifications = mock.Mock(wraps=hashers.check_password)
    monkeypatch.setattr(auth_services, "make_password", hachages)
    monkeypatch.setattr(auth_services, "check_password", verifications)
    identifiant = "personne" if cas == "inconnu" else "awa"
    assert auth_services.reinitialiser_mot_de_passe(identifiant, saisi, NOUVEAU) is None
    attendu = 1 + auth_services.CODES_REMPLACES_VERIFIES
    assert hachages.call_count + verifications.call_count == attendu


# --- N3 leftover: the purge -------------------------------------------------------------------


def test_purge_logs_every_unsent_password(caplog: pytest.LogCaptureFixture) -> None:
    compte = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    envoi = EnvoiMotDePasse.objects.create(
        user=compte,
        nature=NatureEnvoi.BIENVENUE,
        contenu=b"x",
        expire_le=timezone.now() - timedelta(minutes=1),
    )
    with caplog.at_level(logging.INFO):
        assert envois.purger_envois_expires() == 1
    erreurs = _erreurs(caplog, compte)
    assert len(erreurs) == 1 and "purgé sans envoi" in erreurs[0] and str(envoi.pk) in erreurs[0]
