"""Account-management delegation: an admin grants, per person, four rights.

A delegate can never touch an ADMIN account, another manager (delegate) or his own account,
never assign the ADMIN role, never read or change any delegation. The rules hold in the
services too (they are called from commands), and every right is re-read on each call.
"""

from collections.abc import Callable
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction, TypeEntite
from apps.users import services
from apps.users.delegation import ACTIONS, droits_effectifs, peut
from apps.users.models import DelegationGestionComptes, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/user-accounts/"
AUCUN: dict[str, bool] = dict.fromkeys(ACTIONS, False)
TOUS: dict[str, bool] = dict.fromkeys(ACTIONS, True)


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _deleguer(user: User, par: User, **droits: bool) -> DelegationGestionComptes:
    return services.definir_delegation(user, droits={**AUCUN, **droits}, par=par)


def _delegue(admin: User, **droits: bool) -> User:
    delegue = make_user(Role.RAI)
    _deleguer(delegue, admin, **droits)
    return delegue


# Each entry: right needed, then a call building its own fresh target -> status code.
Appel = Callable[[APIClient, User], int]


def _creer(client: APIClient, admin: User) -> int:
    n = User.objects.count()
    corps = {"username": f"nouveau{n}", "role": "AUDITEUR", "envoyer_courriel": False}
    return client.post(BASE, corps, format="json").status_code


def _reinitialiser(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR)
    url = f"{BASE}{cible.id}/reset-password/"
    return client.post(url, {"envoyer_courriel": False}, format="json").status_code


def _desactiver_otp(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR, otp_connexion_actif=True)
    return client.post(f"{BASE}{cible.id}/disable-otp/").status_code


def _changer_role(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR)
    return client.post(f"{BASE}{cible.id}/change-role/", {"role": "RAI"}, format="json").status_code


def _desactiver(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR)
    return client.post(f"{BASE}{cible.id}/deactivate/", {"motif": "x"}, format="json").status_code


def _reactiver(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR, is_active=False)
    return client.post(f"{BASE}{cible.id}/reactivate/").status_code


def _modifier_noms(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR)
    corps = {"first_name": "Mariam", "fonction": "Cheffe"}
    return client.patch(f"{BASE}{cible.id}/", corps, format="json").status_code


def _modifier_courriel(client: APIClient, admin: User) -> int:
    cible = make_user(Role.AUDITEUR)
    corps = {"email": f"nouvelle.{cible.pk}@onea.bf"}
    return client.patch(f"{BASE}{cible.id}/", corps, format="json").status_code


def _modifier_direction(client: APIClient, admin: User) -> int:
    if not Direction.objects.filter(code="DNEW").exists():
        Direction.objects.create(code="DNEW", libelle="DNEW", type=TypeEntite.DIRECTION)
    cible = make_user(Role.AUDITE)
    return client.patch(f"{BASE}{cible.id}/", {"direction_code": "DNEW"}, format="json").status_code


APPELS: list[tuple[str, Appel, int]] = [
    ("creer", _creer, 201),
    ("creer", _modifier_noms, 200),
    ("reinitialiser", _reinitialiser, 200),
    ("reinitialiser", _desactiver_otp, 200),
    ("reinitialiser", _modifier_courriel, 200),
    ("roles", _changer_role, 200),
    ("roles", _modifier_direction, 200),
    ("desactiver", _desactiver, 200),
    ("desactiver", _reactiver, 200),
]


def test_admin_can_do_all(admin: User) -> None:
    autre_admin = make_user(Role.ADMIN)
    agent = make_user(Role.AUDITEUR)
    for action in ACTIONS:
        assert peut(admin, action)
        assert peut(admin, action, agent)
        assert peut(admin, action, autre_admin)
    assert droits_effectifs(admin) == TOUS
    client = _client(admin)
    for _droit, appel, attendu in APPELS:
        assert appel(client, admin) == attendu, appel.__name__
    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}{agent.id}/delegation/").status_code == 200
    r = client.put(f"{BASE}{agent.id}/delegation/", {**AUCUN, "creer": True}, format="json")
    assert r.status_code == 200 and r.json()["creer"] is True


@pytest.mark.parametrize("droit", ACTIONS)
def test_delegate_limited_to_granted_actions(admin: User, droit: str) -> None:
    delegue = _delegue(admin, **{droit: True})
    assert droits_effectifs(delegue) == {**AUCUN, droit: True}
    agent = make_user(Role.AUDITEUR)
    for action in ACTIONS:
        assert peut(delegue, action, agent) is (action == droit)
    client = _client(delegue)
    # Any manager can read the accounts he acts on.
    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}{agent.id}/").status_code == 200
    for requis, appel, attendu in APPELS:
        statut = appel(client, admin)
        assert statut == (attendu if requis == droit else 403), (droit, appel.__name__)
    # Still admin-only: imports, directory, Keycloak resync.
    assert client.post(f"{BASE}{agent.id}/resync-profile/").status_code == 403
    assert client.get(BASE + "directory-search/?q=aud").status_code == 403


def test_delegate_actions_flags_follow_rights(admin: User) -> None:
    delegue = _delegue(admin, reinitialiser=True)
    agent = make_user(Role.AUDITEUR, otp_connexion_actif=True)
    actions = _client(delegue).get(f"{BASE}{agent.id}/").json()["actions"]
    assert actions == {
        "modifier_profil": False,
        "modifier_courriel": True,
        "modifier_direction": False,
        "changer_role": False,
        "desactiver": False,
        "reactiver": False,
        "resynchroniser_profil": False,
        "relancer_synchro_keycloak": False,
        "reinitialiser_mot_de_passe": True,
        "desactiver_otp": True,
    }
    sur_admin = _client(delegue).get(f"{BASE}{admin.id}/").json()["actions"]
    assert not any(sur_admin.values())


def test_user_without_rights_gets_403_everywhere(admin: User) -> None:
    sans_droit = make_user(Role.RAI)
    _deleguer(sans_droit, admin)  # an all-false delegation grants nothing
    client = _client(sans_droit)
    assert client.get(BASE).status_code == 403
    for _droit, appel, _attendu in APPELS:
        assert appel(client, admin) == 403, appel.__name__


def test_delegate_cannot_grant_self_rights(admin: User) -> None:
    delegue = _delegue(admin, creer=True)
    client = _client(delegue)
    assert client.get(f"{BASE}{delegue.id}/delegation/").status_code == 403
    r = client.put(f"{BASE}{delegue.id}/delegation/", TOUS, format="json")
    assert r.status_code == 403
    with pytest.raises(PermissionDenied):
        services.definir_delegation(delegue, droits=TOUS, par=delegue)
    assert droits_effectifs(delegue) == {**AUCUN, "creer": True}
    # Nor through his own account: role, profile, nothing on himself.
    assert (
        client.post(
            f"{BASE}{delegue.id}/change-role/", {"role": "ADMIN"}, format="json"
        ).status_code
        == 403
    )
    assert client.patch(f"{BASE}{delegue.id}/", {"fonction": "X"}, format="json").status_code == 403
    assert not peut(delegue, "creer", delegue)
    delegue.refresh_from_db()
    assert delegue.role == Role.RAI


def test_delegate_cannot_touch_admin_account(admin: User) -> None:
    autre_admin = make_user(Role.ADMIN, otp_connexion_actif=True)
    delegue = _delegue(admin, **TOUS)
    for action in ACTIONS:
        assert not peut(delegue, action, autre_admin)
    avant = User.objects.values().get(pk=autre_admin.pk)
    client = _client(delegue)
    cible = f"{BASE}{autre_admin.id}/"
    assert client.post(cible + "reset-password/", {"envoyer_courriel": False}).status_code == 403
    assert client.post(cible + "disable-otp/").status_code == 403
    assert client.post(cible + "change-role/", {"role": "AUDITE"}, format="json").status_code == 403
    assert client.post(cible + "deactivate/", {"motif": "x"}, format="json").status_code == 403
    assert client.patch(cible, {"first_name": "X"}, format="json").status_code == 403
    assert client.patch(cible, {"email": "pirate@onea.bf"}, format="json").status_code == 403
    for appel in (
        lambda: services.reinitialiser_mot_de_passe(autre_admin, par=delegue),
        lambda: services.desactiver_otp(autre_admin, par=delegue),
        lambda: services.changer_role(autre_admin, role=Role.AUDITE, par=delegue),
        lambda: services.desactiver(autre_admin, motif="x", by=delegue),
        lambda: services.modifier_profil(
            autre_admin, changes={"email": "pirate@onea.bf"}, by=delegue
        ),
    ):
        with pytest.raises(PermissionDenied):
            appel()
    assert User.objects.values().get(pk=autre_admin.pk) == avant
    admin_inactif = make_user(Role.ADMIN, is_active=False)
    assert client.post(f"{BASE}{admin_inactif.id}/reactivate/").status_code == 403
    with pytest.raises(PermissionDenied):
        services.reactiver(admin_inactif, by=delegue)


def test_delegate_cannot_touch_other_delegate(admin: User) -> None:
    """Another manager is out of reach: no lateral move to rights one was not given."""
    delegue = _delegue(admin, reinitialiser=True, desactiver=True)
    autre = _delegue(admin, roles=True)
    assert not peut(delegue, "reinitialiser", autre)
    client = _client(delegue)
    r = client.post(f"{BASE}{autre.id}/reset-password/", {"envoyer_courriel": False})
    assert r.status_code == 403
    assert client.post(f"{BASE}{autre.id}/deactivate/", {"motif": "x"}).status_code == 403
    with pytest.raises(PermissionDenied):
        services.reinitialiser_mot_de_passe(autre, par=delegue, envoyer_courriel=False)
    # Once revoked, the account is an ordinary one again.
    _deleguer(autre, admin)
    assert peut(delegue, "reinitialiser", autre)


def test_delegate_cannot_assign_admin_role(admin: User) -> None:
    delegue = _delegue(admin, creer=True, roles=True)
    client = _client(delegue)
    corps = {"username": "chef", "role": "ADMIN", "envoyer_courriel": False}
    assert client.post(BASE, corps, format="json").status_code == 403
    assert not User.objects.filter(username="chef").exists()
    with pytest.raises(PermissionDenied):
        services.creer_compte(
            donnees={"username": "chef", "role": "ADMIN"}, par=delegue, envoyer_courriel=False
        )
    agent = make_user(Role.AUDITEUR)
    r = client.post(f"{BASE}{agent.id}/change-role/", {"role": "ADMIN"}, format="json")
    assert r.status_code == 403
    with pytest.raises(PermissionDenied):
        services.changer_role(agent, role=Role.ADMIN, par=delegue)
    agent.refresh_from_db()
    assert agent.role == Role.AUDITEUR
    # Non-admin roles are fine.
    r = client.post(f"{BASE}{agent.id}/change-role/", {"role": "DG"}, format="json")
    assert r.status_code == 200 and r.json()["role"] == "DG"


def test_delegate_cannot_delegate(admin: User) -> None:
    delegue = _delegue(admin, **TOUS)
    agent = make_user(Role.AUDITEUR)
    client = _client(delegue)
    assert client.get(f"{BASE}{agent.id}/delegation/").status_code == 403
    assert client.put(f"{BASE}{agent.id}/delegation/", TOUS, format="json").status_code == 403
    with pytest.raises(PermissionDenied):
        services.definir_delegation(agent, droits={**AUCUN, "creer": True}, par=delegue)
    assert not DelegationGestionComptes.objects.filter(user=agent).exists()


def test_delegate_cannot_disable_self(admin: User) -> None:
    delegue = _delegue(admin, desactiver=True)
    client = _client(delegue)
    r = client.post(f"{BASE}{delegue.id}/deactivate/", {"motif": "x"}, format="json")
    assert r.status_code == 403
    with pytest.raises(PermissionDenied):
        services.desactiver(delegue, motif="x", by=delegue)
    delegue.refresh_from_db()
    assert delegue.is_active


def test_revoked_delegation_effective_immediately(admin: User) -> None:
    delegue = _delegue(admin, reinitialiser=True, desactiver=True)
    client = _client(delegue)  # same client and same user object throughout
    assert _reinitialiser(client, admin) == 200
    r = _client(admin).put(
        f"{BASE}{delegue.id}/delegation/", {**AUCUN, "desactiver": True}, format="json"
    )
    assert r.status_code == 200
    assert _reinitialiser(client, admin) == 403
    assert _desactiver(client, admin) == 200
    with pytest.raises(PermissionDenied):
        services.reinitialiser_mot_de_passe(make_user(), par=delegue, envoyer_courriel=False)
    _client(admin).put(f"{BASE}{delegue.id}/delegation/", AUCUN, format="json")
    assert _desactiver(client, admin) == 403
    assert client.get(BASE).status_code == 403


def test_disabled_delegate_has_no_rights(admin: User) -> None:
    delegue = _delegue(admin, **TOUS)
    services.desactiver(delegue, motif="Départ", by=admin)
    assert droits_effectifs(delegue) == AUCUN
    assert not peut(delegue, "creer")
    with pytest.raises(PermissionDenied):
        services.creer_compte(
            donnees={"username": "x", "role": "AUDITE"}, par=delegue, envoyer_courriel=False
        )


def test_delegation_changes_audited(admin: User) -> None:
    agent = make_user(Role.AUDITEUR)
    client = _client(admin)
    r = client.put(
        f"{BASE}{agent.id}/delegation/", {**AUCUN, "creer": True, "roles": True}, format="json"
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["creer"] is True and corps["roles"] is True
    assert corps["reinitialiser"] is False and corps["desactiver"] is False
    assert corps["accorde_par"]["id"] == admin.id
    assert corps["accorde_le"] is not None
    delegation = DelegationGestionComptes.objects.get(user=agent)
    entrees = list(LogEntry.objects.get_for_object(delegation).order_by("pk"))
    assert len(entrees) == 1
    assert entrees[0].actor == admin
    assert entrees[0].changes_dict["creer"][1] == "True"
    autre_admin = make_user(Role.ADMIN)
    r = _client(autre_admin).put(f"{BASE}{agent.id}/delegation/", AUCUN, format="json")
    assert r.status_code == 200 and r.json()["accorde_par"]["id"] == autre_admin.id
    entrees = list(LogEntry.objects.get_for_object(delegation).order_by("pk"))
    assert len(entrees) == 2
    assert entrees[1].actor == autre_admin
    assert set(entrees[1].changes_dict) >= {"creer", "roles", "accorde_par"}
    # A PUT that changes nothing writes nothing.
    _client(autre_admin).put(f"{BASE}{agent.id}/delegation/", AUCUN, format="json")
    assert LogEntry.objects.get_for_object(delegation).count() == 2


def test_delegation_get_defaults_and_validation(admin: User) -> None:
    agent = make_user(Role.AUDITEUR)
    client = _client(admin)
    r = client.get(f"{BASE}{agent.id}/delegation/")
    assert r.status_code == 200
    assert r.json() == {**AUCUN, "accorde_par": None, "accorde_le": None}
    # An all-false PUT on an account without delegation creates nothing.
    assert client.put(f"{BASE}{agent.id}/delegation/", AUCUN, format="json").status_code == 200
    assert not DelegationGestionComptes.objects.filter(user=agent).exists()
    r = client.put(f"{BASE}{agent.id}/delegation/", {"creer": True}, format="json")
    assert r.status_code == 400
    assert {"reinitialiser", "roles", "desactiver"} <= set(r.json()["errors"])
    with pytest.raises(ValueError):
        services.definir_delegation(agent, droits={"creer": True}, par=admin)
    with pytest.raises(ValueError):
        services.definir_delegation(agent, droits={**AUCUN, "admin": True}, par=admin)


def test_delegation_to_admin_rejected(admin: User) -> None:
    autre_admin = make_user(Role.ADMIN)
    r = _client(admin).put(f"{BASE}{autre_admin.id}/delegation/", TOUS, format="json")
    assert r.status_code == 422
    with pytest.raises(RegleMetierError):
        services.definir_delegation(autre_admin, droits=TOUS, par=admin)
    assert not DelegationGestionComptes.objects.filter(user=autre_admin).exists()


def test_promotion_to_admin_revokes_delegation(admin: User) -> None:
    delegue = _delegue(admin, **TOUS)
    services.changer_role(delegue, role=Role.ADMIN, par=admin)
    delegation = DelegationGestionComptes.objects.get(user=delegue)
    assert not any(getattr(delegation, a) for a in ACTIONS)
    # Back to a non-admin role: no right comes back by itself.
    services.changer_role(delegue, role=Role.RAI, par=admin)
    assert droits_effectifs(delegue) == AUCUN


def test_role_change_rules(admin: User) -> None:
    agent = make_user(Role.AUDITEUR)
    r = _client(admin).post(f"{BASE}{agent.id}/change-role/", {"role": "RAI"}, format="json")
    assert r.status_code == 200 and r.json()["role"] == "RAI"
    entree = LogEntry.objects.get_for_object(agent).order_by("pk").last()
    assert entree is not None and entree.actor == admin
    assert entree.changes_dict["role"] == ["AUDITEUR", "RAI"]
    assert (entree.additional_data or {}).get("action") == "changement_role"
    # Same role, invalid role, own role.
    assert _client(admin).post(f"{BASE}{agent.id}/change-role/", {"role": "RAI"}).status_code == 422
    assert (
        _client(admin).post(f"{BASE}{agent.id}/change-role/", {"role": "CHEF"}).status_code == 400
    )
    assert _client(admin).post(f"{BASE}{admin.id}/change-role/", {"role": "RAI"}).status_code == 422
    with pytest.raises(RegleMetierError):
        services.changer_role(admin, role=Role.RAI, par=admin)


def test_last_admin_cannot_be_demoted(admin: User) -> None:
    autre_admin = make_user(Role.ADMIN)
    services.changer_role(autre_admin, role=Role.RAI, par=admin)
    systeme = make_user(Role.ADMIN, is_active=False)  # inactive: does not count
    with pytest.raises(RegleMetierError):
        services.changer_role(admin, role=Role.RAI, par=systeme)
    admin.refresh_from_db()
    assert admin.role == Role.ADMIN


def test_me_exposes_effective_account_rights(admin: User) -> None:
    delegue = _delegue(admin, creer=True)
    assert _client(delegue).get("/api/v1/me/").json()["gestion_comptes"] == {
        **AUCUN,
        "creer": True,
    }
    assert _client(admin).get("/api/v1/me/").json()["gestion_comptes"] == TOUS
    agent = make_user(Role.AUDITEUR)
    assert _client(agent).get("/api/v1/me/").json()["gestion_comptes"] == AUCUN


def test_account_actions_throttled_per_user(admin: User) -> None:
    """Creation and resets send emails: a delegate cannot flood mailboxes."""
    delegue = _delegue(admin, creer=True, reinitialiser=True)
    base: dict[str, Any] = settings.REST_FRAMEWORK
    taux = {**base["DEFAULT_THROTTLE_RATES"], "gestion_comptes": "2/hour"}
    with override_settings(REST_FRAMEWORK={**base, "DEFAULT_THROTTLE_RATES": taux}):
        client = _client(delegue)
        assert _creer(client, admin) == 201
        assert _reinitialiser(client, admin) == 200
        assert _desactiver_otp(client, admin) == 429
        assert _creer(client, admin) == 429
        # Per user: the admin is not slowed down by the delegate.
        assert _creer(_client(admin), admin) == 201


def test_peut_rejects_unknown_action(admin: User) -> None:
    with pytest.raises(ValueError):
        peut(admin, "supprimer")  # type: ignore[arg-type]


def _routes_delegation(cible: int) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        ("get", f"{BASE}{cible}/delegation/", {}),
        ("put", f"{BASE}{cible}/delegation/", TOUS),
        ("post", f"{BASE}{cible}/change-role/", {"role": "RAI"}),
    ]


@pytest.mark.parametrize("role", ["RAI", "AUDITEUR", "AUDITE", "DG"])
def test_new_routes_closed_to_non_managers(role: str) -> None:
    cible = make_user(Role.AUDITEUR)
    client = _client(make_user(role))
    for methode, url, corps in _routes_delegation(cible.id):
        r = getattr(client, methode)(url, corps, format="json")
        assert r.status_code == 403, (methode, url)
    anonyme = APIClient()
    for methode, url, corps in _routes_delegation(cible.id):
        assert getattr(anonyme, methode)(url, corps, format="json").status_code == 401
