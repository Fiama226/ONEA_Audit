import logging
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.users import auth_services
from apps.users.auth_services import (
    emettre_otp,
    envoi_courriel_actif,
    generer_mot_de_passe_temporaire,
    purger_codes_expires,
    verifier_otp,
)
from apps.users.courriels import envoyer_bienvenue, envoyer_code
from apps.users.models import CodeOtp, ObjetOtp, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="otp.user", email="otp@onea.bf", password="x" * 14)


def test_code_is_six_digits_and_stored_hashed(user: User) -> None:
    code = emettre_otp(user, ObjetOtp.RESET)
    assert len(code) == 6 and code.isdigit()
    stocke = CodeOtp.objects.get(user=user, objet=ObjetOtp.RESET)
    assert stocke.code_hash != code
    assert code not in stocke.code_hash
    assert stocke.expire_le > timezone.now() + timedelta(minutes=9)


def test_code_valid_once(user: User) -> None:
    code = emettre_otp(user, ObjetOtp.LOGIN)
    assert verifier_otp(user, ObjetOtp.LOGIN, code) is True
    assert verifier_otp(user, ObjetOtp.LOGIN, code) is False


def test_wrong_code_counts_attempt_and_objet_is_isolated(user: User) -> None:
    code = emettre_otp(user, ObjetOtp.RESET)
    mauvais = "000000" if code != "000000" else "111111"
    assert verifier_otp(user, ObjetOtp.RESET, mauvais) is False
    assert CodeOtp.objects.get(user=user, objet=ObjetOtp.RESET).essais == 1
    assert verifier_otp(user, ObjetOtp.LOGIN, code) is False


def test_sixth_attempt_rejected_even_with_good_code(user: User) -> None:
    code = emettre_otp(user, ObjetOtp.RESET)
    mauvais = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert verifier_otp(user, ObjetOtp.RESET, mauvais) is False
    assert verifier_otp(user, ObjetOtp.RESET, code) is False


def test_fifth_attempt_with_good_code_is_accepted(user: User) -> None:
    code = emettre_otp(user, ObjetOtp.RESET)
    mauvais = "000000" if code != "000000" else "111111"
    for _ in range(4):
        verifier_otp(user, ObjetOtp.RESET, mauvais)
    assert verifier_otp(user, ObjetOtp.RESET, code) is True


def test_expired_after_10_minutes(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    code = emettre_otp(user, ObjetOtp.RESET)
    futur = timezone.now() + timedelta(minutes=10, seconds=1)
    monkeypatch.setattr(auth_services.timezone, "now", lambda: futur)
    assert verifier_otp(user, ObjetOtp.RESET, code) is False


def test_new_code_invalidates_old(user: User) -> None:
    ancien = emettre_otp(user, ObjetOtp.RESET)
    nouveau = emettre_otp(user, ObjetOtp.RESET)
    assert CodeOtp.objects.filter(user=user, objet=ObjetOtp.RESET, utilise_le=None).count() == 1
    if ancien != nouveau:
        assert verifier_otp(user, ObjetOtp.RESET, ancien) is False
    assert verifier_otp(user, ObjetOtp.RESET, nouveau) is True


def test_new_code_replaces_expired_unused_code(user: User) -> None:
    emettre_otp(user, ObjetOtp.RESET)
    CodeOtp.objects.filter(user=user).update(expire_le=timezone.now() - timedelta(hours=1))
    code = emettre_otp(user, ObjetOtp.RESET)
    assert verifier_otp(user, ObjetOtp.RESET, code) is True


def test_purge_removes_codes_expired_over_24h_only(user: User) -> None:
    now = timezone.now()
    for objet, delta in (
        (ObjetOtp.RESET, timedelta(hours=25)),
        (ObjetOtp.LOGIN, timedelta(hours=2)),
    ):
        emettre_otp(user, objet)
        CodeOtp.objects.filter(user=user, objet=objet).update(expire_le=now - delta)
    assert purger_codes_expires() == 1
    assert list(CodeOtp.objects.values_list("objet", flat=True)) == [ObjetOtp.LOGIN]


def test_code_never_in_logs(user: User, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        code = emettre_otp(user, ObjetOtp.RESET)
        verifier_otp(user, ObjetOtp.RESET, "999999")
        envoyer_code(user, code, ObjetOtp.RESET)
        verifier_otp(user, ObjetOtp.RESET, code)
    assert code not in caplog.text


def test_temporary_password_is_long_and_random() -> None:
    a, b = generer_mot_de_passe_temporaire(), generer_mot_de_passe_temporaire()
    assert len(a) >= 16 and a != b


def test_envoi_courriel_actif(settings) -> None:
    settings.EMAIL_HOST = "smtp.onea.bf"
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    assert envoi_courriel_actif() is True
    settings.EMAIL_HOST = ""
    assert envoi_courriel_actif() is False
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    assert envoi_courriel_actif() is True


def test_envoyer_bienvenue_contains_password_and_url(user: User, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        assert envoyer_bienvenue(user, "Mdp-Temporaire-123") is True
    corps = mail.outbox[0].body
    assert "Mdp-Temporaire-123" in corps and "otp.user" in corps
    assert "Mdp-Temporaire-123" not in caplog.text


def test_courriels_texte_sans_echappement_html(user: User) -> None:
    """Plain-text emails: « N'Diaye », never « N&#x27;Diaye » (final review M7)."""
    user.first_name, user.last_name = "Aïcha", "N'Diaye & Fils <x>"
    user.save()
    assert envoyer_bienvenue(user, "Mdp-Temporaire-123") is True
    assert envoyer_code(user, "123456", ObjetOtp.RESET) is True
    for message in mail.outbox:
        assert "N'Diaye & Fils <x>" in message.body
        assert "&#x27;" not in message.body and "&amp;" not in message.body


def test_envoyer_code_mentions_code_and_validity(user: User) -> None:
    assert envoyer_code(user, "123456", ObjetOtp.LOGIN) is True
    corps = mail.outbox[0].body
    assert "123456" in corps and "10 minutes" in corps


def test_envoi_without_email_returns_false(user: User) -> None:
    user.email = ""
    assert envoyer_code(user, "123456", ObjetOtp.RESET) is False
    assert mail.outbox == []


def test_second_emission_leaves_one_active_code_and_rejects_older(user: User) -> None:
    premier = emettre_otp(user, ObjetOtp.RESET)
    second = emettre_otp(user, ObjetOtp.RESET)
    assert CodeOtp.objects.filter(user=user, objet=ObjetOtp.RESET, utilise_le=None).count() == 1
    if premier != second:
        assert verifier_otp(user, ObjetOtp.RESET, premier) is False
    assert verifier_otp(user, ObjetOtp.RESET, second) is True


def test_emission_locks_user_row(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[bool] = []
    original = User.objects.select_for_update

    def espion(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        appels.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(type(User.objects), "select_for_update", lambda self, *a, **k: espion())
    emettre_otp(user, ObjetOtp.RESET)
    assert appels


def test_send_failure_logs_without_secrets(
    user: User, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("smtp down 654321 Mdp-Secret-XYZ")

    monkeypatch.setattr("apps.users.courriels.send_mail", boom)
    with caplog.at_level(logging.DEBUG):
        assert envoyer_code(user, "654321", ObjetOtp.RESET) is False
        assert envoyer_bienvenue(user, "Mdp-Secret-XYZ") is False
    assert "failed" in caplog.text
    assert "654321" not in caplog.text and "Mdp-Secret-XYZ" not in caplog.text
    for record in caplog.records:
        assert "654321" not in record.getMessage() and "Mdp-Secret-XYZ" not in record.getMessage()
        assert record.exc_info is None
