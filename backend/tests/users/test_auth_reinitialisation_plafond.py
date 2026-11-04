"""AUTH-02: a cumulative, database-backed cap on the wrong reset codes of an account.

Each new code used to bring 5 fresh guesses (10 codes a day: 50 guesses a day, forever).
Now the wrong codes of an account are counted in the database over a 24 h window whatever
the code, the IP or the cache; past the cap (``AUTH_REINITIALISATION_ECHECS_MAX``, 15 by
default) no code is issued nor accepted for that account until the window ends, behind the
same uniform answers. The reset by an administrator or a delegate stays the way out.
"""

import logging
import re
from datetime import timedelta
from typing import Any, cast
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.conf import settings
from django.contrib.auth import hashers
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import auth_services
from apps.users.models import CodeOtp, ObjetOtp, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

FORGOT = "/api/v1/auth/password/forgot/"
RESET = "/api/v1/auth/password/reset/"
MDP = "Mot-de-passe-solide-2026"
NOUVEAU = "Nouvelle-phrase-secrete-77"
CODE_INVALIDE = {"detail": "Code invalide ou expiré.", "errors": {}}


@pytest.fixture(autouse=True)
def _debits_leves() -> Any:
    """The per-IP and per-identifier throttles are not under test here."""
    actuels = cast(dict[str, str], settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    taux = {portee: "100000/min" for portee in actuels}
    with override_settings(
        REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": taux}
    ):
        yield


@pytest.fixture
def agent() -> User:
    return make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)


def _client(n: int) -> APIClient:
    """A different source address for every request: a distributed attack."""
    return APIClient(REMOTE_ADDR=f"198.51.{n // 250}.{n % 250 + 1}")


def _forgot(n: int, identifiant: str = "awa") -> Any:
    return _client(n).post(FORGOT, {"identifiant": identifiant}, format="json")


def _reset(n: int, code: str, identifiant: str = "awa") -> Any:
    return _client(n).post(
        RESET,
        {"identifiant": identifiant, "code": code, "nouveau_mot_de_passe": NOUVEAU},
        format="json",
    )


def _code_du_courriel() -> str:
    trouve = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert trouve is not None
    return trouve.group(1)


def _faux(code: str, i: int = 0) -> str:
    candidat = f"{(int(code) + 1 + i) % 1_000_000:06d}"
    assert candidat != code
    return candidat


def test_distributed_guessing_across_fresh_codes_is_capped(
    agent: User, caplog: pytest.LogCaptureFixture
) -> None:
    plafond = settings.AUTH_REINITIALISATION_ECHECS_MAX
    assert plafond == 15
    n = 0
    essais = 0
    # Fresh code after fresh code, every request from a new address.
    while essais < plafond:
        assert _forgot(n).status_code == 202
        n += 1
        code = _code_du_courriel()
        for i in range(auth_services.OTP_ESSAIS_MAX):
            if essais == plafond:
                break
            r = _reset(n, _faux(code, i))
            n += 1
            assert r.status_code == 400 and r.json() == CODE_INVALIDE
            essais += 1
    agent.refresh_from_db()
    assert agent.echecs_reinitialisation == plafond
    erreurs = [r for r in caplog.records if r.name == "onea.securite" and r.levelname == "ERROR"]
    assert len(erreurs) == 1 and f"compte={agent.pk}" in erreurs[0].getMessage()
    # The cap reached drops the pending code.
    assert not CodeOtp.objects.filter(user=agent, objet=ObjetOtp.RESET, utilise_le=None).exists()

    # Blocked: the answers do not change, but no code is issued...
    envoyes = len(mail.outbox)
    for _ in range(3):
        assert _forgot(n).status_code == 202
        n += 1
    assert len(mail.outbox) == envoyes
    # ... and none is accepted, not even a right one issued before the block.
    code = auth_services.emettre_otp(agent, ObjetOtp.RESET)
    r = _reset(n, code)
    assert r.status_code == 400 and r.json() == CODE_INVALIDE
    agent.refresh_from_db()
    assert agent.check_password(MDP)
    assert agent.echecs_reinitialisation == plafond  # a refusal while blocked adds nothing
    # Login and the administrator's reset are untouched.
    assert agent.verrouille_jusqu_a is None and agent.echecs_connexion == 0

    # The window over, the flow works again and a success clears the count.
    User.objects.filter(pk=agent.pk).update(
        echecs_reinitialisation_depuis=timezone.now() - timedelta(hours=24, seconds=1)
    )
    assert _forgot(n).status_code == 202
    assert len(mail.outbox) == envoyes + 1
    assert _reset(n + 1, _code_du_courriel()).status_code == 204
    agent.refresh_from_db()
    assert agent.check_password(NOUVEAU)
    assert agent.echecs_reinitialisation == 0


@override_settings(AUTH_REINITIALISATION_ECHECS_MAX=2)
def test_cap_is_configurable_and_counts_across_codes(agent: User) -> None:
    _forgot(0)
    assert _reset(1, _faux(_code_du_courriel())).status_code == 400
    _forgot(2)  # a new code does not restart the count
    code = _code_du_courriel()
    assert _reset(3, _faux(code)).status_code == 400
    assert _reset(4, code).json() == CODE_INVALIDE
    agent.refresh_from_db()
    assert agent.check_password(MDP)


def test_success_clears_the_count(agent: User) -> None:
    _forgot(0)
    code = _code_du_courriel()
    for i in range(3):
        _reset(1, _faux(code, i))
    agent.refresh_from_db()
    assert agent.echecs_reinitialisation == 3
    assert _reset(2, code).status_code == 204
    agent.refresh_from_db()
    assert agent.echecs_reinitialisation == 0 and agent.echecs_reinitialisation_depuis is None


def test_guess_without_a_pending_code_is_not_counted(agent: User) -> None:
    """Nothing could match: no count, so nobody blocks an account without it receiving codes."""
    for i in range(20):
        assert _reset(i, f"{i:06d}").json() == CODE_INVALIDE
    agent.refresh_from_db()
    assert agent.echecs_reinitialisation == 0


def test_blocked_refusal_costs_one_hash(agent: User, monkeypatch: pytest.MonkeyPatch) -> None:
    User.objects.filter(pk=agent.pk).update(
        echecs_reinitialisation=settings.AUTH_REINITIALISATION_ECHECS_MAX,
        echecs_reinitialisation_depuis=timezone.now(),
    )
    code = auth_services.emettre_otp(agent, ObjetOtp.RESET)
    hachages = mock.Mock(wraps=hashers.make_password)
    verifications = mock.Mock(wraps=hashers.check_password)
    monkeypatch.setattr(auth_services, "make_password", hachages)
    monkeypatch.setattr(auth_services, "check_password", verifications)
    assert auth_services.reinitialiser_mot_de_passe("awa", code, NOUVEAU) is None
    assert hachages.call_count + verifications.call_count == 1


def test_issuing_quota_survives_a_cache_flush(agent: User) -> None:
    """Database-backed: neither an eviction nor a cache outage lifts the 10 codes a day."""
    for n in range(auth_services.CODES_REINITIALISATION_MAX + 3):
        cache.clear()
        assert _forgot(n).status_code == 202
    assert len(mail.outbox) == auth_services.CODES_REINITIALISATION_MAX


def test_issuing_quota_does_not_depend_on_the_cache(agent: User) -> None:
    from redis.exceptions import ConnectionError as RedisConnectionError

    panne = mock.Mock(side_effect=RedisConnectionError("cache down"))
    with mock.patch.object(cache, "add", panne), mock.patch.object(cache, "incr", panne):
        resultats = [
            auth_services.quota_codes_reinitialisation(agent.pk)
            for _ in range(auth_services.CODES_REINITIALISATION_MAX + 2)
        ]
    # Fails closed past the cap, cache or not (the old cache counter let everything through).
    assert resultats == [True] * auth_services.CODES_REINITIALISATION_MAX + [False, False]
    agent.refresh_from_db()
    assert agent.codes_reinitialisation_emis == auth_services.CODES_REINITIALISATION_MAX
    assert auth_services.quota_codes_reinitialisation(agent.pk) is False


def test_counters_stay_out_of_the_audit_trail(agent: User) -> None:
    avant = LogEntry.objects.get_for_object(agent).count()
    _forgot(0)
    _reset(1, _faux(_code_du_courriel()))
    assert LogEntry.objects.get_for_object(agent).count() == avant


def test_blocked_account_is_logged_on_each_refusal(
    agent: User, caplog: pytest.LogCaptureFixture
) -> None:
    User.objects.filter(pk=agent.pk).update(
        echecs_reinitialisation=settings.AUTH_REINITIALISATION_ECHECS_MAX,
        echecs_reinitialisation_depuis=timezone.now(),
    )
    with caplog.at_level(logging.INFO, logger="onea.securite"):
        _forgot(0)
        _reset(1, "123456")
    messages = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any("bloqu" in m and f"compte={agent.pk}" in m for m in messages)
    assert sum("motif=bloque" in m for m in messages) == 1
