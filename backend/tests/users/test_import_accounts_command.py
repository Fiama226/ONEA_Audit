from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.users.keycloak_admin import KeycloakIndisponible
from apps.users.models import Role, User

from ..conftest import FakeKeycloakAdmin
from ..factories import make_user

CSV = "identifiant;email;role\ncmd.user;c@onea.bf;AUDITEUR\n"


def _csv(tmp_path: Path) -> str:
    p = tmp_path / "comptes.csv"
    p.write_text(CSV, encoding="utf-8")
    return str(p)


def test_commande_a_blanc_par_defaut(admin: User, tmp_path: Path) -> None:
    out = StringIO()
    call_command("import_accounts", csv=_csv(tmp_path), stdout=out)
    assert "à blanc" in out.getvalue().lower() and "cmd.user" in out.getvalue()
    assert not User.objects.filter(username="cmd.user").exists()


def test_commande_apply_csv(admin: User, tmp_path: Path) -> None:
    out = StringIO()
    call_command("import_accounts", csv=_csv(tmp_path), apply=True, by=admin.username, stdout=out)
    assert User.objects.filter(username="cmd.user", origine="CSV").exists()
    assert "appliqué" in out.getvalue().lower()


def test_commande_by_non_admin_refuse(admin: User, tmp_path: Path) -> None:
    simple = make_user(Role.AUDITEUR)
    with pytest.raises(CommandError):
        call_command("import_accounts", csv=_csv(tmp_path), apply=True, by=simple.username)
    inactif = make_user(Role.ADMIN, is_active=False)
    with pytest.raises(CommandError):
        call_command("import_accounts", csv=_csv(tmp_path), apply=True, by=inactif.username)
    with pytest.raises(CommandError):
        call_command("import_accounts", csv=_csv(tmp_path), apply=True, by="inconnu")
    assert not User.objects.filter(username="cmd.user").exists()


def test_commande_fichier_invalide(admin: User, tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_bytes(b"email\nx\n")
    with pytest.raises(CommandError, match="identifiant"):
        call_command("import_accounts", csv=str(p))
    with pytest.raises(CommandError):
        call_command("import_accounts", csv=str(tmp_path / "absent.csv"))


def test_commande_keycloak_apply(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    fake_keycloak.add_user("kc1", roles={"AUDITEUR"})
    out = StringIO()
    call_command("import_accounts", keycloak=True, apply=True, stdout=out)
    assert User.objects.filter(username="kc1", origine="ANNUAIRE").exists()
    call_command("import_accounts", keycloak=True, search="kc", stdout=out)


def test_commande_keycloak_indisponible_code_1(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    fake_keycloak.fail_with(KeycloakIndisponible("Keycloak injoignable."), times=1)
    with pytest.raises(CommandError, match="Keycloak injoignable.") as exc:
        call_command("import_accounts", keycloak=True)
    assert exc.value.returncode == 1


def test_commande_exige_une_source() -> None:
    with pytest.raises(CommandError):
        call_command("import_accounts")
