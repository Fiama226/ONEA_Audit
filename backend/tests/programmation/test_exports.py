import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import openpyxl
import pytest
from rest_framework.test import APIClient

from apps.programmation import services
from apps.programmation.exports import COLONNES, exporter_csv, nom_fichier
from apps.programmation.models import LigneProgramme
from apps.users.models import Role
from tests.factories import make_user
from tests.referentiel.typed import direction as make_direction

from .factories import LigneProgrammeFactory, ligne, programme


@pytest.fixture
def auth_rai(api_client: APIClient, db: None) -> APIClient:
    api_client.force_authenticate(make_user(Role.RAI))
    return api_client


def _ligne(**kw: Any) -> LigneProgramme:
    return cast(LigneProgramme, LigneProgrammeFactory(**kw))


def test_csv_conserve_les_accents_et_neutralise_les_formules(auth_rai: APIClient) -> None:
    lg = _ligne(
        titre="Gestion des achats – Ouagadougou",
        justification='=HYPERLINK("x")',
        debut_prevu=date(2026, 3, 2),
        fin_prevue=date(2026, 4, 30),
    )
    resp = auth_rai.get(f"/api/v1/audit-plans/{lg.programme_id}/export/?type=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv; charset=utf-8"
    assert resp["Content-Disposition"].endswith('-brouillon.csv"')
    texte = resp.content.decode("utf-8")
    assert texte.startswith("﻿N°;Mission prévue;")
    assert "Gestion des achats – Ouagadougou" in texte
    # Les guillemets de la formule imposent la citation CSV : le champ commence par `"'=`.
    assert ";\"'=HYPERLINK" in texte
    assert "02/03/2026" in texte


def test_csv_libelles_entites_et_decimales(db: None) -> None:
    lg = _ligne(type="CONSEIL", charge_prevue_jours=Decimal("12.5"))
    lg.entites.set([make_direction(code="DRH"), make_direction(code="DAF")])
    lignes = exporter_csv(lg.programme).decode("utf-8-sig").split("\r\n")
    assert lignes[0] == ";".join(COLONNES)
    champs = lignes[1].split(";")
    assert champs[2] == "Conseil"
    assert champs[5] == "DAF, DRH"
    assert champs[8] == "T1"
    assert champs[9] == "12,5"


def test_nom_fichier(db: None) -> None:
    p = programme(annee=2026)
    assert nom_fichier(p, "csv") == "programme-audit-2026-brouillon.csv"


def test_xlsx_deux_feuilles_dates_et_total(auth_rai: APIClient) -> None:
    p = programme(annee=2026)
    ligne(programme=p, debut_prevu=date(2026, 3, 2), charge_prevue_jours=Decimal("10"))
    ligne(
        programme=p,
        type="CONSEIL",
        debut_prevu=date(2026, 5, 4),
        fin_prevue=date(2026, 5, 29),
        charge_prevue_jours=Decimal("5.5"),
    )
    resp = auth_rai.get(f"/api/v1/audit-plans/{p.id}/export/?type=xlsx")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/vnd.openxmlformats")
    classeur = openpyxl.load_workbook(io.BytesIO(resp.content))
    assert classeur.sheetnames == ["Programme", "Synthèse"]
    assert classeur.properties.creator == "ONEA — Département Audit Interne"
    feuille = classeur["Programme"]
    assert "2026" in str(feuille["A1"].value)
    assert "Brouillon" in str(feuille["A2"].value)
    assert [c.value for c in feuille[4]] == COLONNES
    debut = feuille.cell(row=5, column=7)
    assert isinstance(debut.value, datetime)
    assert debut.number_format == "DD/MM/YYYY"
    assert feuille.freeze_panes == "A5"
    assert feuille.cell(row=feuille.max_row, column=10).value == 15.5
    valeurs = [[c.value for c in r] for r in classeur["Synthèse"].iter_rows()]
    assert ["Missions prévues", 2] in valeurs
    assert ["Charge totale (jours)", 15.5] in valeurs


def test_export_type_invalide_400(auth_rai: APIClient) -> None:
    p = programme()
    for suffixe in ("?type=pdf", ""):
        resp = auth_rai.get(f"/api/v1/audit-plans/{p.id}/export/{suffixe}")
        assert resp.status_code == 400
        assert "type" in resp.json()["errors"]


def test_export_interdit_a_l_audite(api_client: APIClient, db: None) -> None:
    api_client.force_authenticate(make_user(Role.AUDITE))
    p = programme()
    assert api_client.get(f"/api/v1/audit-plans/{p.id}/export/?type=csv").status_code == 403


def test_export_programme_vide(auth_rai: APIClient) -> None:
    p = programme()
    assert exporter_csv(p).decode("utf-8-sig") == ";".join(COLONNES) + "\r\n"
    assert auth_rai.get(f"/api/v1/audit-plans/{p.id}/export/?type=xlsx").status_code == 200


def test_export_lignes_supprimees_absentes(auth_rai: APIClient) -> None:
    p = programme()
    ligne(programme=p, titre="Conservée")
    supprimee = ligne(programme=p, titre="Retirée")
    services.supprimer_ligne(supprimee, by=make_user(Role.RAI))
    texte = auth_rai.get(f"/api/v1/audit-plans/{p.id}/export/?type=csv").content.decode()
    assert "Conservée" in texte
    assert "Retirée" not in texte
