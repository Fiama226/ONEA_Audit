"""E2E seed command: refuses outside the throw-away e2e database, then logs in for real."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from apps.users.management.commands import creer_comptes_e2e
from apps.users.models import DelegationGestionComptes, User

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Onea-e2e-2026-test"


def _lancer(**options: object) -> str:
    sortie = StringIO()
    call_command("creer_comptes_e2e", stdout=sortie, **options)
    return sortie.getvalue()


@pytest.fixture
def base_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(connection.settings_dict, "NAME", "onea_e2e_1730000000")
    monkeypatch.setitem(connection.settings_dict, "HOST", "localhost")


@override_settings(DEBUG=True)
def test_refuse_une_base_qui_n_est_pas_jetable() -> None:
    with pytest.raises(CommandError, match="onea_e2e"):
        _lancer(mot_de_passe=MOT_DE_PASSE)
    assert not User.objects.filter(username="rai").exists()


@pytest.mark.usefixtures("base_e2e")
@override_settings(DEBUG=False)
def test_refuse_hors_debug() -> None:
    with pytest.raises(CommandError, match="DEBUG"):
        _lancer(mot_de_passe=MOT_DE_PASSE)
    assert not User.objects.exists()


@pytest.mark.usefixtures("base_e2e")
@override_settings(DEBUG=True)
def test_refuse_un_hote_de_base_distant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(connection.settings_dict, "HOST", "db.prod.example.org")
    with pytest.raises(CommandError, match="hôte"):
        _lancer(mot_de_passe=MOT_DE_PASSE)
    assert not User.objects.exists()


@pytest.mark.usefixtures("base_e2e")
@override_settings(DEBUG=True)
def test_refuse_sans_mot_de_passe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("E2E_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="Mot de passe"):
        _lancer()


@pytest.mark.usefixtures("base_e2e")
@override_settings(DEBUG=True)
def test_cree_des_comptes_utilisables_sans_changement_force_et_idempotents() -> None:
    _lancer(mot_de_passe=MOT_DE_PASSE)
    _lancer(mot_de_passe=MOT_DE_PASSE)
    assert User.objects.count() == len(creer_comptes_e2e.COMPTES_E2E)
    rai = User.objects.get(username="rai")
    assert rai.check_password(MOT_DE_PASSE)
    assert not rai.doit_changer_mot_de_passe
    assert rai.mot_de_passe_expire_le is None
    assert User.objects.get(username="audite1").direction_code == "DEX"
    assert DelegationGestionComptes.objects.filter(user__username="delegue1", creer=True).exists()
    assert DelegationGestionComptes.objects.count() == 1
