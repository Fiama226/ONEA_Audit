"""Fourth security round on the in-app authentication.

- a looser per-address cap counts EVERY refusal, of any kind and whatever the secret
  (``echecs_tous``, 120 per 15 min): it bounds the unauthenticated hashing one address can
  cause, and cannot be used as a password oracle;
- the dummy hashes that even out the cost of refusals run outside any transaction holding
  the account row: flooding someone's reset never delays that person's login;
- on reset, every refusal counts the same way on the per-address counter, at most 5 per
  typed identifier: the counter tells nothing about the identifier.
"""

from datetime import timedelta
from typing import Any, cast
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth import hashers
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import auth_services
from apps.users.auth_throttles import (
    EchecsConnexionParIpThrottle,
    EchecsReinitialisationParIpThrottle,
)
from apps.users.models import CodeOtp, ObjetOtp, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
LOGIN_OTP = "/api/v1/auth/login/otp/"
RESET = "/api/v1/auth/password/reset/"
MDP = "Mot-de-passe-solide-2026"
NOUVEAU = "Nouvelle-phrase-secrete-77"
LEVES = {
    "connexion": "100000/min",
    "connexion_code": "100000/min",
    "reinitialisation": "100000/min",
    "echecs_connexion": "100000/15min",
    "echecs_reinitialisation": "100000/hour",
    "echecs_tous": "100000/15min",
}


def _taux(**taux: str) -> Any:
    actuels = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    return override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {**actuels, **LEVES, **taux},
        }
    )


def _requete(adresse: str) -> Any:
    return type("R", (), {"META": {"REMOTE_ADDR": adresse}})()


def _login(adresse: str, identifiant: str, mot_de_passe: str = MDP) -> int:
    corps = {"identifiant": identifiant, "mot_de_passe": mot_de_passe}
    return APIClient(REMOTE_ADDR=adresse).post(LOGIN, corps, format="json").status_code


def _reset(adresse: str, identifiant: str, code: str = "123456") -> int:
    corps = {"identifiant": identifiant, "code": code, "nouveau_mot_de_passe": NOUVEAU}
    return APIClient(REMOTE_ADDR=adresse).post(RESET, corps, format="json").status_code


def _verrouille(username: str = "awa") -> User:
    compte = make_user(Role.AUDITEUR, username=username, email=f"{username}@onea.bf", password=MDP)
    compte.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    compte.save()
    return compte


# --- 1. every refusal, any kind ------------------------------------------------------------


def test_default_and_setting_of_the_all_refusals_cap() -> None:
    taux = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    assert taux["echecs_tous"] == "120/15min"


@pytest.mark.parametrize("mot_de_passe", [MDP, "pas-le-bon"])
def test_all_refusals_cap_trips_at_its_count_whatever_the_secret(mot_de_passe: str) -> None:
    _verrouille()
    with _taux(echecs_tous="3/15min"):
        for _ in range(3):
            assert _login("203.0.113.5", "awa", mot_de_passe) == 401
        # Same outcome after a right or a wrong password: no oracle.
        assert _login("203.0.113.5", "awa", mot_de_passe) == 429
        assert _login("203.0.113.5", "quelqu.un", "x") == 429
        assert _reset("203.0.113.5", "awa") == 429
        assert _login("203.0.113.6", "quelqu.un", "x") == 401  # another address


def test_all_refusals_cap_counts_every_kind_across_endpoints() -> None:
    make_user(Role.AUDITEUR, username="ali", password=MDP)
    _verrouille()
    with _taux(echecs_tous="4/15min"):
        assert _login("203.0.113.7", "ali", "faux") == 401  # wrong secret
        assert _login("203.0.113.7", "awa") == 401  # locked account
        assert _login("203.0.113.7", "personne", "x") == 401  # unknown
        assert _reset("203.0.113.7", "personne") == 400  # refused reset
        assert _login("203.0.113.7", "ali") == 429  # even the right password now


def test_admin_login_counts_in_the_all_refusals_cap() -> None:
    from django.test import Client

    make_user(Role.ADMIN, username="chef", password=MDP, is_staff=True)
    with _taux(echecs_tous="2/15min"):
        client = Client(REMOTE_ADDR="198.51.100.9")
        for _ in range(2):
            assert (
                client.post("/admin/login/", {"username": "x", "password": "y"}).status_code == 200
            )
        r = client.post("/admin/login/", {"username": "chef", "password": MDP})
        assert r.status_code == 200 and "_auth_user_id" not in client.session


# --- 1b. dummy hashes outside the row lock -------------------------------------------------


def _dans_une_transaction() -> bool:
    connexion = transaction.get_connection()
    return any(not getattr(b, "_from_testcase", False) for b in connexion.atomic_blocks)


@pytest.fixture
def bourrage(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, bool]]:
    """Every call of the dummy hashing: (count, inside a transaction of the code)."""
    appels: list[tuple[int, bool]] = []
    reel = auth_services._hachages_factices

    def espion(code: str, nombre: int) -> None:
        appels.append((nombre, _dans_une_transaction()))
        reel(code, nombre)

    monkeypatch.setattr(auth_services, "_hachages_factices", espion)
    return appels


@pytest.mark.parametrize("cas", ["desactive", "bloque", "sans_code", "mauvais_code"])
def test_reset_padding_runs_outside_the_account_lock(
    bourrage: list[tuple[int, bool]], cas: str
) -> None:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    code = auth_services.emettre_otp(compte, ObjetOtp.RESET)
    if cas == "desactive":
        User.objects.filter(pk=compte.pk).update(is_active=False)
    elif cas == "bloque":
        User.objects.filter(pk=compte.pk).update(
            echecs_reinitialisation=settings.AUTH_REINITIALISATION_ECHECS_MAX,
            echecs_reinitialisation_depuis=timezone.now(),
        )
    elif cas == "sans_code":
        CodeOtp.objects.filter(user=compte).delete()
    saisi = f"{(int(code) + 1) % 1_000_000:06d}"
    assert auth_services.reinitialiser_mot_de_passe("awa", saisi, NOUVEAU) is None
    payes = [(n, dedans) for n, dedans in bourrage if n]
    assert payes, "a refusal pays dummy hashes"
    assert not any(dedans for _, dedans in payes), payes


def test_login_code_padding_runs_outside_any_transaction(bourrage: list[tuple[int, bool]]) -> None:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    auth_services.emettre_otp(compte, ObjetOtp.LOGIN)
    assert auth_services.authentifier_code(compte.pk, "999999").etape is None
    assert all(not dedans for n, dedans in bourrage if n)


@pytest.mark.parametrize("parcours", ["reinitialisation", "connexion"])
def test_wrong_code_with_no_replaced_code_still_costs_four_hashes(
    monkeypatch: pytest.MonkeyPatch, parcours: str
) -> None:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    objet = ObjetOtp.RESET if parcours == "reinitialisation" else ObjetOtp.LOGIN
    code = auth_services.emettre_otp(compte, objet)  # one code, nothing replaced
    faux = f"{(int(code) + 1) % 1_000_000:06d}"
    hachages = mock.Mock(wraps=hashers.make_password)
    verifications = mock.Mock(wraps=hashers.check_password)
    monkeypatch.setattr(auth_services, "make_password", hachages)
    monkeypatch.setattr(auth_services, "check_password", verifications)
    if parcours == "reinitialisation":
        assert auth_services.reinitialiser_mot_de_passe("awa", faux, NOUVEAU) is None
    else:
        assert auth_services.authentifier_code(compte.pk, faux).etape is None
    assert hachages.call_count + verifications.call_count == auth_services.HACHAGES_PAR_REFUS == 4


# --- 2. reset: the counter tells nothing about the identifier ------------------------------


@pytest.mark.parametrize("cible", ["inconnu", "code_faux", "desactive", "bloque"])
def test_reset_counter_same_for_any_identifier(cible: str) -> None:
    """24 refusals on junk identifiers, then 6 on the target: the probe gets the same answer
    and the counter the same value, whatever the target is."""
    if cible != "inconnu":
        compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
        auth_services.emettre_otp(compte, ObjetOtp.RESET)
        if cible == "desactive":
            User.objects.filter(pk=compte.pk).update(is_active=False)
        elif cible == "bloque":
            User.objects.filter(pk=compte.pk).update(
                echecs_reinitialisation=settings.AUTH_REINITIALISATION_ECHECS_MAX,
                echecs_reinitialisation_depuis=timezone.now(),
            )
    adresse = "203.0.113.20"
    with _taux(echecs_reinitialisation="30/hour"):
        for i in range(24):
            assert _reset(adresse, f"rebut{i}") == 400
        for _ in range(6):
            assert _reset(adresse, "awa") == 400
        assert EchecsReinitialisationParIpThrottle().nombre_echecs(_requete(adresse)) == 29
        assert _reset(adresse, "sonde") == 400


# --- nits: the right code at the OTP step of a locked account ------------------------------


def test_right_code_on_a_locked_account_counts_like_a_wrong_one() -> None:
    compteurs = []
    for n, juste in enumerate((True, False)):
        compte = make_user(
            Role.AUDITEUR, username=f"agent{n}", email=f"agent{n}@onea.bf", password=MDP
        )
        compte.otp_connexion_actif = True
        compte.save()
        adresse = f"203.0.113.{30 + n}"
        with _taux():
            client = APIClient(REMOTE_ADDR=adresse)
            corps = {"identifiant": compte.username, "mot_de_passe": MDP}
            assert client.post(LOGIN, corps, format="json").json()["etape"] == "OTP"
            code = auth_services.emettre_otp(compte, ObjetOtp.LOGIN)
            User.objects.filter(pk=compte.pk).update(
                verrouille_jusqu_a=timezone.now() + timedelta(minutes=10)
            )
            saisi = code if juste else f"{(int(code) + 1) % 1_000_000:06d}"
            for _ in range(3):
                r = client.post(LOGIN_OTP, {"code": saisi}, format="json")
                assert r.status_code == 401
            compteurs.append(EchecsConnexionParIpThrottle().nombre_echecs(_requete(adresse)))
    assert compteurs == [1, 1]
