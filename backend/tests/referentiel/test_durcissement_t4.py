"""Durcissement de la tâche 4 : caractères de contrôle, bornes d'import, journal d'audit."""

import io
from pathlib import Path
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from apps.referentiel.imports import ImportReferentielError, importer_referentiel
from apps.referentiel.models import Direction
from apps.users.models import User
from tests.referentiel import typed

REF_CSV = Path(__file__).resolve().parents[2] / "apps/referentiel/data/referentiel-onea.csv"
EN_TETE = "type;code;libelle;famille;ordre;parent;directions"


def _body(v: Any, p: Any, **kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "version": str(v.id),
        "processus": str(p.id),
        "libelle": "Rupture d'approvisionnement",
        "probabilite": 3,
        "impact": 5,
    }
    body.update(kw)
    return body


@pytest.mark.django_db
@pytest.mark.parametrize(
    "champ", ["libelle", "description", "vulnerabilite", "objectif_controle", "dispositif_controle"]
)
@pytest.mark.parametrize("caractere", ["\x00", "\x0b", "\x01"])
def test_caracteres_de_controle_refuses_en_saisie(
    auth_rai: APIClient, champ: str, caractere: str
) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    r = auth_rai.post("/api/v1/risks/", _body(v, p, **{champ: f"a{caractere}b"}), format="json")
    assert r.status_code == 400
    assert champ in r.json()["errors"]  # NUL : message natif de DRF, autres : le notre
    if ord(caractere) != 0:
        assert r.json()["errors"][champ] == ["Les caractères de contrôle ne sont pas autorisés."]


@pytest.mark.django_db
def test_caracteres_de_controle_refuses_en_modification(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    cree = auth_rai.post("/api/v1/risks/", _body(v, p), format="json").json()
    r = auth_rai.patch(f"/api/v1/risks/{cree['id']}/", {"description": "a\x0bb"}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_retours_a_la_ligne_et_tabulations_acceptes(auth_rai: APIClient) -> None:
    v = typed.version(annee=2026)
    p = typed.processus(code="FEP")
    body = _body(v, p, description="ligne 1\r\nligne 2\n\tligne 3")
    assert auth_rai.post("/api/v1/risks/", body, format="json").status_code == 201


def _erreurs(texte: str, by: User) -> list[str]:
    with pytest.raises(ImportReferentielError) as exc:
        importer_referentiel(io.StringIO(texte), by=by)
    return exc.value.erreurs


def test_import_ordre_non_ascii_message_ligne(rai: User) -> None:
    erreurs = _erreurs(f"{EN_TETE}\nPROCESSUS;EST;P;PILOTAGE;²;;\n", rai)
    assert len(erreurs) == 1 and erreurs[0].startswith("Ligne 2 : ordre")


@pytest.mark.parametrize("caractere", ["\x00", "\x01", "\x1f"])
def test_import_caractere_de_controle_message_ligne(rai: User, caractere: str) -> None:
    csv = f"{EN_TETE}\nDIRECTION;DG;Direction{caractere}Générale;;;;\n"
    assert _erreurs(csv, rai) == ["Ligne 2 : caractère de contrôle interdit."]
    assert Direction.objects.count() == 0


def test_dry_run_ne_laisse_aucune_entree_d_audit(rai: User) -> None:
    avant = LogEntry.objects.count()
    with open(REF_CSV, encoding="utf-8-sig") as f:
        importer_referentiel(f, by=rai, dry_run=True)
    assert LogEntry.objects.count() == avant


def test_commande_refuse_un_utilisateur_inactif(rai: User) -> None:
    rai.is_active = False
    rai.save()
    with pytest.raises(CommandError):
        call_command("import_referentiel", str(REF_CSV), "--user", rai.username)
    assert Direction.objects.count() == 0


def test_commande_refuse_un_fichier_trop_gros(
    rai: User, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("apps.referentiel.management.commands.import_referentiel.TAILLE_MAX", 100)
    p = tmp_path / "gros.csv"
    p.write_text(f"{EN_TETE}\n" + "x" * 500, encoding="utf-8")
    with pytest.raises(CommandError, match="Fichier trop volumineux"):
        call_command("import_referentiel", str(p), "--user", rai.username)
    assert Direction.objects.count() == 0


def test_dai_est_un_departement_audit_interne() -> None:
    ligne = next(li for li in REF_CSV.read_text(encoding="utf-8-sig").splitlines() if ";DAI;" in li)
    assert ligne.split(";")[2] == "Département Audit Interne"
