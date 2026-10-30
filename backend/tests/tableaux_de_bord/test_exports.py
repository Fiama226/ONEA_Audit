# ruff: noqa: F811, F401
"""Exports CSV / XLSX des taux de mise en oeuvre : droits, contenu, anti-injection."""

import io

import pytest
from openpyxl import load_workbook

from apps.tableaux_de_bord import exports
from apps.users.models import Role
from tests.accomplissement.fixtures_api import client_de
from tests.factories import make_user
from tests.tableaux_de_bord.conftest import (
    creer_suivi,
    jeu_complet,
    mission_diffusee,
    valider_carto,
)
from tests.tableaux_de_bord.jeux_api import JeuApi, figer_la_date, jeu_api

pytestmark = pytest.mark.django_db

URL = "/api/v1/dashboards/implementation-rates/export/"


def test_export_taux_xlsx(jeu_api: JeuApi) -> None:
    reponse = client_de(jeu_api.dg).get(URL, {"annee": "2026", "format": "xlsx"})
    assert reponse.status_code == 200
    assert reponse["Content-Type"] == exports.TYPE_XLSX
    assert reponse["Content-Disposition"] == 'attachment; filename="taux-mise-en-oeuvre-2026.xlsx"'
    feuille = load_workbook(io.BytesIO(reponse.content)).active
    lignes = list(feuille.iter_rows(min_row=3, values_only=True))
    assert list(lignes[0]) == exports.COLONNES
    assert lignes[-1][0] == "Total"
    assert lignes[-1][2] == 6  # actions du jeu (3 de la mission de base + 3)
    assert len(lignes) == 2 + len(
        set(jeu_api.mission.suivis_actions.values_list("entite", flat=True))
    )


def test_export_taux_csv(jeu_api: JeuApi) -> None:
    reponse = client_de(jeu_api.rai).get(URL, {"annee": "2026", "format": "csv"})
    assert reponse.status_code == 200
    assert reponse["Content-Type"] == exports.TYPE_CSV
    texte = reponse.content.decode("utf-8-sig")
    assert reponse.content.startswith(b"\xef\xbb\xbf")
    lignes = texte.strip().split("\r\n")
    assert lignes[0] == ";".join(exports.COLONNES)
    assert lignes[-1].startswith("Total;Toutes directions;6;")
    assert all(len(ligne.split(";")) == len(exports.COLONNES) for ligne in lignes)


def test_export_taux_droits_et_format(jeu_api: JeuApi) -> None:
    for role in (Role.AUDITEUR, Role.AUDITE, Role.ADMIN):
        reponse = client_de(make_user(role)).get(URL, {"format": "csv"})
        assert reponse.status_code == 403
        assert set(reponse.json()) == {"detail", "errors"}
    client = client_de(jeu_api.rai)
    for format_ in ("pdf", "", "CSV", "xlsx; rm"):
        reponse = client.get(URL, {"format": format_})
        assert reponse.status_code == 400, format_
        assert "format" in reponse.json()["errors"]
    assert client.get(URL).status_code == 400
    assert client.get(URL, {"format": "csv"}, HTTP_ACCEPT="application/json").status_code == 200


def test_export_neutralise_les_formules() -> None:
    donnees = {
        "annee": 2026,
        "taux": {
            "total": 1,
            "cloturees": 0,
            "abandonnees": 0,
            "taux": 0.0,
            "echues": 0,
            "cloturees_echues": 0,
            "taux_echues": None,
        },
        "taux_par_direction": [
            {
                "code": "=CMD()",
                "libelle": "@SUM(A1)\x00",
                "total": 1,
                "cloturees": 0,
                "abandonnees": 0,
                "taux": 0.0,
                "echues": 0,
                "cloturees_echues": 0,
                "taux_echues": None,
            }
        ],
    }
    csv = exports.exporter_csv(donnees).decode("utf-8-sig").split("\r\n")[1]
    assert csv.startswith("'=CMD();'@SUM(A1);")
    feuille = load_workbook(io.BytesIO(exports.exporter_xlsx(donnees))).active
    cellule = feuille["A4"]
    assert cellule.data_type == "s"
    assert cellule.value == "=CMD()"
    assert "\x00" not in feuille["B4"].value
