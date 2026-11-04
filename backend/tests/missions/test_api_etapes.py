from rest_framework.test import APIClient

from apps.missions.models import (
    DeclarationIndependance,
    EtapeMission,
    Mission,
    StatutDeclaration,
    StatutEtape,
)
from apps.users.models import User

Equipe = tuple[Mission, dict[str, User]]


def test_mission_steps_sans_mission_400_et_18_lignes(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["chef"])
    r = api_client.get("/api/v1/mission-steps/")
    assert r.status_code == 400
    assert "mission" in r.json()["errors"]
    assert api_client.get("/api/v1/mission-steps/?mission=nope").status_code == 400
    r = api_client.get(f"/api/v1/mission-steps/?mission={m.id}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert [e["numero"] for e in r.json()] == list(range(1, 19))
    assert r.json()[5]["romain"] == "VI"
    assert r.json()[5]["jalon"] is True
    assert r.json()[0]["evenements"] == []
    assert r.json()[0]["livrables_manquants"] == []
    api_client.force_authenticate(users["auditeur_non_affecte"])
    assert api_client.get(f"/api/v1/mission-steps/?mission={m.id}").status_code == 404


def test_liste_des_etapes_requetes_bornees(
    api_client: APIClient, equipe_complete: Equipe, django_assert_max_num_queries
) -> None:
    m, users = equipe_complete
    for qui in ("rai", "chef", "auditeur_confirme"):
        api_client.force_authenticate(users[qui])
        with django_assert_max_num_queries(4):
            r = api_client.get(f"/api/v1/mission-steps/?mission={m.id}")
        assert r.status_code == 200


def test_detail_etape_livrables_et_evenements(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["chef"])
    e2 = EtapeMission.objects.get(mission=m, numero=2)
    r = api_client.post(f"/api/v1/mission-steps/{e2.id}/start/")
    assert r.status_code == 422  # une déclaration d'indépendance est en attente
    DeclarationIndependance.objects.filter(statut=StatutDeclaration.EN_ATTENTE).update(
        statut=StatutDeclaration.CONFIRMEE
    )
    r = api_client.post(f"/api/v1/mission-steps/{e2.id}/start/")
    assert r.status_code == 200, r.json()
    assert r.json()["statut"] == "EN_COURS"
    assert [e["type"] for e in r.json()["evenements"]] == ["DEMARREE"]
    assert r.json()["evenements"][0]["par"]["id"] == users["chef"].id
    assert (
        "La réunion d'ouverture n'est pas marquée comme tenue." in r.json()["livrables_manquants"]
    )
    r = api_client.post(f"/api/v1/mission-steps/{e2.id}/complete/")
    assert r.status_code == 422
    assert r.json()["errors"]["livrables"]


def test_planification_d_une_etape(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    e3 = EtapeMission.objects.get(mission=m, numero=3)
    corps = {
        "date_debut_prevue": "2026-03-02",
        "date_fin_prevue": "2026-03-06",
        "charge_prevue_jours": "4.5",
    }
    api_client.force_authenticate(users["auditeur_confirme"])
    assert (
        api_client.patch(f"/api/v1/mission-steps/{e3.id}/", corps, format="json").status_code == 403
    )
    api_client.force_authenticate(users["chef"])
    r = api_client.patch(f"/api/v1/mission-steps/{e3.id}/", corps, format="json")
    assert r.status_code == 200, r.json()
    assert r.json()["charge_prevue_jours"] == "4.5"
    # Les champs en lecture seule ne s'écrivent pas par PATCH.
    r = api_client.patch(f"/api/v1/mission-steps/{e3.id}/", {"statut": "VALIDEE"}, format="json")
    assert r.status_code == 200
    assert r.json()["statut"] == "A_FAIRE"
    r = api_client.patch(
        f"/api/v1/mission-steps/{e3.id}/",
        {"date_debut_prevue": "2026-03-09", "date_fin_prevue": "2026-03-06"},
        format="json",
    )
    assert r.status_code == 422


def test_valider_un_jalon_puis_renvoyer_et_rouvrir(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    e6 = EtapeMission.objects.get(mission=m, numero=6)
    api_client.force_authenticate(users["rai"])
    assert (
        api_client.post(f"/api/v1/mission-steps/{e6.id}/return/", {}, format="json").status_code
        == 400
    )
    r = api_client.post(
        f"/api/v1/mission-steps/{e6.id}/return/", {"motif": "Incomplet"}, format="json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["statut"] == StatutEtape.RENVOYEE
    assert r.json()["evenements"][-1]["motif"] == "Incomplet"
    EtapeMission.objects.filter(pk=e6.pk).update(statut=StatutEtape.TERMINEE)
    r = api_client.post(f"/api/v1/mission-steps/{e6.id}/validate/")
    assert r.status_code == 200
    assert r.json()["validee_par"]["id"] == users["rai"].id
    r = api_client.post(
        f"/api/v1/mission-steps/{e6.id}/reopen/", {"motif": "Erreur"}, format="json"
    )
    assert r.json()["statut"] == "EN_COURS"


def test_non_applicable_conseil_seulement(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    e3 = EtapeMission.objects.get(mission=m, numero=3)
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        f"/api/v1/mission-steps/{e3.id}/not-applicable/", {"motif": "Sans objet"}, format="json"
    )
    assert r.status_code == 422
    Mission._base_manager.filter(pk=m.pk).update(type="CONSEIL")  # noqa: SLF001
    r = api_client.post(
        f"/api/v1/mission-steps/{e3.id}/not-applicable/", {"motif": "Sans objet"}, format="json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["motif_non_applicable"] == "Sans objet"
    r = api_client.post(f"/api/v1/mission-steps/{e3.id}/restore/")
    assert r.json()["statut"] == "A_FAIRE"


def test_audite_affecte_lit_les_etapes_sans_journal_ni_action(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    """L'audité charge le plan d'actions : la liste des étapes lui est ouverte en lecture seule."""
    m, users = equipe_complete
    api_client.force_authenticate(users["audite_affecte"])
    r = api_client.get(f"/api/v1/mission-steps/?mission={m.id}")
    assert r.status_code == 200, r.content
    assert [e["numero"] for e in r.json()] == list(range(1, 19))
    assert all(e["actions_possibles"] == [] for e in r.json())
    etape = EtapeMission.objects.get(mission=m, numero=2)
    detail = api_client.get(f"/api/v1/mission-steps/{etape.id}/")
    assert detail.status_code == 200
    assert detail.json()["evenements"] == []
    assert api_client.post(f"/api/v1/mission-steps/{etape.id}/start/").status_code == 403
    assert api_client.patch(f"/api/v1/mission-steps/{etape.id}/", {}).status_code == 403


def test_audite_non_affecte_ne_voit_pas_les_etapes(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["auditeur_non_affecte"])
    assert api_client.get(f"/api/v1/mission-steps/?mission={m.id}").status_code == 404
