"""Identity of an account: username without "@", unique email, editable email and names.

Login resolves the exact username first, then the email: a new account must never be able
to shadow someone's email login, and an email change must keep addresses unique.
"""

from datetime import timedelta
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.users import services
from apps.users.models import CodeOtp, DelegationGestionComptes, ObjetOtp, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/user-accounts/"


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _creer(client: APIClient, **corps: Any) -> Any:
    return client.post(
        BASE, {"role": "AUDITEUR", "envoyer_courriel": False, **corps}, format="json"
    )


# --- Username / email collisions at creation ----------------------------------------------


@pytest.mark.parametrize("identifiant", ["awa@onea.bf", "awa@", "@awa"])
def test_username_with_at_sign_refused(admin: User, identifiant: str) -> None:
    r = _creer(_client(admin), username=identifiant)
    assert r.status_code == 422 and "username" in r.json()["errors"]
    assert not User.objects.filter(username=identifiant).exists()
    with pytest.raises(RegleMetierError) as exc:
        services.creer_compte(
            donnees={"username": identifiant, "role": "AUDITE"}, par=admin, envoyer_courriel=False
        )
    assert "username" in exc.value.errors


def test_email_equal_to_existing_username_refused(admin: User) -> None:
    # A legacy username that looks like an address (created before the "@" rule).
    make_user(Role.AUDITEUR, username="Chef@Onea.bf", email="chef.reel@onea.bf")
    r = _creer(_client(admin), username="nouveau", email="chef@onea.BF")
    assert r.status_code == 422 and "email" in r.json()["errors"]
    assert not User.objects.filter(username="nouveau").exists()


def test_username_equal_to_existing_email_refused(admin: User) -> None:
    # Only reachable for addresses without "@", e.g. a legacy local value.
    make_user(Role.AUDITEUR, username="awa", email="ADRESSE-LOCALE")
    with pytest.raises(RegleMetierError) as exc:
        services.creer_compte(
            donnees={"username": "adresse-locale", "role": "AUDITE"},
            par=admin,
            envoyer_courriel=False,
        )
    assert "username" in exc.value.errors


# --- Editing email and names --------------------------------------------------------------


def test_admin_edits_email_and_names(admin: User) -> None:
    cible = make_user(Role.AUDITEUR, email="ancienne@onea.bf")
    client = _client(admin)
    r = client.patch(
        f"{BASE}{cible.id}/",
        {"email": " Nouvelle@ONEA.bf ", "first_name": " Mariam ", "last_name": "Traoré"},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["email"] == "Nouvelle@onea.bf"
    assert r.json()["first_name"] == "Mariam" and r.json()["last_name"] == "Traoré"
    entree = LogEntry.objects.get_for_object(cible).filter(actor=admin).order_by("pk").last()
    assert entree is not None
    assert entree.changes_dict["email"] == ["ancienne@onea.bf", "Nouvelle@onea.bf"]


def test_email_change_keeps_uniqueness(admin: User) -> None:
    make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf")
    make_user(Role.AUDITEUR, username="legacy@onea.bf", email="autre@onea.bf")
    cible = make_user(Role.AUDITEUR, email="cible@onea.bf")
    client = _client(admin)
    for prise in ("AWA@onea.bf", "Legacy@Onea.bf"):
        r = client.patch(f"{BASE}{cible.id}/", {"email": prise}, format="json")
        assert r.status_code == 422 and "email" in r.json()["errors"], prise
    with pytest.raises(RegleMetierError):
        services.modifier_profil(cible, changes={"email": "awa@onea.bf"}, by=admin)
    cible.refresh_from_db()
    assert cible.email == "cible@onea.bf"
    # Its own address in another case is not a collision.
    r = client.patch(f"{BASE}{cible.id}/", {"email": "CIBLE@onea.bf"}, format="json")
    assert r.status_code == 200
    r = client.patch(f"{BASE}{cible.id}/", {"email": "pas-une-adresse"}, format="json")
    assert r.status_code == 400
    with pytest.raises(RegleMetierError):
        services.modifier_profil(cible, changes={"email": "pas-une-adresse"}, by=admin)


def test_email_change_drops_pending_codes(admin: User) -> None:
    cible = make_user(Role.AUDITEUR, email="ancienne@onea.bf")
    for objet in (ObjetOtp.RESET, ObjetOtp.LOGIN):
        CodeOtp.objects.create(
            user=cible,
            objet=objet,
            code_hash="x",
            expire_le=timezone.now() + timedelta(minutes=10),
        )
    services.modifier_profil(cible, changes={"first_name": "Awa"}, by=admin)
    assert CodeOtp.objects.filter(user=cible).count() == 2
    services.modifier_profil(cible, changes={"email": "nouvelle@onea.bf"}, by=admin)
    assert not CodeOtp.objects.filter(user=cible, utilise_le__isnull=True).exists()


def test_legacy_mixed_case_email_resent_unchanged_is_not_a_change(admin: User) -> None:
    """A legacy address stored with an uppercase domain, sent back as is: no right needed
    for the email, no write, pending codes kept."""
    createur = make_user(Role.RAI)
    services.definir_delegation(
        createur,
        droits={"creer": True, "reinitialiser": False, "roles": False, "desactiver": False},
        par=admin,
    )
    cible = make_user(Role.AUDITEUR, email="Awa.Kabore@ONEA.BF")
    CodeOtp.objects.create(
        user=cible,
        objet=ObjetOtp.RESET,
        code_hash="x",
        expire_le=timezone.now() + timedelta(minutes=10),
    )
    r = _client(createur).patch(
        f"{BASE}{cible.id}/",
        {"email": "Awa.Kabore@ONEA.BF", "fonction": "Comptable"},
        format="json",
    )
    assert r.status_code == 200
    cible.refresh_from_db()
    assert cible.email == "Awa.Kabore@ONEA.BF" and cible.fonction == "Comptable"
    assert CodeOtp.objects.filter(user=cible, utilise_le__isnull=True).count() == 1
    entree = LogEntry.objects.get_for_object(cible).order_by("pk").last()
    assert entree is not None and "email" not in entree.changes_dict


def test_email_cannot_be_cleared_while_login_code_on(admin: User) -> None:
    cible = make_user(Role.AUDITEUR, otp_connexion_actif=True)
    r = _client(admin).patch(f"{BASE}{cible.id}/", {"email": ""}, format="json")
    assert r.status_code == 422 and "email" in r.json()["errors"]
    sans_otp = make_user(Role.AUDITEUR)
    assert _client(admin).patch(f"{BASE}{sans_otp.id}/", {"email": ""}).status_code == 200


def test_edit_rights_per_field(admin: User) -> None:
    """Names and matricule follow `creer`; the email (recovery channel) `reinitialiser`;
    the direction (data scope of an audité) `roles`."""
    createur = make_user(Role.RAI)
    services.definir_delegation(
        createur,
        droits={"creer": True, "reinitialiser": False, "roles": False, "desactiver": False},
        par=admin,
    )
    cible = make_user(Role.AUDITE, email="cible@onea.bf", direction_code="DAI")
    client = _client(createur)
    r = client.patch(f"{BASE}{cible.id}/", {"last_name": "Zongo"}, format="json")
    assert r.status_code == 200
    r = client.patch(f"{BASE}{cible.id}/", {"email": "pirate@onea.bf"}, format="json")
    assert r.status_code == 403
    r = client.patch(f"{BASE}{cible.id}/", {"direction_code": "DAF"}, format="json")
    assert r.status_code == 403
    with pytest.raises(PermissionDenied):
        services.modifier_profil(cible, changes={"email": "pirate@onea.bf"}, by=createur)
    # Sending an unchanged value needs no extra right (a full form re-sent as is).
    r = client.patch(
        f"{BASE}{cible.id}/",
        {"email": "cible@onea.bf", "direction_code": "DAI", "fonction": "Comptable"},
        format="json",
    )
    assert r.status_code == 200
    cible.refresh_from_db()
    assert cible.email == "cible@onea.bf" and cible.fonction == "Comptable"
    assert DelegationGestionComptes.objects.filter(user=cible).count() == 0


@pytest.mark.parametrize(
    "champ,message",
    [
        ("role", "Utilisez l'action « Changer le rôle »."),
        ("username", "L'identifiant ne peut pas être modifié."),
        ("is_active", "Utilisez les actions « Désactiver » et « Réactiver »."),
        ("password", "Champ non modifiable."),
    ],
)
def test_patch_still_refuses_other_fields(admin: User, champ: str, message: str) -> None:
    cible = make_user(Role.AUDITEUR)
    avant = User.objects.values().get(pk=cible.pk)
    r = _client(admin).patch(f"{BASE}{cible.id}/", {champ: "x"}, format="json")
    assert r.status_code == 400 and r.json()["errors"] == {champ: [message]}
    assert User.objects.values().get(pk=cible.pk) == avant
