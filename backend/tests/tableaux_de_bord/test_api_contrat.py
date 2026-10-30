# ruff: noqa: F811, F401
"""Contrat JSON des tableaux de bord (fixtures MSW du frontend, lot 8 T15 et T16).

Cles et types des 4 tableaux de bord, et cles de chaque bloc (meme quand le jeu le laisse vide),
comparees a `contrat_lot8.json`. Evolution volontaire : `UPDATE_CONTRAT_LOT8=1 pytest <ce fichier>`.
Le contrat du lot 8 est gele a la fin de la tache 11 : toute evolution est une decision de revue.
"""

import inspect
from pathlib import Path

import pytest
from rest_framework import serializers

from apps.tableaux_de_bord import serializers as blocs
from tests.accomplissement.fixtures_api import client_de
from tests.contrat_forme import comparer
from tests.tableaux_de_bord.conftest import (
    creer_suivi,
    jeu_complet,
    mission_diffusee,
    valider_carto,
)
from tests.tableaux_de_bord.jeux_api import JeuApi, figer_la_date, jeu_api

pytestmark = pytest.mark.django_db
GOLDEN = Path(__file__).with_name("contrat_lot8.json")
BASE = "/api/v1/dashboards/"


@pytest.mark.parametrize(
    "partie, role, chemin",
    [
        ("tableau_rai", "rai", "rai/"),
        ("tableau_auditeur", "auditeur", "auditor/"),
        ("tableau_audite", "audite", "auditee/"),
        ("tableau_dg", "dg", "dg/"),
    ],
)
def test_api_contrat_tableaux(jeu_api: JeuApi, partie: str, role: str, chemin: str) -> None:
    reponse = client_de(getattr(jeu_api, role)).get(BASE + chemin, {"annee": "2026"})
    assert reponse.status_code == 200
    comparer(GOLDEN, partie, reponse.json())


def test_api_contrat_cles_de_chaque_bloc() -> None:
    cles = {
        nom: sorted(classe().fields)
        for nom, classe in inspect.getmembers(blocs, inspect.isclass)
        if issubclass(classe, serializers.Serializer) and classe.__module__ == blocs.__name__
    }
    comparer(GOLDEN, "blocs", cles, brut=True)
