# ruff: noqa: F811, F401
"""API des tableaux de bord : rôles, paramètre `annee`, cohérence avec le registre."""

import pytest
from django.db.models import Count

from apps.suivi.models import SuiviAction
from apps.suivi.services.commun import EXPR_EN_RETARD
from apps.users.models import Role
from tests.accomplissement.fixtures_api import client_de
from tests.factories import make_user
from tests.tableaux_de_bord.conftest import (  # noqa: isort
    AUJOURD_HUI,
    creer_suivi,
    jeu_complet,
    mission_diffusee,
    valider_carto,
)
from tests.tableaux_de_bord.jeux_api import JeuApi, figer_la_date, jeu_api

pytestmark = pytest.mark.django_db

BASE = "/api/v1/dashboards/"
AUTORISES = {
    "rai/": {Role.RAI},
    "auditor/": {Role.AUDITEUR},
    "auditee/": {Role.AUDITE},
    "dg/": {Role.DG, Role.RAI},
}


@pytest.mark.parametrize("chemin", sorted(AUTORISES))
def test_dashboards_role_403(chemin: str, figer_la_date: object) -> None:
    for role in Role.values:
        reponse = client_de(make_user(role)).get(BASE + chemin)
        if role in AUTORISES[chemin]:
            assert reponse.status_code == 200, (chemin, role, reponse.content)
        else:
            assert reponse.status_code == 403, (chemin, role)
            assert set(reponse.json()) == {"detail", "errors"}


@pytest.mark.parametrize("chemin", sorted(AUTORISES))
def test_dashboards_anonyme_401(chemin: str, api_client: object) -> None:
    assert api_client.get(BASE + chemin).status_code == 401  # type: ignore[attr-defined]


@pytest.mark.parametrize("chemin", ["rai/", "dg/", "implementation-rates/export/"])
@pytest.mark.parametrize("annee", ["1999", "2101", "abc", "", "-1", "2026.5", "２０２６", "2026 "])
def test_annee_invalide_400(chemin: str, annee: str, jeu_api: JeuApi) -> None:
    params = {"annee": annee, **({"format": "csv"} if "export" in chemin else {})}
    reponse = client_de(jeu_api.rai).get(BASE + chemin, params)
    assert reponse.status_code == 400, (chemin, annee)
    assert "annee" in reponse.json()["errors"]


def test_annee_par_defaut_et_bornes(jeu_api: JeuApi, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.tableaux_de_bord.views.aujourd_hui", lambda: AUJOURD_HUI)
    client = client_de(jeu_api.rai)
    assert client.get(BASE + "rai/").json()["annee"] == 2026
    assert client.get(BASE + "rai/", {"annee": "2000"}).json()["annee"] == 2000
    assert client.get(BASE + "dg/", {"annee": "2100"}).json()["annee"] == 2100
    assert client.get(BASE + "rai/", {"annee": "2025"}).json()["taux"]["total"] == 0


def test_tableau_rai_coherent_avec_registre(jeu_api: JeuApi) -> None:
    """« En retard » par direction = nombre de suivis en retard du registre, par entité."""
    corps = client_de(jeu_api.rai).get(BASE + "rai/", {"annee": "2026"}).json()
    attendu = {
        str(ligne["entite_id"]): ligne["n"]
        for ligne in SuiviAction.objects.filter(EXPR_EN_RETARD(AUJOURD_HUI))
        .values("entite_id")
        .annotate(n=Count("pk"))
    }
    obtenu = {
        ligne["direction_id"]: ligne["en_retard"]
        for ligne in corps["actions_par_direction"]
        if ligne["en_retard"]
    }
    assert obtenu == attendu
    assert attendu  # le jeu comporte bien un retard
    assert corps["taux"]["total"] == SuiviAction.objects.count()


def test_tableau_auditeur_et_audite_limites_a_leur_perimetre(jeu_api: JeuApi) -> None:
    auditeur = client_de(jeu_api.auditeur).get(BASE + "auditor/").json()
    assert [m["mission_id"] for m in auditeur["mes_missions"]] == [str(jeu_api.mission.pk)]
    assert len(auditeur["actions_a_verifier"]) == 1
    audite = client_de(jeu_api.audite).get(BASE + "auditee/").json()
    assert len(audite["constats_a_repondre"]) == 1
    assert len(audite["mes_actions"]) == 3
    assert len(audite["mes_demandes_report"]) == 1
    autre = client_de(make_user(Role.AUDITEUR)).get(BASE + "auditor/").json()
    assert autre["mes_missions"] == [] and autre["actions_a_verifier"] == []
    vide = client_de(make_user(Role.AUDITE)).get(BASE + "auditee/").json()
    assert vide["mes_actions"] == [] and vide["constats_a_repondre"] == []


def test_tableau_dg_pour_dg_et_rai(jeu_api: JeuApi) -> None:
    pour_dg = client_de(jeu_api.dg).get(BASE + "dg/", {"annee": "2026"}).json()
    pour_rai = client_de(jeu_api.rai).get(BASE + "dg/", {"annee": "2026"}).json()
    assert pour_dg == pour_rai
    assert pour_dg["taux"]["total"] > 0
    assert {r["mission_id"] for r in pour_dg["rapports_diffuses"]} == {str(jeu_api.mission.pk)}
    assert isinstance(pour_dg["taux"]["taux"], float)
