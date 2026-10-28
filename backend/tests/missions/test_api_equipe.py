from rest_framework.test import APIClient

from apps.missions.models import DeclarationIndependance, Mission, StatutDeclaration
from apps.signatures.models import Confirmation
from apps.users.models import Role, User
from tests.factories import make_user

Equipe = tuple[Mission, dict[str, User]]


def _declaration(m: Mission, user: User) -> DeclarationIndependance:
    return DeclarationIndependance.objects.get(
        affectation__mission=m, affectation__utilisateur=user
    )


def test_affectations_lecture_filtres(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["chef"])
    r = api_client.get(f"/api/v1/mission-assignments/?mission={m.id}")
    assert r.status_code == 200
    assert r.json()["count"] == 5
    r = api_client.get("/api/v1/mission-assignments/?role_mission=SUPERVISEUR")
    assert [a["utilisateur"] for a in r.json()["results"]] == [users["superviseur"].id]
    api_client.force_authenticate(users["auditeur_non_affecte"])
    assert api_client.get("/api/v1/mission-assignments/").json()["count"] == 0


def test_affectation_ecriture_rai_seul(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    nouveau = make_user(Role.AUDITEUR)
    corps = {"mission": str(m.id), "utilisateur": nouveau.id, "role_mission": "AUDITEUR"}
    api_client.force_authenticate(users["chef"])
    assert api_client.post("/api/v1/mission-assignments/", corps, format="json").status_code == 403
    api_client.force_authenticate(users["auditeur_non_affecte"])
    assert api_client.post("/api/v1/mission-assignments/", corps, format="json").status_code == 404
    api_client.force_authenticate(users["rai"])
    r = api_client.post("/api/v1/mission-assignments/", corps, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["utilisateur_detail"]["id"] == nouveau.id
    # Règle métier : un utilisateur n'est affecté qu'une fois.
    r2 = api_client.post("/api/v1/mission-assignments/", corps, format="json")
    assert r2.status_code == 422
    assert "utilisateur" in r2.json()["errors"]
    # Mission absente ou illisible : 400, jamais 404.
    r3 = api_client.post(
        "/api/v1/mission-assignments/",
        {"utilisateur": nouveau.id, "role_mission": "AUDITEUR"},
        format="json",
    )
    assert r3.status_code == 400
    r4 = api_client.delete(f"/api/v1/mission-assignments/{r.json()['id']}/")
    assert r4.status_code == 204
    assert api_client.get(f"/api/v1/mission-assignments/{r.json()['id']}/").status_code == 404


def test_declarations_liste_mine_statut(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.get("/api/v1/independence-declarations/?mine=true&statut=EN_ATTENTE")
    assert r.status_code == 200
    assert r.json()["count"] == 1
    declaration = r.json()["results"][0]
    assert declaration["mission_reference"] == "DAI/2026/M01"
    assert declaration["texte"].startswith("Je soussigné(e)")
    assert declaration["confirmation"] is None
    assert (
        api_client.get("/api/v1/independence-declarations/?mine=true&statut=CONFIRMEE").json()[
            "count"
        ]
        == 0
    )
    api_client.force_authenticate(users["rai"])
    assert api_client.get(f"/api/v1/independence-declarations/?mission={m.id}").json()["count"] == 4


def test_confirm_declaration_puis_affichage(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    declaration = _declaration(m, users["auditeur_non_confirme"])
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.post(
        f"/api/v1/independence-declarations/{declaration.id}/confirm/",
        {"confirme": True},
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert r.json()["statut"] == "CONFIRMEE"
    assert r.json()["levee"] is True
    assert r.json()["confirmation"]["type_document"] == "DECLARATION_INDEPENDANCE"
    assert Confirmation.objects.filter(object_id=declaration.id).count() == 1
    # La confirmation apparaît dans l'équipe de la mission.
    r = api_client.get(f"/api/v1/missions/{m.id}/")
    declarations = [a["declaration"] for a in r.json()["equipe"] if a["declaration"]]
    assert all(
        d["confirmee_le"] is not None for d in declarations if d["id"] == str(declaration.id)
    )
    assert r.json()["mes_droits"]["confirmer_ma_declaration"] is False


def test_confirm_declaration_sans_confirme_400(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    declaration = _declaration(m, users["auditeur_non_confirme"])
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.post(
        f"/api/v1/independence-declarations/{declaration.id}/confirm/",
        {"confirme": False},
        format="json",
    )
    assert r.status_code == 400


def test_confirm_declaration_d_un_autre_403(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    declaration = _declaration(m, users["auditeur_non_confirme"])
    for qui in ("rai", "chef"):
        api_client.force_authenticate(users[qui])
        r = api_client.post(
            f"/api/v1/independence-declarations/{declaration.id}/confirm/",
            {"confirme": True},
            format="json",
        )
        assert r.status_code == 403, qui
    declaration.refresh_from_db()
    assert declaration.statut == StatutDeclaration.EN_ATTENTE


def test_conflit_puis_arbitrage(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    declaration = _declaration(m, users["auditeur_non_confirme"])
    api_client.force_authenticate(users["auditeur_non_confirme"])
    sans_description = {"confirme": True, "conflit": True}
    r = api_client.post(
        f"/api/v1/independence-declarations/{declaration.id}/confirm/",
        sans_description,
        format="json",
    )
    assert r.status_code == 422
    r = api_client.post(
        f"/api/v1/independence-declarations/{declaration.id}/confirm/",
        {**sans_description, "description_conflit": "Parent dans l'entité."},
        format="json",
    )
    assert r.json()["statut"] == "CONFLIT_DECLARE"
    assert r.json()["levee"] is False
    api_client.force_authenticate(users["chef"])
    route = f"/api/v1/independence-declarations/{declaration.id}/arbitrate/"
    assert api_client.post(route, {"justification": "ok"}, format="json").status_code == 403
    api_client.force_authenticate(users["rai"])
    assert api_client.post(route, {}, format="json").status_code == 400
    r = api_client.post(route, {"justification": "Risque maîtrisé."}, format="json")
    assert r.status_code == 200, r.json()
    assert r.json()["levee"] is True
    assert r.json()["arbitre_par"]["id"] == users["rai"].id
