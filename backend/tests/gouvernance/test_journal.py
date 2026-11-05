"""Journal d'audit visible : changements de règles de gouvernance (ADMIN, RAI, DG en lecture)."""

import pytest
from rest_framework.test import APIClient

from apps.gouvernance import regles_gouvernance as rg
from apps.users.models import Role, User
from tests.connexion import connecter
from tests.factories import make_user

pytestmark = pytest.mark.django_db

URL = "/api/v1/audit-log/"


@pytest.fixture
def changement(admin: User) -> None:
    rg.modifier(rg.OBJECTIVITY, {"mode": "WARN"}, motif="Effectif réduit en 2026", by=admin)
    make_user(Role.AUDITEUR)  # une entrée d'audit sans rapport avec la gouvernance


def _client(user: User) -> APIClient:
    return connecter(APIClient(), user)


def test_governance_filter_shows_rule_changes_with_reason(changement: None, admin: User) -> None:
    corps = _client(admin).get(URL, {"categorie": "gouvernance"}).json()
    entrees = corps["results"]
    assert entrees and all(e["model"] == "gouvernance.reglegouvernance" for e in entrees)
    modification = next(e for e in entrees if e["action"] == "update")
    assert modification["motif"] == "Effectif réduit en 2026"
    assert modification["affaiblissement"] is True
    avant, apres = modification["changes"]["valeur"]
    assert "BLOCK" in avant and "WARN" in apres
    assert modification["actor"]["id"] == admin.pk


def test_dg_reads_only_governance_entries(changement: None) -> None:
    corps = _client(make_user(Role.DG)).get(URL).json()
    assert corps["results"]
    assert {e["model"] for e in corps["results"]} == {"gouvernance.reglegouvernance"}
    corps = _client(make_user(Role.DG)).get(URL, {"model": "users.user"}).json()
    assert corps["results"] == []


def test_rai_reads_everything(changement: None) -> None:
    corps = _client(make_user(Role.RAI)).get(URL).json()
    assert len({e["model"] for e in corps["results"]}) > 1


@pytest.mark.parametrize("role", [Role.AUDITEUR, Role.AUDITE])
def test_other_roles_are_refused(role: str) -> None:
    assert _client(make_user(role)).get(URL).status_code == 403


def test_masked_mode_still_shows_rule_changes(changement: None, admin: User) -> None:
    from apps.core.parametres import ContenuJournal, modifier_contenu_journal

    modifier_contenu_journal(ContenuJournal.MASQUE, by=admin)
    corps = _client(admin).get(URL, {"categorie": "gouvernance"}).json()
    modification = next(e for e in corps["results"] if e["action"] == "update")
    assert modification["motif"] == "Effectif réduit en 2026"
