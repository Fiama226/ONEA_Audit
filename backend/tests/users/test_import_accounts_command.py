import csv
import io
import os
from io import StringIO
from pathlib import Path

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.users.keycloak_admin import KeycloakIndisponible
from apps.users.models import FichierMotsDePasse, Role, User

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


def test_commande_apply_exige_by(admin: User, tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="--by"):
        call_command("import_accounts", csv=_csv(tmp_path), apply=True)
    assert not User.objects.filter(username="cmd.user").exists()


def test_commande_fichier_trop_gros_refuse_avant_lecture(admin: User, tmp_path: Path) -> None:
    p = tmp_path / "gros.csv"
    p.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(CommandError, match="1 Mo"):
        call_command("import_accounts", csv=str(p))


def test_commande_apply_csv(admin: User, tmp_path: Path) -> None:
    out = StringIO()
    call_command("import_accounts", csv=_csv(tmp_path), apply=True, by=admin.username, stdout=out)
    compte = User.objects.get(username="cmd.user", origine="CSV")
    assert compte.doit_changer_mot_de_passe and compte.has_usable_password()
    assert "appliqué" in out.getvalue().lower()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["c@onea.bf"]
    assert not FichierMotsDePasse.objects.exists()


def test_commande_sans_courriel_indique_le_fichier(admin: User, tmp_path: Path) -> None:
    out = StringIO()
    call_command(
        "import_accounts",
        csv=_csv(tmp_path),
        apply=True,
        by=admin.username,
        sans_courriel=True,
        stdout=out,
    )
    fichier = FichierMotsDePasse.objects.get()
    assert fichier.cree_par_id == admin.pk
    assert f"/api/v1/user-accounts/import-passwords/{fichier.pk}/" in out.getvalue()
    assert mail.outbox == []


def test_commande_ecrit_le_fichier_local(admin: User, tmp_path: Path) -> None:
    cible = tmp_path / "mdp.csv"
    out = StringIO()
    call_command(
        "import_accounts",
        csv=_csv(tmp_path),
        apply=True,
        by=admin.username,
        sans_courriel=True,
        fichier_mots_de_passe=str(cible),
        stdout=out,
    )
    texte = cible.read_text(encoding="utf-8-sig")
    ligne = next(csv.DictReader(io.StringIO(texte), delimiter=";"))
    assert User.objects.get(username="cmd.user").check_password(ligne["mot_de_passe_temporaire"])
    assert ligne["mot_de_passe_temporaire"] not in out.getvalue()
    assert not FichierMotsDePasse.objects.exists()  # consumed: no second copy on the server


def test_commande_fichier_local_existant_refuse_avant_import(admin: User, tmp_path: Path) -> None:
    cible = tmp_path / "mdp.csv"
    cible.write_text("ancien", encoding="utf-8")
    with pytest.raises(CommandError, match="existe déjà"):
        call_command(
            "import_accounts",
            csv=_csv(tmp_path),
            apply=True,
            by=admin.username,
            fichier_mots_de_passe=str(cible),
        )
    assert cible.read_text(encoding="utf-8") == "ancien"
    assert not User.objects.filter(username="cmd.user").exists()


def test_commande_cible_non_inscriptible_refuse_avant_import(admin: User, tmp_path: Path) -> None:
    cible = tmp_path / "dossier-absent" / "mdp.csv"
    with pytest.raises(CommandError, match="Impossible de créer"):
        call_command(
            "import_accounts",
            csv=_csv(tmp_path),
            apply=True,
            by=admin.username,
            sans_courriel=True,
            fichier_mots_de_passe=str(cible),
        )
    assert not User.objects.filter(username="cmd.user").exists()
    assert not FichierMotsDePasse.objects.exists()


def test_commande_echec_ecriture_garde_la_copie_serveur(
    admin: User, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def disque_plein(descripteur: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", disque_plein)
    cible = tmp_path / "mdp.csv"
    with pytest.raises(CommandError, match="/api/v1/user-accounts/import-passwords/"):
        call_command(
            "import_accounts",
            csv=_csv(tmp_path),
            apply=True,
            by=admin.username,
            sans_courriel=True,
            fichier_mots_de_passe=str(cible),
            stdout=StringIO(),
        )
    assert not cible.exists()  # no half-written file left behind
    fichier = FichierMotsDePasse.objects.get()  # the server copy was not consumed
    assert fichier.nombre_comptes == 1
    assert User.objects.filter(username="cmd.user").exists()


def test_commande_fichier_local_rien_a_ecrire(admin: User, tmp_path: Path) -> None:
    cible = tmp_path / "mdp.csv"
    out = StringIO()
    call_command(
        "import_accounts",
        csv=_csv(tmp_path),
        apply=True,
        by=admin.username,
        fichier_mots_de_passe=str(cible),
        stdout=out,
    )
    assert len(mail.outbox) == 1
    assert "Aucun mot de passe à écrire" in out.getvalue()
    assert not cible.exists()


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
    call_command("import_accounts", keycloak=True, apply=True, by=admin.username, stdout=out)
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
