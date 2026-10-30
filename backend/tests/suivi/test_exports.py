# ruff: noqa: F811, F401, F403
"""Exports du registre : CSV / XLSX, neutralisation des formules, plafond, droits, limitation."""

import csv
import io
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings
from openpyxl import load_workbook

from apps.missions.models import StatutEtape
from apps.recommandations.models import Action
from apps.suivi import exports
from apps.suivi.models import StatutSuivi, SuiviAction
from tests.accomplissement.fixtures_api import client_de
from tests.missions.conftest import forcer_etapes
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import ACTIONS, RECOMMANDATIONS, EquipeSuivi

pytestmark = pytest.mark.django_db

FORMULE = '=HYPERLINK("http://exemple.org","cliquez")'


@contextmanager
def etape_ouverte(e: EquipeSuivi, numero: int) -> Iterator[None]:
    """Rouvre une étape le temps d'écrire (gardes des lots 6 et 7 sur le plan d'actions)."""
    forcer_etapes(e.mission, {numero: StatutEtape.EN_COURS})
    yield
    forcer_etapes(e.mission, {numero: StatutEtape.VALIDEE})


def _export(e: EquipeSuivi, qui: str = "rai", base: str = ACTIONS, **params: Any) -> Any:
    return client_de(e.users[qui]).get(f"{base}export/", params)


def _csv(contenu: bytes) -> list[list[str]]:
    texte = contenu.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texte), delimiter=";"))


def test_export_csv_bom_et_point_virgule(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    r = _export(e, format="csv")
    assert r.status_code == 200, r.content
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert r["Content-Type"].startswith("text/csv")
    assert re.fullmatch(
        r'attachment; filename="suivi-actions-\d{8}\.csv"', r["Content-Disposition"]
    )
    assert r["Cache-Control"] == "private, no-store"
    assert r["X-Content-Type-Options"] == "nosniff"
    assert b"\r\n" in r.content
    lignes = _csv(r.content)
    assert lignes[0] == exports.COLONNES_ACTIONS
    assert len(lignes) == 4
    mission = lignes[1][0]
    assert mission == e.mission.reference
    assert lignes[1][11] == "À lancer"
    assert lignes[1][12] == "Non"
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", lignes[1][9])


def test_export_csv_neutralise_les_formules(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    with etape_ouverte(e, 16):
        Action.objects.filter(pk=e.suivi.action_id).update(
            libelle=FORMULE, indicateur="+cmd|' /C calc'!A0"
        )
    lignes = _csv(_export(e, format="csv").content)
    cellules = {c for ligne in lignes for c in ligne}
    assert "'" + FORMULE in cellules
    assert FORMULE not in cellules
    assert "'+cmd|' /C calc'!A0" in cellules


def test_export_xlsx_neutralise_les_formules(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    with etape_ouverte(e, 16):
        Action.objects.filter(pk=e.suivi.action_id).update(libelle=FORMULE)
    r = _export(e, format="xlsx")
    assert r.status_code == 200
    assert r["Content-Type"] == exports.TYPE_XLSX
    assert re.fullmatch(
        r'attachment; filename="suivi-actions-\d{8}\.xlsx"', r["Content-Disposition"]
    )
    classeur = load_workbook(io.BytesIO(r.content))
    feuille = classeur["Actions"]
    en_tetes = [c.value for c in feuille[1]]
    assert en_tetes == exports.COLONNES_ACTIONS
    valeurs = [c.value for ligne in feuille.iter_rows(min_row=2) for c in ligne]
    assert "'" + FORMULE in valeurs
    assert FORMULE not in valeurs
    for ligne in feuille.iter_rows(min_row=2):
        for cellule in ligne:
            assert cellule.data_type != "f", cellule.coordinate
    assert feuille.max_row == 4
    assert feuille.cell(row=2, column=10).number_format == "DD/MM/YYYY"
    assert feuille.cell(row=2, column=11).value == 0


def test_export_recommandations(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    reco = e.suivi.recommandation
    with etape_ouverte(e, 14):
        type(reco).objects.filter(pk=reco.pk).update(libelle=FORMULE)
    r = _export(e, base=RECOMMANDATIONS, format="csv")
    assert r.status_code == 200
    assert re.search(r'filename="suivi-recommandations-\d{8}\.csv"', r["Content-Disposition"])
    lignes = _csv(r.content)
    assert lignes[0] == exports.COLONNES_RECOMMANDATIONS
    assert len(lignes) == 4  # trois recommandations, dont une à risque accepté
    assert "'" + FORMULE in {c for ligne in lignes for c in ligne}
    assert "Risque accepté" in {ligne[5] for ligne in lignes[1:]}
    x = _export(e, base=RECOMMANDATIONS, format="xlsx")
    assert load_workbook(io.BytesIO(x.content))["Recommandations"].max_row == 4


def test_export_respecte_filtres_et_visibilite(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    SuiviAction.objects.filter(pk=e.suivi.pk).update(statut=StatutSuivi.EN_COURS)
    assert len(_csv(_export(e, format="csv", statut="EN_COURS").content)) == 2
    assert len(_csv(_export(e, format="csv", statut="CLOTUREE").content)) == 1
    assert len(_csv(_export(e, "dg", format="csv").content)) == 4
    assert len(_csv(_export(e, "non_affecte", format="csv").content)) == 1
    assert len(_csv(_export(e, "audite_non_affecte", format="csv").content)) == 1
    assert _export(e, "admin", format="csv").status_code == 403
    assert _export(e, "admin", base=RECOMMANDATIONS, format="csv").status_code == 403


def test_export_format_et_negociation(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    for params in ({}, {"format": "pdf"}, {"format": ""}):
        r = _export(e, **params)
        assert r.status_code == 400, params
        assert "format" in r.json()["errors"]
    client = client_de(e.users["rai"])
    r = client.get(f"{ACTIONS}export/", {"format": "csv"}, HTTP_ACCEPT="application/json")
    assert r.status_code == 200
    assert client.get(f"{ACTIONS}export/", {"format": "csv"}, HTTP_ACCEPT="*/*").status_code == 200


def test_export_plafond(equipe_suivi: EquipeSuivi, monkeypatch: pytest.MonkeyPatch) -> None:
    e = equipe_suivi
    monkeypatch.setattr(exports, "LIMITE_LIGNES", 2)
    for base in (ACTIONS, RECOMMANDATIONS):
        r = _export(e, base=base, format="csv")
        assert r.status_code == 422
        assert r.json()["detail"] == "Affinez les filtres : l'export est limité à 5 000 lignes."
    monkeypatch.setattr(exports, "LIMITE_LIGNES", 3)
    assert _export(e, format="csv").status_code == 200
    assert exports.LIMITE_LIGNES == 3


def test_export_plafond_par_defaut_est_5000() -> None:
    import importlib

    assert importlib.import_module("apps.suivi.exports").LIMITE_LIGNES == 5000
    assert "5 000" in exports.MSG_LIMITE


def test_export_limite_429(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    base: dict[str, Any] = settings.REST_FRAMEWORK
    taux = {**base["DEFAULT_THROTTLE_RATES"], "export": "2/min"}
    with override_settings(REST_FRAMEWORK={**base, "DEFAULT_THROTTLE_RATES": taux}):
        client = client_de(e.users["rai"])
        assert client.get(f"{ACTIONS}export/", {"format": "csv"}).status_code == 200
        assert client.get(f"{RECOMMANDATIONS}export/", {"format": "csv"}).status_code == 200
        r = client.get(f"{ACTIONS}export/", {"format": "csv"})
        assert r.status_code == 429
        assert r.json()["errors"] == {}
        assert "Retry-After" in r
        # la limite est par utilisateur : un autre profil n'est pas bloqué
        assert (
            client_de(e.users["dg"]).get(f"{ACTIONS}export/", {"format": "csv"}).status_code == 200
        )
