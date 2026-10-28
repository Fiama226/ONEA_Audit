import io
from pathlib import Path

import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command

from apps.referentiel.imports import ImportReferentielError, RapportImport, importer_referentiel
from apps.referentiel.models import Direction, Processus
from apps.users.models import Role, User
from tests.factories import make_user

REF_CSV = Path(__file__).resolve().parents[2] / "apps/referentiel/data/referentiel-onea.csv"
EN_TETE = "type;code;libelle;famille;ordre;parent;directions"
MSG_TROP_VOLUMINEUX = "Fichier trop volumineux : 5 000 lignes au maximum."


def _importer(texte: str, by: User, *, dry_run: bool = False) -> RapportImport:
    return importer_referentiel(io.StringIO(texte), by=by, dry_run=dry_run)


def _erreurs(texte: str, by: User) -> list[str]:
    with pytest.raises(ImportReferentielError) as exc:
        _importer(texte, by)
    return exc.value.erreurs


def test_import_deux_fois_est_idempotent(rai: User) -> None:
    with open(REF_CSV, encoding="utf-8-sig") as f:
        premier = importer_referentiel(f, by=rai)
    assert premier.crees == {"directions": 17, "departements": 0, "processus": 11}
    with open(REF_CSV, encoding="utf-8-sig") as f:
        rapport = importer_referentiel(f, by=rai)
    assert sum(rapport.crees.values()) == 0 and sum(rapport.mis_a_jour.values()) == 0
    assert rapport.inchanges == 28
    assert Processus.objects.count() == 11 and Direction.objects.count() == 17
    est = Processus.objects.get(code="EST")
    assert est.libelle == "Élaborer et mettre en œuvre la stratégie"
    assert est.directions.count() == 6


def test_import_met_a_jour_sans_rien_supprimer(rai: User) -> None:
    _importer(f"{EN_TETE}\nDIRECTION;DG;Ancien;;;;\nPROCESSUS;EST;Ancien;pilotage;1;;DG\n", rai)
    rapport = _importer(
        f"{EN_TETE}\nDIRECTION;DG;Direction Générale;;;;\nPROCESSUS;EST;Stratégie;Pilotage;2;;DG\n",
        rai,
    )
    assert rapport.mis_a_jour == {"directions": 1, "departements": 0, "processus": 1}
    assert Direction.objects.get(code="DG").libelle == "Direction Générale"
    assert Processus.objects.get(code="EST").ordre == 2
    # un fichier partiel ne supprime rien
    _importer(f"{EN_TETE}\nDIRECTION;DAI;Audit Interne;;;;\n", rai)
    assert Direction.objects.count() == 2
    assert Processus.objects.count() == 1


def test_import_departement_et_famille_sans_accent_ni_casse(rai: User) -> None:
    csv = (
        f"{EN_TETE}\nDIRECTION;DRH;Ressources humaines;;;;\n"
        "DEPARTEMENT;DRH-REC;Recrutement;;;DRH;\n"
        "PROCESSUS;GRH;Gérer les RH;RÉALISATION;3;;DRH\n"
    )
    _importer(csv, rai)
    dep = Direction.objects.get(code="DRH-REC")
    assert dep.parent is not None and dep.parent.code == "DRH"
    assert Processus.objects.get(code="GRH").famille == "REALISATION"


def test_import_5001_lignes_refuse_sans_ecriture(rai: User) -> None:
    lignes = "".join(f"DIRECTION;D{i};Libellé {i};;;;\n" for i in range(5001))
    assert _erreurs(f"{EN_TETE}\n{lignes}", rai) == [MSG_TROP_VOLUMINEUX]
    assert Direction.objects.count() == 0


def test_import_limite_incluse(rai: User, monkeypatch: pytest.MonkeyPatch) -> None:
    # limite abaissée : 5 000 écritures par les services prendraient plusieurs minutes
    monkeypatch.setattr("apps.referentiel.imports.MAX_LIGNES", 30)
    lignes = "".join(f"DIRECTION;D{i};Libellé {i};;;;\n" for i in range(30))
    assert _importer(f"{EN_TETE}\n{lignes}", rai).crees["directions"] == 30
    assert _erreurs(f"{EN_TETE}\n{lignes}DIRECTION;DZ;Z;;;;\n", rai) == [MSG_TROP_VOLUMINEUX]


def test_import_cp1252_refuse(rai: User, tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_bytes(f"{EN_TETE}\nDIRECTION;DG;Générale;;;;\n".encode("cp1252"))
    with open(p, encoding="utf-8-sig") as f, pytest.raises(ImportReferentielError) as exc:
        importer_referentiel(f, by=rai)
    assert exc.value.erreurs == ["Encodage invalide : enregistrez le fichier en UTF-8."]
    assert Direction.objects.count() == 0


def test_import_en_tete_incorrect(rai: User) -> None:
    attendu = ["En-tête attendu : type;code;libelle;famille;ordre;parent;directions"]
    assert _erreurs("code;libelle\nDG;x\n", rai) == attendu
    assert _erreurs("", rai) == attendu


def test_import_erreur_ligne_annule_tout(rai: User) -> None:
    csv = (
        f"{EN_TETE}\nDIRECTION;DG;Direction Générale;;;;\nPROCESSUS;ÉST;Stratégie;PILOTAGE;1;;DG\n"
    )
    assert _erreurs(csv, rai) == ["Ligne 3 : code « ÉST » invalide."]
    assert Direction.objects.count() == 0 and Processus.objects.count() == 0


def test_import_erreur_de_service_annule_tout(rai: User) -> None:
    csv = f"{EN_TETE}\nDIRECTION;DG;Direction Générale;;;;\nPROCESSUS;EST;P;PILOTAGE;1;;ABSENT\n"
    erreurs = _erreurs(csv, rai)
    assert len(erreurs) == 1 and erreurs[0].startswith("Ligne 3 : ")
    assert Direction.objects.count() == 0


def test_import_departement_sans_direction_connue(rai: User) -> None:
    erreurs = _erreurs(f"{EN_TETE}\nDEPARTEMENT;DEP1;Dép;;;INCONNU;\n", rai)
    assert erreurs == ["Ligne 2 : direction « INCONNU » introuvable."]


def test_import_erreurs_multiples(rai: User) -> None:
    csv = (
        f"{EN_TETE}\nDIRECTION;DG;A;;;;\nDIRECTION;DG;B;;;;\n"
        "PROCESSUS;EST;P;MAUVAISE;1;;ABSENT\n"
        "TRUC;XX;Y;;;;\n"
        "DIRECTION;DX;;;;;\n"
        "DIRECTION;DY;Y\n"
    )
    erreurs = _erreurs(csv, rai)
    for n in (3, 4, 5, 6, 7):
        assert any(e.startswith(f"Ligne {n} : ") for e in erreurs), (n, erreurs)
    assert "doublon" in next(e for e in erreurs if e.startswith("Ligne 3 : "))
    assert Direction.objects.count() == 0


def test_import_champ_trop_long_message_ligne(rai: User) -> None:
    csv = f"{EN_TETE}\nDIRECTION;DG;{'x' * 200_000};;;;\n"
    erreurs = _erreurs(csv, rai)
    assert len(erreurs) == 1 and erreurs[0].startswith("Ligne 2 : ")


def test_import_dry_run_n_ecrit_rien(rai: User) -> None:
    with open(REF_CSV, encoding="utf-8-sig") as f:
        rapport = importer_referentiel(f, by=rai, dry_run=True)
    assert rapport.crees["directions"] == 17 and rapport.crees["processus"] == 11
    assert Direction.objects.count() == 0 and Processus.objects.count() == 0


def test_import_historise_avec_l_acteur(rai: User) -> None:
    _importer(f"{EN_TETE}\nDIRECTION;DG;Direction Générale;;;;\n", rai)
    d = Direction.objects.get(code="DG")
    entree = LogEntry.objects.get(
        content_type=ContentType.objects.get_for_model(Direction), object_pk=str(d.pk)
    )
    assert entree.actor == rai


def test_commande_importe_et_affiche_le_resume(
    rai: User, capsys: pytest.CaptureFixture[str]
) -> None:
    call_command("import_referentiel", str(REF_CSV), "--user", rai.username)
    sortie = capsys.readouterr().out
    assert "Directions : 17 créées, 0 mises à jour" in sortie
    assert Direction.objects.count() == 17


def test_commande_dry_run(rai: User, capsys: pytest.CaptureFixture[str]) -> None:
    call_command("import_referentiel", str(REF_CSV), "--user", rai.username, "--dry-run")
    assert Direction.objects.count() == 0
    assert "simulation" in capsys.readouterr().out.lower()


def test_commande_accepte_un_admin(db: None) -> None:
    admin = make_user(Role.ADMIN)
    call_command("import_referentiel", str(REF_CSV), "--user", admin.username)
    assert Processus.objects.count() == 11


def test_commande_refuse_un_auditeur(user: User) -> None:
    with pytest.raises(CommandError):
        call_command("import_referentiel", str(REF_CSV), "--user", user.username)
    assert Direction.objects.count() == 0


def test_commande_utilisateur_ou_fichier_inconnu(rai: User) -> None:
    with pytest.raises(CommandError):
        call_command("import_referentiel", str(REF_CSV), "--user", "fantome")
    with pytest.raises(CommandError):
        call_command("import_referentiel", "/nulle/part.csv", "--user", rai.username)


def test_commande_echec_liste_les_erreurs(
    rai: User, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "x.csv"
    p.write_text(f"{EN_TETE}\nDIRECTION;dg;Direction;;;;\n", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command("import_referentiel", str(p), "--user", rai.username)
    assert "Ligne 2 : code « dg » invalide." in capsys.readouterr().err
    assert Direction.objects.count() == 0
