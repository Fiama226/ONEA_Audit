# ruff: noqa: F811, F401, F403
"""Clôture de mission par l'API (R7) : liste des missions à clôturer et clôture (RAI)."""

import pytest

from apps.missions.models import Mission
from apps.suivi.models import StatutSuivi, SuiviAction
from tests.accomplissement.fixtures_api import client_de
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import MISSIONS, EquipeSuivi

pytestmark = pytest.mark.django_db


def _tout_clore(e: EquipeSuivi) -> None:
    SuiviAction.objects.filter(mission=e.mission).update(statut=StatutSuivi.CLOTUREE)


def test_liste_vide_tant_qu_une_action_est_ouverte(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    r = client_de(e.users["rai"]).get(MISSIONS)
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_liste_puis_cloture(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    rai = client_de(e.users["rai"])
    refus = rai.post(f"{MISSIONS}{e.mission.pk}/close/", {}, format="json")
    assert refus.status_code == 422
    assert refus.json()["detail"] == "3 action(s) du plan ne sont pas closes."
    _tout_clore(e)
    liste = rai.get(MISSIONS).json()["results"]
    assert liste == [
        {
            "id": str(e.mission.pk),
            "reference": e.mission.reference,
            "titre": e.mission.titre,
            "statut": "RAPPORT_DIFFUSE",
            "annee": e.mission.annee,
            "actions_total": 3,
            "actions_closes": 3,
        }
    ]
    r = rai.post(
        f"{MISSIONS}{e.mission.pk}/close/", {"commentaire": "Fin du suivi."}, format="json"
    )
    assert r.status_code == 200, r.content
    assert r.json() == {
        "id": str(e.mission.pk),
        "reference": e.mission.reference,
        "titre": e.mission.titre,
        "statut": "CLOTUREE",
    }
    assert Mission.objects.get(pk=e.mission.pk).statut == "CLOTUREE"
    assert rai.get(MISSIONS).json()["results"] == []
    # déjà clôturée : règle métier (la mission reste visible), jamais 404
    assert rai.post(f"{MISSIONS}{e.mission.pk}/close/", {}, format="json").status_code == 422


def test_reserve_au_rai(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    _tout_clore(e)
    for qui in (
        "chef",
        "superviseur",
        "auditeur",
        "responsable",
        "audite",
        "dg",
        "admin",
        "non_affecte",
    ):
        client = client_de(e.users[qui])
        assert client.get(MISSIONS).status_code == 403, qui
        assert client.post(f"{MISSIONS}{e.mission.pk}/close/", {}, format="json").status_code == 403
    assert Mission.objects.get(pk=e.mission.pk).statut == "RAPPORT_DIFFUSE"


def test_mission_inconnue_404(equipe_suivi: EquipeSuivi) -> None:
    rai = client_de(equipe_suivi.users["rai"])
    inconnue = "00000000-0000-0000-0000-000000000000"
    assert rai.post(f"{MISSIONS}{inconnue}/close/", {}, format="json").status_code == 404
