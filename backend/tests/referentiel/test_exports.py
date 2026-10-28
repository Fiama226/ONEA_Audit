import io
from typing import Any, cast

import openpyxl
from rest_framework.test import APIClient

from apps.referentiel import services
from apps.referentiel.exports import COLONNES, exporter_csv, neutraliser_formule, nom_fichier
from apps.referentiel.models import CartographieVersion, Risque
from apps.users.models import User
from tests import factories
from tests.referentiel import typed


def _risque(**kw: Any) -> Risque:
    return cast(Risque, factories.RisqueFactory(**kw))


def test_csv_conserve_les_accents_et_neutralise_les_formules(auth_rai: APIClient) -> None:
    r = _risque(
        libelle="Défaillance du réseau d'eau – Ouagadougou",
        description='=HYPERLINK("x")',
    )
    resp = auth_rai.get(f"/api/v1/risk-maps/{r.version_id}/export/?type=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv; charset=utf-8"
    assert resp["Content-Disposition"].endswith('-brouillon.csv"')
    texte = resp.content.decode("utf-8")
    assert texte.startswith("﻿Code;Processus;")
    assert "Défaillance du réseau d'eau – Ouagadougou" in texte
    # le champ contient des guillemets : il est cité, l'apostrophe neutralise la formule
    assert "\"'=HYPERLINK" in texte
    assert "\r\n" in texte


def test_csv_colonnes_et_valeurs_en_francais(rai: User) -> None:
    r = _risque(probabilite=5, impact=4, reponse="TRAITER", priorite=1)
    lignes = exporter_csv(r.version).decode("utf-8-sig").split("\r\n")
    assert lignes[0] == ";".join(COLONNES)
    assert COLONNES[0] == "Code" and COLONNES[-1] == "Dispositif de contrôle interne"
    cellules = lignes[1].split(";")
    assert cellules[5:9] == ["5", "4", "20", "Élevé"]
    assert cellules[10:12] == ["Traiter", "Prioritaire"]


def test_neutraliser_formule() -> None:
    for dangereux in (
        "=1+1",
        "+1",
        "-1",
        "@SUM(A1)",
        "\tx",
        "\rx",
        " =1+1",
        "\n=1+1",
        " =1+1",
        "  \t@x",
    ):
        assert neutraliser_formule(dangereux) == "'" + dangereux
    assert neutraliser_formule("Texte normal") == "Texte normal"
    assert neutraliser_formule("") == ""


def test_nom_fichier(db: None) -> None:
    v = cast(CartographieVersion, factories.CartographieVersionFactory(annee=2026))
    assert nom_fichier(v, "csv") == "cartographie-2026-brouillon.csv"
    v.statut = "VALIDEE"
    assert nom_fichier(v, "xlsx") == "cartographie-2026.xlsx"


def test_xlsx_deux_feuilles_et_matrice(auth_rai: APIClient) -> None:
    r = _risque(probabilite=3, impact=5)
    resp = auth_rai.get(f"/api/v1/risk-maps/{r.version_id}/export/?type=xlsx")
    assert resp.status_code == 200
    assert resp["Content-Type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert resp["Content-Disposition"].endswith('-brouillon.xlsx"')
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    assert wb.sheetnames == ["Risques", "Matrice"]
    assert wb.properties.creator == "ONEA — Département Audit Interne"
    risques = wb["Risques"]
    assert [c.value for c in risques[1]] == COLONNES
    assert risques["A1"].font.bold
    assert risques.freeze_panes == "A2"
    assert risques.auto_filter.ref
    assert risques["A2"].value == r.code
    matrice = wb["Matrice"]
    assert matrice["B1"].value == "Impact" and matrice["A2"].value == "Probabilité"
    assert matrice["A3"].value == 5 and matrice["A7"].value == 1
    cellule = matrice.cell(row=5, column=6)  # probabilité 3, impact 5
    assert cellule.value == r.code
    assert cellule.fill.fgColor.rgb.endswith("F8C9C4")  # score 15 : élevé


def test_xlsx_ecrit_les_textes_bruts_sans_formule(auth_rai: APIClient) -> None:
    r = _risque(description="=1+1", dispositif_controle="- Contrôle 1\n- Contrôle 2")
    resp = auth_rai.get(f"/api/v1/risk-maps/{r.version_id}/export/?type=xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    feuille = wb["Risques"]
    assert feuille["E2"].value == "=1+1"  # aucune apostrophe visible
    assert feuille["E2"].data_type == "s"  # jamais interprété comme formule
    assert feuille["N2"].value == "- Contrôle 1\n- Contrôle 2"


def test_csv_garde_l_apostrophe_de_neutralisation(auth_rai: APIClient) -> None:
    r = _risque(dispositif_controle="- Contrôle 1")
    resp = auth_rai.get(f"/api/v1/risk-maps/{r.version_id}/export/?type=csv")
    assert ";'- Contrôle 1" in resp.content.decode("utf-8")


def test_caracteres_de_controle_ne_cassent_pas_les_exports(auth_rai: APIClient) -> None:
    r = _risque(description="a\x0bb\x01c", vulnerabilite="x\x1fy")
    base = f"/api/v1/risk-maps/{r.version_id}/export/"
    xlsx = auth_rai.get(f"{base}?type=xlsx")
    assert xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(xlsx.content))
    assert wb["Risques"]["E2"].value == "abc"
    assert wb["Risques"]["J2"].value == "xy"
    texte = auth_rai.get(f"{base}?type=csv").content.decode("utf-8")
    assert ";abc;" in texte and "\x0b" not in texte and "\x01" not in texte


def test_export_ignore_l_en_tete_accept(auth_rai: APIClient) -> None:
    r = _risque()
    base = f"/api/v1/risk-maps/{r.version_id}/export/"
    for accept, type_ in (
        ("text/csv", "csv"),
        ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
        ("application/octet-stream", "csv"),
        ("*/*", "xlsx"),
    ):
        resp = auth_rai.get(f"{base}?type={type_}", HTTP_ACCEPT=accept)
        assert resp.status_code == 200, accept
    erreur = auth_rai.get(f"{base}?type=pdf", HTTP_ACCEPT="text/csv")
    assert erreur.status_code == 400
    assert "type" in erreur.json()["errors"]


def test_export_type_invalide_400(auth_rai: APIClient) -> None:
    v = typed.version()
    for suffixe in ("", "?type=pdf"):
        resp = auth_rai.get(f"/api/v1/risk-maps/{v.pk}/export/{suffixe}")
        assert resp.status_code == 400
        assert "type" in resp.json()["errors"]


def test_export_interdit_a_l_audite(api_client: APIClient, audite: User) -> None:
    v = typed.version()
    api_client.force_authenticate(user=audite)
    assert api_client.get(f"/api/v1/risk-maps/{v.pk}/export/?type=csv").status_code == 403


def test_export_lisible_par_dg_et_anonyme_refuse(api_client: APIClient, dg: User) -> None:
    v = typed.version()
    url = f"/api/v1/risk-maps/{v.pk}/export/?type=csv"
    assert api_client.get(url).status_code == 401
    api_client.force_authenticate(user=dg)
    assert api_client.get(url).status_code == 200


def test_export_cartographie_validee_sans_suffixe(auth_rai: APIClient, rai: User) -> None:
    r = _risque()
    services.valider_version(r.version, by=rai)
    resp = auth_rai.get(f"/api/v1/risk-maps/{r.version_id}/export/?type=csv")
    assert (
        resp["Content-Disposition"] == f'attachment; filename="cartographie-{r.version.annee}.csv"'
    )
