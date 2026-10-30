from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.core.gardes_sql import maintenance
from apps.missions.models import (
    DeclarationIndependance,
    EtapeMission,
    Mission,
    StatutMission,
)
from apps.missions.services.etapes import ActionEtape, actions_possibles
from apps.users.models import User

Equipe = tuple[Mission, dict[str, User]]


@pytest.mark.parametrize(
    ("qui", "lire", "ecrire_reunion", "valider_vi"),
    [
        ("rai", 200, 201, 200),
        ("chef", 200, 201, 403),
        ("superviseur", 200, 201, 200),
        ("auditeur_non_confirme", 200, 403, 403),
        ("auditeur_non_affecte", 404, 404, 404),
        ("audite_affecte", 200, 403, 403),
        ("admin", 403, 403, 403),
        ("dg", 403, 403, 403),
    ],
)
def test_matrice_droits_missions(
    api_client: APIClient,
    equipe_complete: Equipe,
    qui: str,
    lire: int,
    ecrire_reunion: int,
    valider_vi: int,
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users[qui])
    assert api_client.get(f"/api/v1/missions/{m.id}/").status_code == lire
    r = api_client.post(
        "/api/v1/meetings/",
        {"mission": str(m.id), "type": "OUVERTURE", "date": "2026-03-02T09:00:00Z"},
        format="json",
    )
    assert r.status_code == ecrire_reunion
    e6 = m.etapes.get(numero=6)
    assert api_client.post(f"/api/v1/mission-steps/{e6.id}/validate/").status_code == valider_vi


def test_non_authentifie_401(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/missions/").status_code == 401


# droit de `mes_droits` -> (méthode, route, corps)
_APPELS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "modifier": ("patch", "/api/v1/missions/{m}/", {"objectifs": "Nouveaux objectifs"}),
    "planifier": ("post", "/api/v1/missions/{m}/plan/", {}),
    "lancer": ("post", "/api/v1/missions/{m}/launch/", {}),
    "emettre_ordre": ("post", "/api/v1/missions/{m}/issue-order/", {"confirme": True}),
    "suspendre": ("post", "/api/v1/missions/{m}/suspend/", {"motif": "Motif"}),
    "reprendre": ("post", "/api/v1/missions/{m}/resume/", {}),
    "annuler": ("post", "/api/v1/missions/{m}/cancel/", {"motif": "Motif"}),
    "supprimer": ("delete", "/api/v1/missions/{m}/", {}),
    "affecter": ("post", "/api/v1/mission-assignments/", {}),
    "contribuer": ("post", "/api/v1/meetings/", {}),
    "voir_travaux": ("get", "/api/v1/missions/{m}/tracking/", {}),
    "confirmer_ma_declaration": ("post", "/api/v1/independence-declarations/{d}/confirm/", {}),
}


@pytest.mark.parametrize("droit", sorted(_APPELS))
@pytest.mark.parametrize(
    "qui", ["rai", "chef", "superviseur", "auditeur_confirme", "auditeur_non_confirme"]
)
def test_mes_droits_concorde_avec_les_permissions(
    api_client: APIClient, equipe_complete: Equipe, qui: str, droit: str
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users[qui])
    vrai = api_client.get(f"/api/v1/missions/{m.id}/").json()["mes_droits"][droit]
    methode, route, corps = _APPELS[droit]
    declaration = (
        DeclarationIndependance.objects.filter(affectation__utilisateur=users[qui]).first()
        or DeclarationIndependance.objects.filter(affectation__mission=m).first()
    )
    assert declaration is not None
    route = route.format(m=m.id, d=declaration.id)
    if droit == "affecter":
        corps = {"mission": str(m.id), "utilisateur": users["admin"].id, "role_mission": "AUDITEUR"}
    if droit == "contribuer":
        corps = {"mission": str(m.id), "type": "OUVERTURE", "date": "2026-03-02T09:00:00Z"}
    if droit == "confirmer_ma_declaration":
        corps = {"confirme": True}
    r = getattr(api_client, methode)(route, corps, format="json")
    if vrai:
        assert r.status_code != 403, (droit, r.json())
    else:
        assert r.status_code in (403, 422), (droit, r.status_code, r.json())


_ACTIONS: dict[str, tuple[str, str]] = {
    ActionEtape.DEMARRER: ("post", "start"),
    ActionEtape.TERMINER: ("post", "complete"),
    ActionEtape.VALIDER: ("post", "validate"),
    ActionEtape.RENVOYER: ("post", "return"),
    ActionEtape.ROUVRIR: ("post", "reopen"),
    ActionEtape.NON_APPLICABLE: ("post", "not-applicable"),
    ActionEtape.RETABLIR: ("post", "restore"),
    ActionEtape.PLANIFIER: ("patch", ""),
}


@pytest.mark.parametrize("action", sorted(_ACTIONS))
@pytest.mark.parametrize("numero", [6, 2])
@pytest.mark.parametrize("qui", ["rai", "chef", "superviseur", "auditeur_confirme"])
def test_actions_possibles_concorde_avec_les_routes(
    api_client: APIClient, equipe_complete: Equipe, qui: str, numero: int, action: str
) -> None:
    m, users = equipe_complete
    etape = EtapeMission.objects.get(mission=m, numero=numero)
    api_client.force_authenticate(users[qui])
    possibles = actions_possibles(etape, users[qui])
    detail = api_client.get(f"/api/v1/mission-steps/{etape.id}/").json()
    assert detail["actions_possibles"] == possibles
    _, suffixe = _ACTIONS[action]
    r = api_client.generic(
        "PATCH" if action == ActionEtape.PLANIFIER else "POST",
        f"/api/v1/mission-steps/{etape.id}/{suffixe + '/' if suffixe else ''}",
        '{"motif": "Motif"}',
        content_type="application/json",
    )
    if action in possibles:
        assert r.status_code != 403, (action, r.json())
    else:
        assert r.status_code in (403, 422), (action, r.status_code, r.json())


@pytest.mark.parametrize(
    ("methode", "route"),
    [
        ("post", "/api/v1/meetings/"),
        ("post", "/api/v1/interviews/"),
        ("post", "/api/v1/mission-risks/"),
        ("post", "/api/v1/mission-assignments/"),
    ],
)
def test_api_gel_422_sur_creation_enfant(
    api_client: APIClient, equipe_complete: Equipe, methode: str, route: str
) -> None:
    m, users = equipe_complete
    Mission.objects.filter(pk=m.pk).update(
        statut=StatutMission.SUSPENDUE, statut_avant_suspension=StatutMission.EN_PLANIFICATION
    )
    api_client.force_authenticate(users["rai"])
    corps: dict[str, Any] = {"mission": str(m.id)}
    if "meetings" in route:
        corps |= {"type": "OUVERTURE", "date": "2026-03-02T09:00:00Z"}
    elif "interviews" in route:
        corps |= {"objet": "Entretien", "date_prevue": "2026-03-03T09:00:00Z"}
    elif "mission-risks" in route:
        corps |= {
            "processus": str(m.processus.first().id),
            "libelle": "R",
            "probabilite": 2,
            "impact": 2,
        }
    else:
        corps |= {"utilisateur": users["auditeur_non_affecte"].id, "role_mission": "AUDITEUR"}
    r = api_client.post(route, corps, format="json")
    assert r.status_code == 422, r.json()
    assert "suspendue" in r.json()["detail"]


def test_api_gel_422_sur_modifications_et_actions(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    from tests.factories import EntretienFactory, ReunionFactory, RisqueMissionFactory

    m, users = equipe_complete
    reunion = ReunionFactory(mission=m, type="LANCEMENT", compte_rendu="CR")
    entretien = EntretienFactory(mission=m, compte_rendu="CR")
    risque = RisqueMissionFactory(mission=m, processus=m.processus.first())
    Mission.objects.filter(pk=m.pk).update(
        statut=StatutMission.SUSPENDUE, statut_avant_suspension=StatutMission.EN_PLANIFICATION
    )
    api_client.force_authenticate(users["rai"])
    e2 = EtapeMission.objects.get(mission=m, numero=2)
    e3 = EtapeMission.objects.get(mission=m, numero=3)
    e6 = EtapeMission.objects.get(mission=m, numero=6)
    affectation = m.affectations.get(utilisateur=users["auditeur_confirme"])
    appels = [
        ("patch", f"/api/v1/meetings/{reunion.id}/", {"lieu": "X"}),
        ("delete", f"/api/v1/meetings/{reunion.id}/", None),
        ("patch", f"/api/v1/interviews/{entretien.id}/", {"lieu": "X"}),
        ("delete", f"/api/v1/interviews/{entretien.id}/", None),
        ("patch", f"/api/v1/mission-risks/{risque.id}/", {"commentaire": "X"}),
        ("delete", f"/api/v1/mission-risks/{risque.id}/", None),
        ("delete", f"/api/v1/mission-assignments/{affectation.id}/", None),
        ("patch", f"/api/v1/mission-steps/{e2.id}/", {"charge_prevue_jours": "1.0"}),
        ("post", f"/api/v1/mission-steps/{e2.id}/start/", None),
        ("post", f"/api/v1/mission-steps/{e2.id}/reopen/", {"motif": "m"}),
        ("post", f"/api/v1/mission-steps/{e2.id}/complete/", None),
        ("post", f"/api/v1/mission-steps/{e6.id}/validate/", None),
        ("post", f"/api/v1/mission-steps/{e6.id}/return/", {"motif": "m"}),
        ("post", f"/api/v1/mission-steps/{e3.id}/not-applicable/", {"motif": "m"}),
        ("post", f"/api/v1/mission-steps/{e3.id}/restore/", None),
        ("post", f"/api/v1/meetings/{reunion.id}/mark-held/", None),
        ("post", f"/api/v1/interviews/{entretien.id}/mark-done/", None),
        ("post", f"/api/v1/interviews/{entretien.id}/cancel/", {"motif": "m"}),
        ("post", f"/api/v1/missions/{m.id}/issue-order/", {"confirme": True}),
        ("post", f"/api/v1/missions/{m.id}/suspend/", {"motif": "m"}),
        ("post", f"/api/v1/missions/{m.id}/launch/", None),
        ("post", f"/api/v1/missions/{m.id}/plan/", None),
        ("patch", f"/api/v1/missions/{m.id}/", {"budget_jours": "3.0"}),
    ]
    chef_seul = ("/complete/", "/not-applicable/", "/restore/")
    for methode, route, corps in appels:
        # Le droit est contrôlé avant l'état : ces actions sont celles du chef de mission.
        api_client.force_authenticate(users["chef" if route.endswith(chef_seul) else "rai"])
        r = getattr(api_client, methode)(route, corps, format="json")
        assert r.status_code == 422, (methode, route, r.status_code, r.json())
        assert "suspendue" in r.json()["detail"], (methode, route, r.json())


def test_erreurs_au_format_unique(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    # 404 d'une mission invisible
    api_client.force_authenticate(users["auditeur_non_affecte"])
    r = api_client.get(f"/api/v1/missions/{m.id}/")
    assert r.status_code == 404
    assert set(r.json()) == {"detail", "errors"}
    # 400 : identifiant invalide dans une liste
    api_client.force_authenticate(users["rai"])
    r = api_client.post(
        "/api/v1/missions/",
        {"titre": "T", "type": "ASSURANCE", "processus": ["pas-un-uuid"]},
        format="json",
    )
    assert r.status_code == 400
    assert "processus.0" in r.json()["errors"]
    # 422 : aucune cartographie validée
    from apps.referentiel.models import CartographieVersion

    with maintenance():
        CartographieVersion._base_manager.all().update(statut="BROUILLON")
    r = api_client.post("/api/v1/missions/", {"titre": "T", "type": "ASSURANCE"}, format="json")
    assert r.status_code == 422
    assert "cartographie" in r.json()["errors"]
    # 403 non confirmé
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.post(
        "/api/v1/meetings/",
        {"mission": str(m.id), "type": "OUVERTURE", "date": "2026-03-02T09:00:00Z"},
        format="json",
    )
    assert r.status_code == 403
    assert set(r.json()) == {"detail", "errors"}
    assert "Confirmez votre déclaration" in r.json()["detail"]
