from uuid import UUID

import pytest

from apps.users.keycloak_admin import KeycloakIndisponible
from apps.users.models import OrigineCompte, Role, User
from apps.users.provisioning import (
    IDENTIFIANT_PRIS,
    claims_depuis_keycloak,
    importer_depuis_annuaire,
    rechercher_annuaire,
)

from ..conftest import FakeKeycloakAdmin
from ..factories import make_user


def _annuaire(fake: FakeKeycloakAdmin, username: str, roles: set[str] | None = None) -> UUID:
    return fake.add_user(
        username,
        roles=roles or {"AUDITEUR", "default-roles-onea"},
        email=f"{username}@onea.bf",
        emailVerified=True,
        firstName="Awa",
        lastName="Zongo",
        attributes={"direction": ["DAI"], "fonction": ["Auditrice"]},
    )


def test_claims_depuis_keycloak() -> None:
    rep = {
        "id": "6f9619ff-8b86-d011-b42d-00c04fc964ff",
        "username": "awa",
        "email": "a@b.bf",
        "emailVerified": True,
        "firstName": "Awa",
        "lastName": "Zongo",
        "attributes": {"direction": ["DAI"], "fonction": "Chef"},
    }
    c = claims_depuis_keycloak(rep, {"RAI"})
    assert c["sub"] == rep["id"] and c["preferred_username"] == "awa"
    assert c["direction"] == "DAI" and c["fonction"] == "Chef" and c["roles"] == ["RAI"]
    assert c["email_verified"] is True and c["given_name"] == "Awa"


def test_import_annuaire_cree_avec_role_effectif(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    kid = _annuaire(fake_keycloak, "awa", roles={"RAI", "offline_access"})
    rapport = importer_depuis_annuaire([kid], by=admin, dry_run=False)
    assert rapport.crees == ["awa"] and rapport.ignores == [] and not rapport.dry_run
    u = User.objects.get(username="awa")
    assert u.origine == OrigineCompte.ANNUAIRE and u.keycloak_id == kid and u.role == Role.RAI
    assert u.premiere_connexion_le is None and u.is_active and not u.has_usable_password()
    assert (u.direction_code, u.fonction) == ("DAI", "Auditrice")


def test_import_annuaire_a_blanc_n_ecrit_rien(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    kid = _annuaire(fake_keycloak, "awa")
    rapport = importer_depuis_annuaire([kid], by=admin, dry_run=True)
    assert rapport.crees == ["awa"] and rapport.dry_run
    assert not User.objects.filter(username="awa").exists()


def test_import_annuaire_met_a_jour_sans_toucher_is_active_ni_profil_local(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    kid = _annuaire(fake_keycloak, "awa", roles={"RAI"})
    local = make_user(
        Role.AUDITE,
        username="awa",
        keycloak_id=kid,
        is_active=False,
        profil_gere_localement=True,
        direction_code="X",
        fonction="Local",
        matricule="M-1",
    )
    rapport = importer_depuis_annuaire([kid], by=admin, dry_run=False)
    assert rapport.mis_a_jour == ["awa (rôle AUDITE → RAI)"] and rapport.crees == []
    local.refresh_from_db()
    assert local.role == Role.RAI and not local.is_active
    assert (local.direction_code, local.fonction, local.matricule) == ("X", "Local", "M-1")
    assert User.objects.filter(username__iexact="awa").count() == 1


def test_import_annuaire_lie_un_compte_csv_sans_premiere_connexion(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    kid = _annuaire(fake_keycloak, "awa")
    pre = make_user(
        Role.AUDITE, username="awa", keycloak_id=None, origine="CSV", role_provisoire=True
    )
    rapport = importer_depuis_annuaire([kid], by=admin, dry_run=False)
    assert rapport.mis_a_jour == ["awa (rôle AUDITE → AUDITEUR)"]
    pre.refresh_from_db()
    assert pre.keycloak_id == kid and not pre.role_provisoire and pre.role == Role.AUDITEUR
    assert pre.premiere_connexion_le is None and pre.origine == "CSV"


def test_import_annuaire_identifiant_pris(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    kid = _annuaire(fake_keycloak, "awa")
    make_user(Role.AUDITE, username="Awa", keycloak_id=UUID(int=5))
    rapport = importer_depuis_annuaire([kid], by=admin, dry_run=False)
    assert rapport.crees == [] and rapport.mis_a_jour == []
    assert [(i.identifiant, i.motif) for i in rapport.ignores] == [("awa", IDENTIFIANT_PRIS)]


def test_import_annuaire_tout_l_annuaire(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    for n in ("a1", "a2", "a3"):
        _annuaire(fake_keycloak, n)
    rapport = importer_depuis_annuaire(None, by=admin, dry_run=False)
    assert sorted(rapport.crees) == ["a1", "a2", "a3"]


def test_import_annuaire_compte_introuvable_ignore(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    rapport = importer_depuis_annuaire([UUID(int=42)], by=admin, dry_run=False)
    assert len(rapport.ignores) == 1 and rapport.crees == []


def test_import_annuaire_indisponible_leve(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    kid = _annuaire(fake_keycloak, "awa")
    fake_keycloak.fail_with(KeycloakIndisponible("Keycloak injoignable."), times=1)
    with pytest.raises(KeycloakIndisponible):
        importer_depuis_annuaire([kid], by=admin, dry_run=False)
    assert not User.objects.filter(username="awa").exists()


def test_rechercher_annuaire_signale_compte_existant(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    k1 = _annuaire(fake_keycloak, "awa")
    _annuaire(fake_keycloak, "awb")
    existing = make_user(Role.AUDITE, username="awa", keycloak_id=k1)
    entrees = {e.username: e for e in rechercher_annuaire("aw")}
    assert entrees["awa"].compte_id == existing.pk and entrees["awb"].compte_id is None
    assert entrees["awa"].keycloak_id == k1 and entrees["awa"].nom_complet == "Awa Zongo"
    assert (entrees["awa"].direction, entrees["awa"].fonction) == ("DAI", "Auditrice")


def test_import_annuaire_ignore_comptes_de_service_et_desactives(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    svc = fake_keycloak.add_user("service-account-onea-admin-sync", roles={"AUDITE"})
    fake_keycloak.users[svc]["serviceAccountClientId"] = "onea-admin-sync"
    off = _annuaire(fake_keycloak, "parti")
    fake_keycloak.users[off]["enabled"] = False
    _annuaire(fake_keycloak, "actif")
    rapport = importer_depuis_annuaire(None, by=admin, dry_run=False)
    assert rapport.crees == ["actif"]
    assert {i.identifiant for i in rapport.ignores} == {
        "service-account-onea-admin-sync",
        "parti",
    }
    interdits = ["parti", "service-account-onea-admin-sync"]
    assert not User.objects.filter(username__in=interdits).exists()


def test_import_annuaire_signale_les_identifiants_non_uuid(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    fake_keycloak.users[UUID(int=1)] = {"id": "pas-un-uuid", "username": "bizarre", "enabled": True}
    rapport = importer_depuis_annuaire(None, by=admin, dry_run=True)
    assert [i.identifiant for i in rapport.ignores] == ["bizarre"]


def test_import_annuaire_identifiant_affiche_tronque(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    fake_keycloak.users[UUID(int=1)] = {"id": "x" * 500, "username": "b\x1b[31m" + "z" * 500}
    rapport = importer_depuis_annuaire(None, by=admin, dry_run=True)
    echo = rapport.ignores[0].identifiant
    assert len(echo) <= 151 and "\x1b" not in echo
