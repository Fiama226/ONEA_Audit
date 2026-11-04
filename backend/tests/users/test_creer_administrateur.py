"""Bootstrap command: create the initial administrator, or reset its password."""

import logging
import re
from datetime import timedelta
from io import StringIO

import pytest
from auditlog.models import LogEntry
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from apps.users.models import OrigineCompte, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

ANCIEN = "Ancien-mot-de-passe-2026"
SANS_SMTP = {"EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": ""}


def _lancer(**options: object) -> tuple[str, str]:
    """Run the command; returns (stdout, the temporary password it printed)."""
    sortie = StringIO()
    call_command("creer_administrateur", stdout=sortie, **options)
    texte = sortie.getvalue()
    trouve = re.findall(r"Mot de passe temporaire : (\S+)", texte)
    assert len(trouve) == 1, texte
    return texte, trouve[0]


def _session_de(compte: User) -> str:
    session = SessionStore()
    session[SESSION_KEY] = str(compte.pk)
    session.create()
    assert session.session_key is not None
    return session.session_key


def test_creer_administrateur_creates_then_resets() -> None:
    avant = timezone.now()
    _, premier = _lancer(identifiant="admin.onea", courriel="admin@onea.bf")
    compte = User.objects.get(username="admin.onea")
    assert compte.role == Role.ADMIN and compte.is_active
    assert compte.email == "admin@onea.bf"
    assert compte.origine == OrigineCompte.ADMINISTRATION
    assert not compte.is_staff and not compte.is_superuser
    assert compte.check_password(premier) and len(premier) >= 16
    assert compte.doit_changer_mot_de_passe is True
    assert compte.mot_de_passe_expire_le is not None
    assert avant + timedelta(hours=72) <= compte.mot_de_passe_expire_le

    # Locked out with an open session: the second run resets, unlocks and logs out.
    compte.echecs_connexion = 5
    compte.verrouille_jusqu_a = timezone.now() + timedelta(minutes=15)
    compte.doit_changer_mot_de_passe = False
    compte.save(
        update_fields=["echecs_connexion", "verrouille_jusqu_a", "doit_changer_mot_de_passe"]
    )
    cle = _session_de(compte)
    texte, second = _lancer(identifiant="admin.onea")
    assert "réinitialisé" in texte
    compte.refresh_from_db()
    assert second != premier
    assert compte.check_password(second) and not compte.check_password(premier)
    assert compte.doit_changer_mot_de_passe is True
    assert compte.echecs_connexion == 0 and compte.verrouille_jusqu_a is None
    assert not Session.objects.filter(session_key=cle).exists()
    assert User.objects.filter(username__iexact="admin.onea").count() == 1


def test_reset_matches_identifier_case_insensitively() -> None:
    _lancer(identifiant="admin.onea", courriel="admin@onea.bf")
    _, mdp = _lancer(identifiant="ADMIN.onea")
    assert User.objects.get(username="admin.onea").check_password(mdp)


def test_refuses_existing_non_admin_account() -> None:
    agent = make_user(Role.AUDITEUR, username="agent", password=ANCIEN)
    with pytest.raises(CommandError, match="n'est pas un administrateur"):
        call_command("creer_administrateur", identifiant="agent", stdout=StringIO())
    agent.refresh_from_db()
    assert agent.role == Role.AUDITEUR
    assert agent.check_password(ANCIEN)


def test_refuses_disabled_admin() -> None:
    make_user(Role.ADMIN, username="ancien", is_active=False)
    with pytest.raises(CommandError, match="désactivé"):
        call_command("creer_administrateur", identifiant="ancien", stdout=StringIO())


@pytest.mark.parametrize(
    ("options", "fragment"),
    [
        ({"identifiant": "nouveau"}, "--courriel"),
        ({"identifiant": "nouveau", "courriel": "pas-une-adresse"}, "courriel valide"),
        ({"identifiant": "a@b", "courriel": "a@onea.bf"}, "@"),
        ({"identifiant": "", "courriel": "a@onea.bf"}, "obligatoire"),
        ({"identifiant": "nom avec espace", "courriel": "a@onea.bf"}, "Identifiant invalide"),
        ({"identifiant": "x/y", "courriel": "a@onea.bf"}, "Identifiant invalide"),
        ({"identifiant": "x" * 151, "courriel": "a@onea.bf"}, "150 caractères"),
        # ASCII only, like the creation form and the import (AUTH-11, final review M4).
        ({"identifiant": "ɡadmin", "courriel": "a@onea.bf"}, "lettres non accentuées"),
        ({"identifiant": "ｃhef", "courriel": "a@onea.bf"}, "lettres non accentuées"),
        ({"identifiant": "élodie", "courriel": "a@onea.bf"}, "lettres non accentuées"),
    ],
)
def test_creation_refused_on_invalid_input(options: dict[str, str], fragment: str) -> None:
    with pytest.raises(CommandError, match=re.escape(fragment)):
        call_command("creer_administrateur", stdout=StringIO(), **options)
    assert not User.objects.exists()


def test_creation_refuses_address_already_used() -> None:
    make_user(Role.AUDITE, username="awa", email="admin@onea.bf")
    with pytest.raises(CommandError, match="déjà utilisée"):
        call_command(
            "creer_administrateur", identifiant="admin", courriel="ADMIN@onea.bf", stdout=StringIO()
        )
    assert not User.objects.filter(username="admin").exists()


def test_password_never_logged_nor_audited(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        _, premier = _lancer(identifiant="admin", courriel="admin@onea.bf")
        _, second = _lancer(identifiant="admin")
    compte = User.objects.get(username="admin")
    for secret in (premier, second, compte.password):
        assert secret not in caplog.text
    entrees = list(LogEntry.objects.get_for_object(compte).order_by("pk"))
    assert [e.additional_data for e in entrees] == [
        {"action": "amorcage_administrateur"},
        {"action": "amorcage_administrateur"},
    ]
    for entree in entrees:
        assert "password" not in entree.changes_dict
        for secret in (premier, second):
            assert secret not in str(entree.changes)
    securite = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any(f"compte={compte.pk}" in m for m in securite)


def test_refuses_ambiguous_identifier() -> None:
    # Legacy data: two usernames differing only by case.
    make_user(Role.ADMIN, username="Chef")
    make_user(Role.ADMIN, username="chef")
    with pytest.raises(CommandError, match="Plusieurs comptes"):
        call_command("creer_administrateur", identifiant="CHEF", stdout=StringIO())


def _admin_avec_otp() -> User:
    compte = make_user(Role.ADMIN, username="chef", email="chef@onea.bf")
    compte.otp_connexion_actif = True
    compte.save(update_fields=["otp_connexion_actif"])
    return compte


@override_settings(**SANS_SMTP)
def test_reset_turns_login_code_off_without_smtp(caplog: pytest.LogCaptureFixture) -> None:
    compte = _admin_avec_otp()
    with caplog.at_level(logging.INFO):
        texte, _ = _lancer(identifiant="chef")
    compte.refresh_from_db()
    assert compte.otp_connexion_actif is False
    assert "Code de connexion par courriel désactivé" in texte
    entree = LogEntry.objects.get_for_object(compte).latest("pk")
    assert entree.additional_data == {"action": "amorcage_administrateur"}
    assert "otp_connexion_actif" in entree.changes_dict
    securite = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any(f"compte={compte.pk}" in m and "otp_desactive=True" in m for m in securite)


def test_reset_keeps_login_code_when_smtp_works() -> None:
    compte = _admin_avec_otp()
    _lancer(identifiant="chef")
    compte.refresh_from_db()
    assert compte.otp_connexion_actif is True


def test_reset_turns_login_code_off_on_request() -> None:
    compte = _admin_avec_otp()
    texte, mdp = _lancer(identifiant="chef", desactiver_otp=True)
    compte.refresh_from_db()
    assert compte.otp_connexion_actif is False and compte.check_password(mdp)
    assert "Code de connexion par courriel désactivé" in texte
