"""Temporary passwords for the active accounts left without one by the Keycloak switch."""

import logging
from datetime import timedelta
from io import StringIO

import pytest
from auditlog.models import LogEntry
from django.core.management import call_command
from django.utils import timezone

from apps.users.models import Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

MDP = "Mot-de-passe-solide-2026"


def _sans_mot_de_passe(username: str, **kwargs: object) -> User:
    compte = make_user(Role.AUDITEUR, username=username, **kwargs)
    compte.set_unusable_password()
    compte.save(update_fields=["password"])
    return compte


def _lancer(*args: str) -> tuple[str, str]:
    sortie, erreurs = StringIO(), StringIO()
    call_command("donner_mots_de_passe_temporaires", *args, stdout=sortie, stderr=erreurs)
    return sortie.getvalue(), erreurs.getvalue()


def test_gives_temp_passwords_to_accounts_without_one(caplog: pytest.LogCaptureFixture) -> None:
    rai = _sans_mot_de_passe("rai")
    audite = _sans_mot_de_passe("audite1")
    avec = make_user(Role.AUDITEUR, username="deja", password=MDP)
    inactif = _sans_mot_de_passe("parti", is_active=False)
    avant = timezone.now()
    with caplog.at_level(logging.DEBUG):
        sortie, erreurs = _lancer()
    lignes = dict(ligne.split("\t") for ligne in sortie.splitlines())
    assert set(lignes) == {"rai", "audite1"}
    for compte in (rai, audite):
        compte.refresh_from_db()
        mdp = lignes[compte.username]
        assert compte.check_password(mdp) and len(mdp) >= 16
        assert compte.doit_changer_mot_de_passe is True
        assert compte.mot_de_passe_expire_le is not None
        assert compte.mot_de_passe_expire_le >= avant + timedelta(hours=72)
        entree = LogEntry.objects.get_for_object(compte).latest("pk")
        assert entree.additional_data == {"action": "mot_de_passe_temporaire_migration"}
        assert "password" not in entree.changes_dict
        assert mdp not in caplog.text and mdp not in str(entree.changes)
    avec.refresh_from_db()
    assert avec.check_password(MDP) and not avec.doit_changer_mot_de_passe
    inactif.refresh_from_db()
    assert not inactif.has_usable_password()
    assert "2 mot(s) de passe" in erreurs
    securite = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any("nombre=2" in m for m in securite)


def test_second_run_changes_nothing() -> None:
    _sans_mot_de_passe("rai")
    _lancer()
    sortie, erreurs = _lancer()
    assert sortie == "" and "0 mot(s) de passe" in erreurs


def test_dry_run_lists_without_changing() -> None:
    rai = _sans_mot_de_passe("rai")
    sortie, erreurs = _lancer("--a-blanc")
    assert sortie.splitlines() == ["rai"]
    assert "aucune modification" in erreurs
    rai.refresh_from_db()
    assert not rai.has_usable_password()
