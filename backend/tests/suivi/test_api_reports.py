# ruff: noqa: F811, F401, F403
"""Demandes de report d'échéance par l'API (R5)."""

import datetime
from typing import Any

import pytest

from apps.suivi.models import DemandeReport, StatutDemandeReport, StatutSuivi, SuiviAction
from tests.accomplissement.fixtures_api import client_de
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import ACTIONS, REPORTS, EquipeSuivi

pytestmark = pytest.mark.django_db


def _demander(e: EquipeSuivi, qui: str = "responsable", jours: int = 30, **corps: Any) -> Any:
    s = corps.pop("suivi", e.suivi)
    donnees = {
        "action": str(s.pk),
        "nouvelle_echeance": (s.echeance + datetime.timedelta(days=jours)).isoformat(),
        "motif": "Marché de fournitures retardé.",
        **corps,
    }
    return client_de(e.users[qui]).post(REPORTS, donnees, format="json")


def test_demande_puis_acceptation(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    r = _demander(e)
    assert r.status_code == 201, r.content
    demande = r.json()
    assert demande["statut"] == "EN_ATTENTE"
    assert demande["action"] == str(s.pk)
    assert demande["echeance_actuelle"] == str(s.echeance)
    assert demande["demandee_par"]["id"] == e.users["responsable"].pk
    assert demande["decidee_par"] is None
    assert demande["actions_possibles"] == []  # le responsable ne décide pas
    action = client_de(e.users["rai"]).get(f"{ACTIONS}{s.pk}/").json()
    assert action["demande_report_en_attente"]["id"] == demande["id"]
    assert action["demande_report_en_attente"]["actions_possibles"] == ["ACCEPTER", "REFUSER"]
    # une seule demande en attente par action
    assert _demander(e, jours=40).status_code == 422
    rai = client_de(e.users["rai"])
    r = rai.post(f"{REPORTS}{demande['id']}/accept/", {"commentaire": "Accordé."}, format="json")
    assert r.status_code == 200, r.content
    assert r.json()["statut"] == "ACCEPTEE"
    assert r.json()["decidee_par"]["id"] == e.users["rai"].pk
    assert r.json()["commentaire_decision"] == "Accordé."
    assert r.json()["actions_possibles"] == []
    s.refresh_from_db()
    assert str(s.echeance) == demande["nouvelle_echeance"]
    assert s.nombre_reports == 1
    action = rai.get(f"{ACTIONS}{s.pk}/").json()
    assert action["nombre_reports"] == 1
    assert action["demande_report_en_attente"] is None
    assert action["echeance_initiale"] != action["echeance"]
    assert rai.post(f"{REPORTS}{demande['id']}/accept/", {}, format="json").status_code == 422


def test_refus_commentaire_obligatoire(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    demande = _demander(e).json()
    rai = client_de(e.users["rai"])
    url = f"{REPORTS}{demande['id']}/refuse/"
    assert rai.post(url, {}, format="json").status_code == 400
    r = rai.post(url, {"commentaire": "Délai trop long."}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "REFUSEE"
    assert str(SuiviAction.objects.get(pk=e.suivi.pk).echeance) == demande["echeance_actuelle"]
    assert _demander(e, jours=10).status_code == 201  # une nouvelle demande est possible


def test_droits_et_ordre_des_refus(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    demande = _demander(e).json()
    url = f"{REPORTS}{demande['id']}/"
    for qui in ("responsable", "chef", "auditeur", "audite", "dg"):
        assert (
            client_de(e.users[qui]).post(f"{url}accept/", {}, format="json").status_code == 403
        ), qui
        assert (
            client_de(e.users[qui]).post(f"{url}refuse/", {}, format="json").status_code == 403
        ), qui
    for qui in ("non_affecte", "audite_non_affecte"):
        assert client_de(e.users[qui]).post(f"{url}accept/", {}, format="json").status_code == 404
        assert client_de(e.users[qui]).get(url).status_code == 404
    assert client_de(e.users["admin"]).get(REPORTS).status_code == 403
    # création : rôle 403, action invisible 404, droit 403, corps 400, règle 422
    for qui in ("chef", "audite", "dg", "auditeur"):
        assert _demander(e, qui, suivi=e.suivis[1]).status_code == 403, qui
    assert _demander(e, "non_affecte", suivi=e.suivis[1]).status_code == 404
    assert _demander(e, "admin", suivi=e.suivis[1]).status_code == 403
    assert _demander(e, suivi=e.suivis[1], motif="").status_code == 400
    assert _demander(e, suivi=e.suivis[1], nouvelle_echeance="pas une date").status_code == 400
    assert _demander(e, suivi=e.suivis[1], jours=-1).status_code == 422
    assert _demander(e, suivi=e.suivis[1], jours=0).status_code == 422
    sans = client_de(e.users["responsable"]).post(REPORTS, {"motif": "x"}, format="json")
    assert sans.status_code == 400


def test_rai_pour_le_compte_du_responsable(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    corps = {"motif": "Appel du responsable."}
    r = _demander(e, "rai", **corps)
    assert r.status_code == 201
    assert r.json()["demandee_par"]["id"] == e.users["rai"].pk


def test_action_non_reportable_et_gel(equipe_suivi: EquipeSuivi) -> None:
    from apps.missions.models import Mission, StatutMission

    e = equipe_suivi
    SuiviAction.objects.filter(pk=e.suivi.pk).update(statut=StatutSuivi.REALISEE)
    assert _demander(e).status_code == 422
    Mission.objects.filter(pk=e.mission.pk).update(statut=StatutMission.CLOTUREE)
    assert _demander(e, suivi=e.suivis[1]).status_code == 422


def test_liste_filtres_et_requetes_bornees(
    equipe_suivi: EquipeSuivi, django_assert_max_num_queries: Any
) -> None:
    e = equipe_suivi
    for s in e.suivis:
        assert _demander(e, suivi=s).status_code == 201
    DemandeReport.objects.filter(suivi=e.suivi).update(statut=StatutDemandeReport.REFUSEE)
    rai = client_de(e.users["rai"])
    for qui, borne in (("rai", 5), ("auditeur", 7), ("responsable", 7)):
        with django_assert_max_num_queries(borne):
            r = client_de(e.users[qui]).get(REPORTS)
        assert r.status_code == 200 and r.json()["count"] == 3, qui
    assert rai.get(REPORTS, {"statut": "EN_ATTENTE"}).json()["count"] == 2
    assert rai.get(REPORTS, {"action": str(e.suivi.pk)}).json()["count"] == 1
    assert rai.get(REPORTS, {"mission": str(e.mission.pk)}).json()["count"] == 3
    assert rai.get(REPORTS, {"statut": "INCONNU"}).status_code == 400
    assert client_de(e.users["non_affecte"]).get(REPORTS).json()["results"] == []


def test_liste_expose_mission_et_action_pour_ecran_dedie(equipe_suivi: EquipeSuivi) -> None:
    """Le journal des reports affiche la mission et l'action sans requête supplémentaire."""
    e = equipe_suivi
    assert _demander(e).status_code == 201
    rai = client_de(e.users["rai"])
    ligne = rai.get(REPORTS, {"statut": "EN_ATTENTE"}).json()["results"][0]
    assert ligne["mission_id"] == str(e.mission.pk)
    assert ligne["mission_reference"] == e.mission.reference
    assert ligne["action_libelle"] == e.suivi.action.libelle
    # le détail garde la forme figée du contrat
    detail = rai.get(f"{REPORTS}{ligne['id']}/").json()
    assert "mission_reference" not in detail
