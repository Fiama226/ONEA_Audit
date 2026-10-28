from dataclasses import replace

import pytest

from apps.users.models import Role, User
from apps.users.provisioning import (
    CSV_COMPTE_EXISTANT,
    CSV_DOUBLON_FICHIER,
    CSV_ROLE_ADMIN,
    FichierImportInvalide,
    LigneIgnoree,
    importer_csv,
)
from apps.users.services import DIRECTION_INCONNUE, MATRICULE_PRIS

from ..factories import DirectionFactory, make_user
from .test_account_oidc_sync import _login
from .test_oidc import claims

ENTETE = "identifiant;email;prenom;nom;matricule;direction;fonction;role\n"


def test_csv_dry_run_n_ecrit_rien(admin: User) -> None:
    contenu = (
        b"identifiant;email;matricule;role\n"
        b"kabore.l;l.kabore@onea.bf;M-042;AUDITEUR\nchef;;;ADMIN\n"
    )
    rapport = importer_csv(contenu, by=admin, dry_run=True)
    assert rapport.crees == ["kabore.l"]
    assert rapport.ignores == [LigneIgnoree(3, "chef", CSV_ROLE_ADMIN)]
    assert not User.objects.filter(username="kabore.l").exists()
    assert importer_csv(contenu, by=admin, dry_run=False) == replace(rapport, dry_run=False)


def test_csv_role_admin_refuse(admin: User) -> None:
    rapport = importer_csv(
        (ENTETE + "a;;;;;;;admin\nb;;;;;;;ADMIN\n").encode(), by=admin, dry_run=False
    )
    assert rapport.crees == [] and len(rapport.ignores) == 2
    assert not User.objects.filter(role=Role.ADMIN).exclude(pk=admin.pk).exists()


def test_csv_cree_avec_les_bons_attributs(admin: User) -> None:
    DirectionFactory(code="DAI")  # type: ignore[no-untyped-call]
    importer_csv(
        (
            ENTETE + "kabore.l;l@onea.bf;Landry;Kabore;M-1;DAI;Auditeur;RAI\nsimple;;;;;;;\n"
        ).encode(),
        by=admin,
        dry_run=False,
    )
    u = User.objects.get(username="kabore.l")
    assert (u.origine, u.role, u.keycloak_id, u.role_provisoire) == ("CSV", "RAI", None, True)
    assert u.is_active and not u.is_staff and not u.is_superuser and not u.has_usable_password()
    assert (u.first_name, u.last_name, u.matricule) == ("Landry", "Kabore", "M-1")
    s = User.objects.get(username="simple")
    assert s.role == Role.AUDITE and not s.profil_gere_localement


def test_csv_rapport_identique(admin: User) -> None:
    make_user(username="existe", email="e@onea.bf")
    contenu = (ENTETE + "n1;;;;;;;\nexiste;;;;;;;\nn1;;;;;;;\nn2;e@onea.bf;;;;;;\n").encode()
    a = importer_csv(contenu, by=admin, dry_run=True)
    b = importer_csv(contenu, by=admin, dry_run=False)
    assert replace(b, dry_run=True) == a
    assert a.crees == ["n1"] and len(a.ignores) == 3


def test_csv_bom_et_virgule(admin: User) -> None:
    contenu = "﻿identifiant,email,role\nvirg,v@onea.bf,DG\n".encode()
    rapport = importer_csv(contenu, by=admin, dry_run=False)
    assert rapport.crees == ["virg"]
    assert User.objects.get(username="virg").role == Role.DG


def test_csv_doublon_dans_le_fichier(admin: User) -> None:
    rapport = importer_csv(
        (ENTETE + "dup;;;;;;;\nDUP;;;;;;;\nautre;a@onea.bf;;;;;;\nx;A@ONEA.BF;;;;;;\n").encode(),
        by=admin,
        dry_run=False,
    )
    assert rapport.crees == ["dup", "autre"]
    assert rapport.ignores == [
        LigneIgnoree(3, "DUP", CSV_DOUBLON_FICHIER),
        LigneIgnoree(5, "x", CSV_DOUBLON_FICHIER),
    ]


def test_csv_compte_existant_par_email(admin: User) -> None:
    make_user(username="deja", email="Deja@onea.bf")
    rapport = importer_csv(
        (ENTETE + "nouveau;deja@ONEA.bf;;;;;;\n").encode(), by=admin, dry_run=False
    )
    assert rapport.ignores == [LigneIgnoree(2, "nouveau", CSV_COMPTE_EXISTANT)]


def test_csv_compte_existant_par_identifiant(admin: User) -> None:
    make_user(username="Deja")
    rapport = importer_csv((ENTETE + "deja;;;;;;;\n").encode(), by=admin, dry_run=False)
    assert rapport.ignores == [LigneIgnoree(2, "deja", CSV_COMPTE_EXISTANT)]


def test_csv_matricule_deja_pris(admin: User) -> None:
    make_user(username="deja", matricule="M-9")
    rapport = importer_csv(
        (ENTETE + "n1;;;;M-9;;;\nn2;;;;M-8;;;\nn3;;;;M-8;;;\n").encode(), by=admin, dry_run=False
    )
    assert rapport.crees == ["n2"]
    assert [i.motif for i in rapport.ignores] == [MATRICULE_PRIS, MATRICULE_PRIS]


def test_csv_direction_inconnue(admin: User) -> None:
    rapport = importer_csv((ENTETE + "n1;;;;;ZZZ;;\n").encode(), by=admin, dry_run=False)
    assert rapport.ignores == [LigneIgnoree(2, "n1", DIRECTION_INCONNUE)]


def test_csv_profil_fourni_pose_le_drapeau(admin: User) -> None:
    DirectionFactory(code="DAI")  # type: ignore[no-untyped-call]
    importer_csv(
        (ENTETE + "a;;;;;DAI;;\nb;;;;;;Chef;\nc;;;;;;;\n").encode(), by=admin, dry_run=False
    )
    flags = dict(
        User.objects.filter(username__in=["a", "b", "c"]).values_list(
            "username", "profil_gere_localement"
        )
    )
    assert flags == {"a": True, "b": True, "c": False}


def test_csv_fonction_fournie_pose_le_drapeau(admin: User) -> None:
    importer_csv((ENTETE + "b;;;;;;Chef;\n").encode(), by=admin, dry_run=False)
    assert User.objects.get(username="b").profil_gere_localement is True


def test_csv_valeurs_invalides(admin: User) -> None:
    rapport = importer_csv(
        (
            ENTETE + "bad name;;;;;;;\nok1;pas-un-mail;;;;;;\nok2;;;;;;;SUPER\n"
            f"ok3;;;;{'M' * 33};;;\nok4;;;;;;{'f' * 129};\n"
        ).encode(),
        by=admin,
        dry_run=False,
    )
    assert rapport.crees == [] and len(rapport.ignores) == 5


@pytest.mark.parametrize(
    ("contenu", "message"),
    [
        (b"x" * (1024 * 1024 + 1), "Le fichier dépasse 1 Mo."),
        (("identifiant\n" + "u\n" * 1001).encode(), "Le fichier dépasse 1 000 lignes."),
        ("identifiant\né\n".encode("latin-1"), "Le fichier doit être encodé en UTF-8."),
        (b"email;role\nx;y\n", "En-tête invalide : colonne « identifiant » manquante."),
        (b"", "En-tête invalide : colonne « identifiant » manquante."),
    ],
)
def test_csv_fichier_invalide(admin: User, contenu: bytes, message: str) -> None:
    with pytest.raises(FichierImportInvalide) as exc:
        importer_csv(contenu, by=admin, dry_run=False)
    assert exc.value.message == message


def test_csv_trop_gros_et_trop_long(admin: User) -> None:
    ok = ("identifiant\n" + "".join(f"u{i}\n" for i in range(1000))).encode()
    assert len(importer_csv(ok, by=admin, dry_run=True).crees) == 1000
    with pytest.raises(FichierImportInvalide):
        importer_csv(ok + b"u1000\n", by=admin, dry_run=True)


def test_csv_latin1_refuse(admin: User) -> None:
    with pytest.raises(FichierImportInvalide):
        importer_csv("identifiant;nom\nx;Zoé\n".encode("latin-1"), by=admin, dry_run=False)


def test_csv_entete_sans_identifiant(admin: User) -> None:
    with pytest.raises(FichierImportInvalide):
        importer_csv(b"login;email\nx;y@z.bf\n", by=admin, dry_run=False)


def test_csv_puis_premiere_connexion_sans_doublon(admin: User) -> None:
    DirectionFactory(code="DAI")  # type: ignore[no-untyped-call]
    importer_csv(
        (ENTETE + "kabore.l;l@onea.bf;;;M-042;DAI;Local;AUDITEUR\n").encode(),
        by=admin,
        dry_run=False,
    )
    pre = User.objects.get(username="kabore.l")
    sub = "6f9619ff-8b86-d011-b42d-00c04fc964ff"
    lie = _login(
        claims(
            sub=sub, preferred_username="Kabore.L", roles=["RAI"], email="x@y.bf", direction="DAF"
        )
    )
    assert lie.pk == pre.pk and str(lie.keycloak_id) == sub and lie.role == Role.RAI
    assert lie.matricule == "M-042" and lie.direction_code == "DAI"  # local profile kept
    assert not lie.role_provisoire and lie.premiere_connexion_le is not None
    assert User.objects.filter(username__iexact="kabore.l").count() == 1
