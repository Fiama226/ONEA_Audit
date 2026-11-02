from rest_framework.test import APIClient

from apps.missions.models import DeclarationIndependance, Mission, RoleMission, StatutDeclaration
from apps.signatures.models import Confirmation
from apps.users.models import Role, User
from tests.factories import make_user

from .conftest import affecter

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


def test_affecter_un_responsable_de_l_entite(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["rai"])
    audite = make_user(Role.AUDITE, direction_code="DEX")
    corps = {
        "mission": str(m.id),
        "utilisateur": audite.id,
        "role_mission": "AUDITE",
        "responsable_entite": True,
    }
    r = api_client.post("/api/v1/mission-assignments/", corps, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["responsable_entite"] is True
    # Valeur par défaut : faux.
    autre = make_user(Role.AUDITE, direction_code="DAF")
    corps2 = {"mission": str(m.id), "utilisateur": autre.id, "role_mission": "AUDITE"}
    assert (
        api_client.post("/api/v1/mission-assignments/", corps2, format="json").json()[
            "responsable_entite"
        ]
        is False
    )
    # Second responsable de la même direction : erreur rattachée au champ.
    collegue = make_user(Role.AUDITE, direction_code="DEX")
    corps3 = {**corps, "utilisateur": collegue.id}
    r3 = api_client.post("/api/v1/mission-assignments/", corps3, format="json")
    assert r3.status_code == 422
    assert "responsable_entite" in r3.json()["errors"]
    # Réservé aux audités.
    corps4 = {**corps, "utilisateur": make_user(Role.AUDITEUR).id, "role_mission": "AUDITEUR"}
    r4 = api_client.post("/api/v1/mission-assignments/", corps4, format="json")
    assert r4.status_code == 422
    assert "responsable_entite" in r4.json()["errors"]


def test_modifier_le_responsable_de_l_entite(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    audite = make_user(Role.AUDITE, direction_code="DEX")
    affectation = affecter(m, audite, RoleMission.AUDITE, responsable_entite=False)
    url = f"/api/v1/mission-assignments/{affectation.id}/"
    for qui, statut in (("chef", 403), ("audite_affecte", 403), ("auditeur_non_affecte", 404)):
        api_client.force_authenticate(users[qui])
        r = api_client.patch(url, {"responsable_entite": True}, format="json")
        assert r.status_code == statut, (qui, r.status_code)
    api_client.force_authenticate(users["rai"])
    r = api_client.patch(url, {"responsable_entite": True}, format="json")
    assert r.status_code == 200, r.json()
    assert r.json()["responsable_entite"] is True
    # Les autres champs ne se modifient pas par PATCH.
    r = api_client.patch(url, {"role_mission": "AUDITEUR"}, format="json")
    assert r.status_code == 200
    assert r.json()["role_mission"] == "AUDITE"
    # Corps invalide : 400 ; second responsable : 422 sur le champ.
    assert api_client.patch(url, {"responsable_entite": "x"}, format="json").status_code == 400
    collegue = affecter(
        m,
        make_user(Role.AUDITE, direction_code="DEX"),
        RoleMission.AUDITE,
        responsable_entite=False,
    )
    r = api_client.patch(
        f"/api/v1/mission-assignments/{collegue.id}/", {"responsable_entite": True}, format="json"
    )
    assert r.status_code == 422
    assert "responsable_entite" in r.json()["errors"]
