import csv
import io
import json
import logging
import re
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest import mock
from uuid import UUID

import pytest
from auditlog.models import LogEntry
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import Http404
from django.test import Client, override_settings
from django.utils import timezone

from apps.users import provisioning, tasks
from apps.users.delegation import acteur_systeme
from apps.users.models import FichierMotsDePasse, Role, User
from apps.users.provisioning import (
    CSV_COMPTE_EXISTANT,
    CSV_DOUBLON_FICHIER,
    CSV_EMAIL_INVALIDE,
    CSV_ROLE_ADMIN,
    CSV_TROP_DE_LIGNES,
    FichierImportInvalide,
    LigneIgnoree,
    RapportImport,
    importer_csv,
    lire_fichier_mots_de_passe,
)
from apps.users.services import (
    COURRIEL_PRIS,
    DIRECTION_INCONNUE,
    IDENTIFIANT_AROBASE,
    IDENTIFIANT_PRIS,
    MATRICULE_PRIS,
    ROLE_OBLIGATOIRE,
)
from apps.users.tasks import purger_codes

from ..factories import DirectionFactory, make_user

ENTETE = "identifiant;email;prenom;nom;matricule;direction;fonction;role\n"
SANS_SMTP = {"EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": ""}


def _importer(
    contenu: str | bytes, by: User, *, dry_run: bool = False, envoyer_courriel: bool = False
) -> RapportImport:
    brut = contenu.encode() if isinstance(contenu, str) else contenu
    return importer_csv(brut, by=by, dry_run=dry_run, envoyer_courriel=envoyer_courriel)


def _sans_fichier(rapport: RapportImport) -> RapportImport:
    return replace(rapport, fichier_mots_de_passe_id=None)


def _lignes_fichier(rapport: RapportImport, par: User) -> dict[str, dict[str, str]]:
    assert rapport.fichier_mots_de_passe_id is not None
    texte = lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=par)
    lecteur = csv.DictReader(io.StringIO(texte.lstrip("\ufeff")), delimiter=";")
    return {ligne["identifiant"]: ligne for ligne in lecteur}


def _mots_de_passe_des_courriels() -> dict[str, str]:
    trouves: dict[str, str] = {}
    for message in mail.outbox:
        m = re.search(r"Mot de passe temporaire : (\S+)", str(message.body))
        assert m, message.body
        trouves[message.to[0]] = m.group(1)
    return trouves


# --- Report semantics ------------------------------------------------------------------------


def test_csv_dry_run_n_ecrit_rien(admin: User) -> None:
    contenu = (
        b"identifiant;email;matricule;role\n"
        b"kabore.l;l.kabore@onea.bf;M-042;AUDITEUR\nchef;;;ADMIN\n"
    )
    rapport = _importer(contenu, admin, dry_run=True)
    assert rapport.crees == ["kabore.l"]
    assert rapport.ignores == [LigneIgnoree(3, "chef", CSV_ROLE_ADMIN)]
    assert rapport.fichier_mots_de_passe_id is None
    assert not User.objects.filter(username="kabore.l").exists()
    reel = _importer(contenu, admin)
    assert _sans_fichier(reel) == replace(rapport, dry_run=False)


def test_csv_role_admin_refuse(admin: User) -> None:
    rapport = _importer(ENTETE + "a;;;;;;;admin\nb;;;;;;;ADMIN\n", admin)
    assert rapport.crees == [] and len(rapport.ignores) == 2
    assert not User.objects.filter(role=Role.ADMIN).exclude(pk=admin.pk).exists()


def test_csv_cree_avec_les_bons_attributs(admin: User) -> None:
    DirectionFactory(code="DAI")  # type: ignore[no-untyped-call]
    _importer(ENTETE + "kabore.l;l@onea.bf;Landry;Kabore;M-1;DAI;Auditeur;RAI\n", admin)
    u = User.objects.get(username="kabore.l")
    assert (u.origine, u.role) == ("CSV", "RAI")
    assert u.is_active and not u.is_staff and not u.is_superuser
    assert (u.first_name, u.last_name, u.matricule) == ("Landry", "Kabore", "M-1")


def test_csv_rapport_identique(admin: User) -> None:
    make_user(username="existe", email="e@onea.bf")
    contenu = (
        ENTETE + "n1;;;;;;;AUDITE\nexiste;;;;;;;AUDITE\nn1;;;;;;;AUDITE\nn2;e@onea.bf;;;;;;DG\n"
    )
    a = _importer(contenu, admin, dry_run=True)
    b = _importer(contenu, admin)
    assert replace(_sans_fichier(b), dry_run=True) == a
    assert a.crees == ["n1"] and len(a.ignores) == 3


def test_csv_bom_et_virgule(admin: User) -> None:
    contenu = "\ufeffidentifiant,email,role\nvirg,v@onea.bf,DG\n".encode()
    rapport = _importer(contenu, admin)
    assert rapport.crees == ["virg"]
    assert User.objects.get(username="virg").role == Role.DG


def test_csv_doublon_dans_le_fichier(admin: User) -> None:
    rapport = _importer(
        ENTETE + "dup;;;;;;;AUDITE\nDUP;;;;;;;AUDITE\nautre;a@onea.bf;;;;;;AUDITE\n"
        "x;A@ONEA.BF;;;;;;AUDITE\n",
        admin,
    )
    assert rapport.crees == ["dup", "autre"]
    assert rapport.ignores == [
        LigneIgnoree(3, "DUP", CSV_DOUBLON_FICHIER),
        LigneIgnoree(5, "x", CSV_DOUBLON_FICHIER),
    ]


def test_csv_compte_existant_par_email(admin: User) -> None:
    make_user(username="deja", email="Deja@onea.bf")
    rapport = _importer(ENTETE + "nouveau;deja@ONEA.bf;;;;;;AUDITE\n", admin)
    assert rapport.ignores == [LigneIgnoree(2, "nouveau", COURRIEL_PRIS)]


def test_csv_compte_existant_par_identifiant(admin: User) -> None:
    make_user(username="Deja")
    rapport = _importer(ENTETE + "deja;;;;;;;AUDITE\n", admin)
    assert rapport.ignores == [LigneIgnoree(2, "deja", IDENTIFIANT_PRIS)]


def test_csv_matricule_deja_pris(admin: User) -> None:
    make_user(username="deja", matricule="M-9")
    rapport = _importer(
        ENTETE + "n1;;;;M-9;;;AUDITE\nn2;;;;M-8;;;AUDITE\nn3;;;;M-8;;;AUDITE\n", admin
    )
    assert rapport.crees == ["n2"]
    assert [i.motif for i in rapport.ignores] == [MATRICULE_PRIS, MATRICULE_PRIS]


def test_csv_direction_inconnue(admin: User) -> None:
    rapport = _importer(ENTETE + "n1;;;;;ZZZ;;AUDITE\n", admin)
    assert rapport.ignores == [LigneIgnoree(2, "n1", DIRECTION_INCONNUE)]


def test_csv_profil_fourni_est_enregistre(admin: User) -> None:
    DirectionFactory(code="DAI")  # type: ignore[no-untyped-call]
    _importer(ENTETE + "a;;;;;DAI;;AUDITE\nb;;;;;;Chef;AUDITE\nc;;;;;;;AUDITE\n", admin)
    profils = {
        u: (d, f)
        for u, d, f in User.objects.filter(username__in=["a", "b", "c"]).values_list(
            "username", "direction_code", "fonction"
        )
    }
    assert profils == {"a": ("DAI", ""), "b": ("", "Chef"), "c": ("", "")}


def test_csv_valeurs_invalides(admin: User) -> None:
    rapport = _importer(
        ENTETE + "bad name;;;;;;;AUDITE\nok1;pas-un-mail;;;;;;AUDITE\nok2;;;;;;;SUPER\n"
        f"ok3;;;;{'M' * 33};;;AUDITE\nok4;;;;;;{'f' * 129};AUDITE\n",
        admin,
    )
    assert rapport.crees == [] and len(rapport.ignores) == 5


@pytest.mark.parametrize(
    ("contenu", "message"),
    [
        (b"x" * (1024 * 1024 + 1), "Le fichier dépasse 1 Mo."),
        (("identifiant\n" + "u\n" * 301).encode(), CSV_TROP_DE_LIGNES),
        ("identifiant\né\n".encode("latin-1"), "Le fichier doit être encodé en UTF-8."),
        (b"email;role\nx;y\n", "En-tête invalide : colonne « identifiant » manquante."),
        (b"", "En-tête invalide : colonne « identifiant » manquante."),
    ],
)
def test_csv_fichier_invalide(admin: User, contenu: bytes, message: str) -> None:
    with pytest.raises(FichierImportInvalide) as exc:
        _importer(contenu, admin)
    assert exc.value.message == message


def test_csv_trop_gros_et_trop_long(admin: User) -> None:
    ok = ("identifiant;role\n" + "".join(f"u{i};AUDITE\n" for i in range(300))).encode()
    assert len(_importer(ok, admin, dry_run=True).crees) == 300
    with pytest.raises(FichierImportInvalide):
        _importer(ok + b"u300;AUDITE\n", admin, dry_run=True)


def test_csv_latin1_refuse(admin: User) -> None:
    with pytest.raises(FichierImportInvalide):
        _importer("identifiant;nom\nx;Zoé\n".encode("latin-1"), admin)


def test_csv_entete_sans_identifiant(admin: User) -> None:
    with pytest.raises(FichierImportInvalide):
        _importer(b"login;email\nx;y@z.bf\n", admin)


def test_csv_puis_premiere_connexion_sans_doublon(admin: User) -> None:
    DirectionFactory(code="DAI")  # type: ignore[no-untyped-call]
    rapport = _importer(ENTETE + "kabore.l;l@onea.bf;;;M-042;DAI;Local;AUDITEUR\n", admin)
    mot_de_passe = _lignes_fichier(rapport, admin)["kabore.l"]["mot_de_passe_temporaire"]
    pre = User.objects.get(username="kabore.l")
    assert pre.en_attente_connexion
    r = Client().post(
        "/api/v1/auth/login/",
        {"identifiant": "l@onea.bf", "mot_de_passe": mot_de_passe},
        content_type="application/json",
    )
    assert r.status_code == 200
    lie = User.objects.get(pk=pre.pk)
    assert lie.role == Role.AUDITEUR and lie.doit_changer_mot_de_passe
    assert lie.matricule == "M-042" and lie.direction_code == "DAI"  # imported profile kept
    assert lie.premiere_connexion_le is not None
    assert User.objects.filter(username__iexact="kabore.l").count() == 1


def test_csv_colonnes_is_staff_ignorees(admin: User) -> None:
    _importer(b"identifiant;is_staff;is_superuser;role\nx;true;1;AUDITEUR\n", admin)
    u = User.objects.get(username="x")
    assert not u.is_staff and not u.is_superuser


@pytest.mark.parametrize("valeur", ["=HYPERLINK(1)", "+1", "-2", "@cmd", "a\x07b", "a\x00b"])
def test_csv_caracteres_dangereux_refuses(admin: User, valeur: str) -> None:
    contenu = (
        "identifiant;prenom;nom;fonction;role\n"
        f"x;{valeur};;;AUDITE\ny;;{valeur};;AUDITE\nz;;;{valeur};AUDITE\nok;;;;AUDITE\n"
    )
    rapport = _importer(contenu, admin)
    assert rapport.crees == ["ok"] and len(rapport.ignores) == 3


def test_csv_prenom_compose_accepte(admin: User) -> None:
    rapport = _importer(b"identifiant;prenom;role\nx;Jean-Pierre;AUDITE\n", admin)
    assert rapport.crees == ["x"]


def test_csv_identifiant_affiche_tronque(admin: User) -> None:
    rapport = _importer(f"identifiant;role\n{'x' * 5000};AUDITE\n", admin, dry_run=True)
    assert len(rapport.ignores[0].identifiant) <= 151


def test_csv_conflit_a_l_ecriture_donne_le_bon_motif(
    admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: User, *a: object, **k: object) -> None:
        raise IntegrityError

    monkeypatch.setattr(User, "save", boom)
    rapport = _importer(ENTETE + "n1;;;;M-5;;;AUDITE\n", admin, dry_run=True)
    assert [i.motif for i in rapport.ignores] == [CSV_COMPTE_EXISTANT]


# --- Same validation as the account creation form -------------------------------------------


def test_csv_bad_rows_reported_and_others_created(admin: User) -> None:
    rapport = _importer(
        "identifiant;email;role\n"
        "sans.role;;\n"
        "a@b;;AUDITE\n"
        "mauvais;pas-une-adresse;AUDITE\n"
        "bon;bon@onea.bf;AUDITEUR\n",
        admin,
    )
    assert rapport.crees == ["bon"]
    assert rapport.ignores == [
        LigneIgnoree(2, "sans.role", ROLE_OBLIGATOIRE),
        LigneIgnoree(3, "a@b", IDENTIFIANT_AROBASE),
        LigneIgnoree(4, "mauvais", CSV_EMAIL_INVALIDE),
    ]
    assert User.objects.filter(username="bon").exists()


def test_csv_email_equal_to_existing_username_refused(admin: User) -> None:
    make_user(username="x.y@onea.bf")  # legacy account whose username is an address
    rapport = _importer("identifiant;email;role\nnouveau;X.Y@onea.bf;AUDITE\n", admin)
    assert rapport.ignores == [LigneIgnoree(2, "nouveau", COURRIEL_PRIS)]


# --- Temporary passwords and the one-time file ----------------------------------------------


def test_import_creates_accounts_with_temp_passwords(admin: User) -> None:
    avant = timezone.now()
    rapport = _importer("identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\nsali;;AUDITE\n", admin)
    assert rapport.crees == ["awa", "sali"]
    assert isinstance(rapport.fichier_mots_de_passe_id, UUID)
    assert mail.outbox == []
    lignes = _lignes_fichier(rapport, admin)
    assert set(lignes) == {"awa", "sali"}
    for identifiant, ligne in lignes.items():
        u = User.objects.get(username=identifiant)
        assert u.has_usable_password() and u.check_password(ligne["mot_de_passe_temporaire"])
        assert len(ligne["mot_de_passe_temporaire"]) >= 16
        assert u.doit_changer_mot_de_passe is True
        assert u.mot_de_passe_expire_le is not None
        assert (
            avant + timedelta(hours=72)
            <= u.mot_de_passe_expire_le
            <= timezone.now() + timedelta(hours=72)
        )
    assert lignes["awa"]["courriel"] == "awa@onea.bf"
    assert lignes["awa"]["mot_de_passe_temporaire"] != lignes["sali"]["mot_de_passe_temporaire"]


def test_import_emails_when_active(admin: User) -> None:
    rapport = _importer(
        "identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\nsali;;AUDITE\n",
        admin,
        envoyer_courriel=True,
    )
    envoyes = _mots_de_passe_des_courriels()
    assert set(envoyes) == {"awa@onea.bf"}
    assert User.objects.get(username="awa").check_password(envoyes["awa@onea.bf"])
    # Only the account without an address goes to the file.
    assert set(_lignes_fichier(rapport, admin)) == {"sali"}


def test_import_all_emailed_stores_no_file(admin: User) -> None:
    rapport = _importer(
        "identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\n", admin, envoyer_courriel=True
    )
    assert len(mail.outbox) == 1
    assert rapport.fichier_mots_de_passe_id is None
    assert not FichierMotsDePasse.objects.exists()


@override_settings(**SANS_SMTP)
def test_import_without_smtp_puts_everyone_in_the_file(admin: User) -> None:
    rapport = _importer(
        "identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\n", admin, envoyer_courriel=True
    )
    assert mail.outbox == []
    assert set(_lignes_fichier(rapport, admin)) == {"awa"}


def _file_en_panne(side_effect: Any) -> Any:
    """The broker cannot take the welcome-email tasks (AUTH-01: the worker sends them)."""
    return mock.patch.object(
        tasks.envoyer_mot_de_passe_temporaire, "delay", side_effect=side_effect
    )


def test_import_queue_failure_goes_to_the_file(admin: User) -> None:
    with _file_en_panne(side_effect=OSError("broker down")):
        rapport = _importer(
            "identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\n", admin, envoyer_courriel=True
        )
    assert set(_lignes_fichier(rapport, admin)) == {"awa"}


def test_dry_run_stores_nothing_and_sends_nothing(admin: User) -> None:
    rapport = _importer(
        "identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\nsali;;AUDITE\n",
        admin,
        dry_run=True,
        envoyer_courriel=True,
    )
    assert rapport.crees == ["awa", "sali"] and rapport.fichier_mots_de_passe_id is None
    assert not FichierMotsDePasse.objects.exists()
    assert not User.objects.filter(username__in=["awa", "sali"]).exists()
    assert mail.outbox == []


def test_real_import_needs_an_actor(db: None) -> None:
    with pytest.raises(ValueError):
        importer_csv(
            b"identifiant;role\nx;AUDITE\n", by=None, dry_run=False, envoyer_courriel=False
        )
    assert not User.objects.exists()


def test_password_file_read_once_and_owner_only(admin: User) -> None:
    autre = make_user(Role.ADMIN)
    rapport = _importer("identifiant;role\nawa;AUDITE\n", admin)
    assert rapport.fichier_mots_de_passe_id is not None
    with pytest.raises(PermissionDenied):
        lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=autre)
    assert "awa" in lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=admin)
    with pytest.raises(Http404):
        lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=admin)
    assert not FichierMotsDePasse.objects.exists()


def test_password_file_neutralises_spreadsheet_formulas(admin: User) -> None:
    rapport = _importer("identifiant;role\n-moins;AUDITE\n+plus;AUDITE\n", admin)
    assert rapport.fichier_mots_de_passe_id is not None
    texte = lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=admin)
    assert "\n'-moins;" in texte and "\n'+plus;" in texte


def test_password_file_expires_after_24h(admin: User) -> None:
    rapport = _importer("identifiant;role\nawa;AUDITE\n", admin)
    fichier = FichierMotsDePasse.objects.get()
    assert (
        timezone.now() + timedelta(hours=23)
        < fichier.expire_le
        <= timezone.now() + timedelta(hours=24)
    )
    # Past its expiry: never served, destroyed on the attempt.
    FichierMotsDePasse.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
    assert rapport.fichier_mots_de_passe_id is not None
    with pytest.raises(Http404):
        lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=admin)
    assert not FichierMotsDePasse.objects.exists()


def test_daily_purge_removes_expired_password_files(admin: User) -> None:
    perime = _importer("identifiant;role\nmoussa;AUDITE\n", admin).fichier_mots_de_passe_id
    valide = _importer("identifiant;role\nissouf;AUDITE\n", admin).fichier_mots_de_passe_id
    assert perime is not None and valide is not None
    FichierMotsDePasse.objects.filter(pk=perime).update(
        expire_le=timezone.now() - timedelta(minutes=1)
    )
    purger_codes()
    assert list(FichierMotsDePasse.objects.values_list("pk", flat=True)) == [valide]


def test_password_never_in_audit_or_logs(admin: User, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        rapport = _importer(
            "identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\nsali;;AUDITE\n",
            admin,
            envoyer_courriel=True,
        )
        secrets = list(_mots_de_passe_des_courriels().values())
        brut_stocke = bytes(FichierMotsDePasse.objects.get().contenu)
        secrets += [
            ligne["mot_de_passe_temporaire"] for ligne in _lignes_fichier(rapport, admin).values()
        ]
    assert len(secrets) == 2
    comptes = list(User.objects.filter(username__in=["awa", "sali"]))
    entrees = LogEntry.objects.filter(object_pk__in=[str(c.pk) for c in comptes])
    assert entrees.count() == 2
    for entree in entrees:
        assert entree.actor_id == admin.pk
        assert "password" not in entree.changes_dict
        assert entree.additional_data == {"action": "creation_compte"}
        brut = json.dumps(
            [entree.changes, entree.additional_data, entree.serialized_data], default=str
        )
        for secret in secrets:
            assert secret not in brut
    for secret in secrets:
        assert secret not in caplog.text
        assert secret.encode() not in brut_stocke  # stored encrypted
    for compte in comptes:
        assert compte.password not in caplog.text
    securite = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any(f"par={admin.pk}" in m and "comptes_crees=2" in m for m in securite)


# --- No password lost: file first, emails after, stop at the first SMTP failure -----------

TROIS = (
    "identifiant;email;role\n"
    "awa;awa@onea.bf;AUDITEUR\nsali;sali@onea.bf;AUDITE\nmoussa;moussa@onea.bf;AUDITE\n"
)


def _verifier_mots_de_passe(lignes: dict[str, dict[str, str]]) -> None:
    for identifiant, ligne in lignes.items():
        compte = User.objects.get(username=identifiant)
        assert compte.check_password(ligne["mot_de_passe_temporaire"])


def test_crash_between_commit_and_send_keeps_every_password(
    admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    def panne(*args: object, **kwargs: object) -> set[int]:
        raise RuntimeError("worker killed")

    monkeypatch.setattr(provisioning, "_envoyer_courriels", panne)
    with pytest.raises(RuntimeError):
        _importer(TROIS, admin, envoyer_courriel=True)
    # The accounts are committed, and so is the file with all their passwords.
    assert User.objects.filter(username__in=["awa", "sali", "moussa"]).count() == 3
    fichier = FichierMotsDePasse.objects.get()
    assert fichier.cree_par_id == admin.pk and fichier.nombre_comptes == 3
    texte = lire_fichier_mots_de_passe(fichier.pk, par=admin)
    lignes = {
        ligne["identifiant"]: ligne
        for ligne in csv.DictReader(io.StringIO(texte.lstrip("\ufeff")), delimiter=";")
    }
    assert set(lignes) == {"awa", "sali", "moussa"}
    _verifier_mots_de_passe(lignes)


def test_broker_down_stops_at_first_failure(admin: User) -> None:
    with _file_en_panne(side_effect=OSError("broker down")) as envoi:
        rapport = _importer(TROIS, admin, envoyer_courriel=True)
    assert envoi.call_count == 1  # no waiting for a timeout per remaining account
    lignes = _lignes_fichier(rapport, admin)
    assert set(lignes) == {"awa", "sali", "moussa"}
    _verifier_mots_de_passe(lignes)


def test_queue_failure_midway_keeps_the_unqueued_ones(admin: User) -> None:
    with _file_en_panne(side_effect=[None, OSError("broker down")]) as envoi:
        rapport = _importer(TROIS, admin, envoyer_courriel=True)
    assert envoi.call_count == 2
    lignes = _lignes_fichier(rapport, admin)
    assert set(lignes) == {"sali", "moussa"}  # awa's email is queued for the worker
    _verifier_mots_de_passe(lignes)


def test_email_time_budget_spent_keeps_the_rest(
    admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provisioning, "DUREE_MAX_ENVOIS", timedelta(0))
    rapport = _importer(TROIS, admin, envoyer_courriel=True)
    assert mail.outbox == []
    assert set(_lignes_fichier(rapport, admin)) == {"awa", "sali", "moussa"}


def test_file_cut_down_after_emails(admin: User) -> None:
    rapport = _importer(TROIS + "sans.adresse;;DG\n", admin, envoyer_courriel=True)
    assert len(mail.outbox) == 3
    fichier = FichierMotsDePasse.objects.get()
    assert fichier.pk == rapport.fichier_mots_de_passe_id and fichier.nombre_comptes == 1
    assert set(_lignes_fichier(rapport, admin)) == {"sans.adresse"}


# --- The importer's right is re-checked under lock ---------------------------------------


def test_import_refused_to_an_inactive_admin(db: None) -> None:
    ancien = make_user(Role.ADMIN, is_active=False)
    with pytest.raises(PermissionDenied):
        _importer("identifiant;role\nx;AUDITE\n", ancien)
    assert not User.objects.filter(username="x").exists()
    assert not FichierMotsDePasse.objects.exists()


@pytest.mark.parametrize("role", ["RAI", "AUDITEUR", "AUDITE", "DG"])
def test_import_refused_to_a_non_admin(db: None, role: str) -> None:
    with pytest.raises(PermissionDenied):
        _importer("identifiant;role\nx;AUDITE\n", make_user(role))
    assert not User.objects.filter(username="x").exists()


def test_import_by_system_actor_inside_its_block(db: None) -> None:
    systeme = make_user(Role.ADMIN, is_active=False)
    with acteur_systeme(systeme):
        rapport = _importer("identifiant;role\nx;AUDITE\n", systeme)
    assert rapport.crees == ["x"]


def test_identifiant_rejete_affiche_tronque_sans_caractere_de_controle(admin: User) -> None:
    identifiant = "b\x1b[31m" + "z" * 500
    rapport = _importer(f"identifiant;role\n{identifiant};AUDITEUR\n", admin, dry_run=True)
    echo = rapport.ignores[0].identifiant
    assert len(echo) <= 151 and "\x1b" not in echo
