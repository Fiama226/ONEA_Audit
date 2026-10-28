from rest_framework.test import APIClient

from apps.missions.models import EtapeMission, Mission, RoleMission, StatutEtape, StatutMission
from apps.users.models import Role, User
from tests.factories import (
    DirectionFactory,
    MissionFactory,
    ProcessusFactory,
    make_user,
)

from .conftest import affecter

Equipe = tuple[Mission, dict[str, User]]


def _corps_creation() -> dict[str, object]:
    return {
        "titre": "Audit de la facturation",
        "type": "ASSURANCE",
        "processus": [str(ProcessusFactory().id)],
        "entites": [str(DirectionFactory().id)],
        "date_debut_prevue": "2026-03-02",
        "date_fin_prevue": "2026-03-27",
        "budget_jours": "20.0",
        "objectifs": "Évaluer le dispositif.",
        "perimetre": "Toutes les agences.",
    }


def test_cycle_complet_creation_planification_lancement(api_client: APIClient, rai: User) -> None:
    MissionFactory()  # crée la cartographie validée
    api_client.force_authenticate(rai)
    r = api_client.post("/api/v1/missions/", _corps_creation(), format="json")
    assert r.status_code == 201, r.json()
    mission = r.json()
    assert mission["statut"] == "BROUILLON"
    assert mission["reference"] == ""
    assert len(mission["processus_detail"]) == 1
    assert mission["mes_droits"]["planifier"] is True
    mid = mission["id"]

    r = api_client.post(f"/api/v1/missions/{mid}/plan/")
    assert r.status_code == 200, r.json()
    assert r.json()["reference"] == "DAI/2026/M01"
    assert r.json()["statut"] == "PLANIFIEE"

    chef = make_user(Role.AUDITEUR)
    r = api_client.post(
        "/api/v1/mission-assignments/",
        {"mission": mid, "utilisateur": chef.id, "role_mission": "CHEF_MISSION"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["declaration"]["statut"] == "EN_ATTENTE"

    r = api_client.post(f"/api/v1/missions/{mid}/launch/")
    assert r.status_code == 200, r.json()
    assert r.json()["statut"] == "EN_PLANIFICATION"
    assert r.json()["etape_courante"] == {"numero": 1, "romain": "I"}
    assert r.json()["chef_mission"]["id"] == chef.id

    r = api_client.post(f"/api/v1/missions/{mid}/issue-order/", {"confirme": True}, format="json")
    assert r.status_code == 200, r.json()
    assert r.json()["ordre_mission"]["type_document"] == "ORDRE_MISSION"
    assert r.json()["ordre_mission_emis_le"] is not None

    r = api_client.post(f"/api/v1/missions/{mid}/suspend/", {"motif": "Grève"}, format="json")
    assert r.json()["statut"] == "SUSPENDUE"
    r = api_client.post(f"/api/v1/missions/{mid}/resume/")
    assert r.json()["statut"] == "EN_PLANIFICATION"
    r = api_client.post(f"/api/v1/missions/{mid}/cancel/", {"motif": "Abandon"}, format="json")
    assert r.json()["statut"] == "ANNULEE"
    assert r.json()["motif_annulation"] == "Abandon"


def test_suppression_d_un_brouillon_seulement(api_client: APIClient, rai: User) -> None:
    brouillon = MissionFactory()
    lancee = MissionFactory(statut=StatutMission.PLANIFIEE, reference="DAI/2026/M09")
    api_client.force_authenticate(rai)
    assert api_client.delete(f"/api/v1/missions/{brouillon.id}/").status_code == 204
    assert api_client.get(f"/api/v1/missions/{brouillon.id}/").status_code == 404
    assert api_client.delete(f"/api/v1/missions/{lancee.id}/").status_code == 422


def test_issue_order_sans_confirme_400(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["rai"])
    for corps in ({}, {"confirme": False}):
        r = api_client.post(f"/api/v1/missions/{m.id}/issue-order/", corps, format="json")
        assert r.status_code == 400
        assert "confirme" in r.json()["errors"]


def test_pas_de_put(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["rai"])
    assert api_client.put(f"/api/v1/missions/{m.id}/", {}, format="json").status_code == 405


def test_filtres_et_tri_des_missions(api_client: APIClient, rai: User) -> None:
    a = MissionFactory(
        titre="Audit eau",
        statut=StatutMission.PLANIFIEE,
        reference="DAI/2026/M01",
        annee=2026,
        numero=1,
    )
    b = MissionFactory(
        titre="Conseil achats",
        type="CONSEIL",
        statut=StatutMission.PLANIFIEE,
        reference="DAI/2025/M01",
        annee=2025,
        numero=1,
    )
    api_client.force_authenticate(rai)

    def ids(query: str) -> list[str]:
        r = api_client.get(f"/api/v1/missions/?{query}")
        assert r.status_code == 200, r.json()
        return [x["id"] for x in r.json()["results"]]

    assert ids("type=CONSEIL") == [str(b.id)]
    assert ids("annee=2026") == [str(a.id)]
    assert ids("q=achats") == [str(b.id)]
    assert ids("q=DAI/2026") == [str(a.id)]
    assert ids("statut=BROUILLON") == []
    assert ids("ordering=reference") == [str(b.id), str(a.id)]
    assert api_client.get("/api/v1/missions/?processus=pas-un-uuid").status_code == 400


def test_audite_champs_internes_nuls_et_403_sur_etapes(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    audite = users["audite_affecte"]
    api_client.force_authenticate(audite)
    r = api_client.get(f"/api/v1/missions/{m.id}/")
    assert r.status_code == 200
    corps = r.json()
    assert corps["budget_jours"] is None
    assert corps["cartographie"] is None
    assert corps["motif_annulation"] is None
    assert all(a["declaration"] is None for a in corps["equipe"])
    assert corps["mes_droits"]["contribuer"] is False
    for route in (
        f"/api/v1/mission-steps/?mission={m.id}",
        f"/api/v1/missions/{m.id}/tracking/",
        f"/api/v1/missions/{m.id}/risk-matrix/",
        f"/api/v1/mission-risks/?mission={m.id}",
        f"/api/v1/mission-assignments/?mission={m.id}",
        f"/api/v1/independence-declarations/?mission={m.id}",
        f"/api/v1/missions/{m.id}/default-auditees/",
    ):
        assert api_client.get(route).status_code == 403, route


def test_audite_sans_ordre_emis_ne_voit_pas_la_mission(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    Mission.objects.filter(pk=m.pk).update(ordre_mission_emis_le=None)
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.get(f"/api/v1/missions/{m.id}/").status_code == 404


def test_default_auditees_rai_seul(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    direction = DirectionFactory()
    # Les entités ne se modifient plus une fois l'ordre émis (D17) : mission lue en brouillon.
    Mission.objects.filter(pk=m.pk).update(ordre_mission_emis_le=None)
    EtapeMission.objects.filter(mission=m, numero=1).update(statut=StatutEtape.EN_COURS)
    m.entites.add(direction)
    candidat = make_user(Role.AUDITE, direction_code=direction.code)
    make_user(Role.AUDITE, direction_code="AUTRE")
    api_client.force_authenticate(users["rai"])
    r = api_client.get(f"/api/v1/missions/{m.id}/default-auditees/")
    assert r.status_code == 200
    assert [u["id"] for u in r.json()] == [candidat.id]
    api_client.force_authenticate(users["chef"])
    assert api_client.get(f"/api/v1/missions/{m.id}/default-auditees/").status_code == 403


def test_replace_chief(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["rai"])
    nouveau = make_user(Role.AUDITEUR)
    r = api_client.post(
        f"/api/v1/missions/{m.id}/replace-chief/", {"utilisateur": nouveau.id}, format="json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["chef_mission"]["id"] == nouveau.id
    roles = {a["utilisateur"]: a["role_mission"] for a in r.json()["equipe"]}
    assert roles[users["chef"].id] == "AUDITEUR"
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        f"/api/v1/missions/{m.id}/replace-chief/", {"utilisateur": nouveau.id}, format="json"
    )
    assert r.status_code == 403


def test_risk_matrix_et_tracking(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["chef"])
    r = api_client.get(f"/api/v1/missions/{m.id}/risk-matrix/")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert len(r.json()["cellules"]) == 25
    r = api_client.get(f"/api/v1/missions/{m.id}/tracking/")
    assert r.status_code == 200
    assert len(r.json()["lignes"]) == 18


def test_listes_requetes_bornees_missions(
    api_client: APIClient, rai: User, django_assert_max_num_queries
) -> None:
    from tests.factories import EtapeMissionFactory

    auditeur = make_user(Role.AUDITEUR)
    for i in range(1, 31):
        m = MissionFactory(
            statut=StatutMission.EN_PLANIFICATION,
            reference=f"DAI/2026/M{i:02d}",
            annee=2026,
            numero=i,
        )
        EtapeMissionFactory(mission=m, numero=1, statut=StatutEtape.EN_COURS)
        affecter(m, make_user(Role.AUDITEUR), RoleMission.CHEF_MISSION)
        affecter(m, auditeur, RoleMission.AUDITEUR)
    for qui in (rai, auditeur):
        api_client.force_authenticate(qui)
        with django_assert_max_num_queries(6):
            r = api_client.get("/api/v1/missions/?page_size=30")
        assert r.status_code == 200
        assert len(r.json()["results"]) == 30
        assert r.json()["results"][0]["etape_courante"] == {"numero": 1, "romain": "I"}


def test_ma_declaration_en_attente(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.get("/api/v1/missions/")
    assert [x["ma_declaration_en_attente"] for x in r.json()["results"]] == [True]
    api_client.force_authenticate(users["chef"])
    r = api_client.get("/api/v1/missions/")
    assert [x["ma_declaration_en_attente"] for x in r.json()["results"]] == [False]
