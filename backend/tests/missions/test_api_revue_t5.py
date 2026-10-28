"""Corrections de la revue de la tâche 5 : ordre des refus, filtres booléens, comptes actifs."""

import pytest
from rest_framework.test import APIClient

from apps.missions.models import EtapeMission, Mission
from apps.users.models import Role, User
from tests.factories import EntretienFactory, RisqueMissionFactory, make_user

Equipe = tuple[Mission, dict[str, User]]


@pytest.mark.parametrize(
    ("suffixe", "autorise"),
    [("return", "rai"), ("reopen", "rai"), ("not-applicable", "chef")],
)
def test_m1_role_verifie_avant_le_corps_sur_les_actions_a_motif(
    api_client: APIClient, equipe_complete: Equipe, suffixe: str, autorise: str
) -> None:
    m, users = equipe_complete
    etape = EtapeMission.objects.get(mission=m, numero=6)
    # Un auditeur simple n'a aucun de ces droits : 403 même avec un corps invalide.
    api_client.force_authenticate(users["auditeur_confirme"])
    r = api_client.post(f"/api/v1/mission-steps/{etape.id}/{suffixe}/", {}, format="json")
    assert r.status_code == 403, r.json()
    # Le corps n'est examiné que pour qui a le droit.
    api_client.force_authenticate(users[autorise])
    r = api_client.post(f"/api/v1/mission-steps/{etape.id}/{suffixe}/", {}, format="json")
    assert r.status_code == 400, r.json()


def test_m1_role_verifie_avant_le_corps_sur_le_patch_d_etape(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    etape = EtapeMission.objects.get(mission=m, numero=3)
    corps = {"date_debut_prevue": "pas-une-date"}
    api_client.force_authenticate(users["auditeur_confirme"])
    assert (
        api_client.patch(f"/api/v1/mission-steps/{etape.id}/", corps, format="json").status_code
        == 403
    )
    api_client.force_authenticate(users["chef"])
    assert (
        api_client.patch(f"/api/v1/mission-steps/{etape.id}/", corps, format="json").status_code
        == 400
    )


def test_m4_filtres_booleens_acceptent_1_et_true(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["auditeur_non_confirme"])
    for valeur in ("1", "true", "True"):
        r = api_client.get(f"/api/v1/independence-declarations/?mine={valeur}")
        assert r.json()["count"] == 1, valeur
    assert api_client.get("/api/v1/independence-declarations/").json()["count"] == 4
    assert api_client.get("/api/v1/independence-declarations/?mine=false").json()["count"] == 4
    RisqueMissionFactory(mission=m, processus=m.processus.first())
    api_client.force_authenticate(users["rai"])
    for valeur in ("1", "true", "True"):
        r = api_client.get(f"/api/v1/mission-risks/?nouveau={valeur}&mission={m.id}")
        assert r.json()["count"] == 1, valeur
        r = api_client.get(f"/api/v1/mission-risks/?nouveau={valeur}")
        assert r.json()["count"] == 1, valeur
    r = api_client.get(f"/api/v1/mission-risks/?nouveau=false&mission={m.id}")
    assert r.json()["count"] == 0


def test_m6_comptes_desactives_refuses_partout(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    inactif = make_user(Role.AUDITEUR, is_active=False)
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/meetings/",
        {
            "mission": str(m.id),
            "type": "OUVERTURE",
            "date": "2026-03-02T09:00:00Z",
            "participants": [inactif.id],
        },
        format="json",
    )
    assert r.status_code == 400
    assert "participants.0" in r.json()["errors"]
    r = api_client.post(
        "/api/v1/interviews/",
        {
            "mission": str(m.id),
            "objet": "E",
            "date_prevue": "2026-03-04T09:00:00Z",
            "interlocuteurs": [inactif.id],
        },
        format="json",
    )
    assert r.status_code == 400
    assert "interlocuteurs.0" in r.json()["errors"]
    r = api_client.post(
        "/api/v1/interviews/",
        {
            "mission": str(m.id),
            "objet": "E",
            "date_prevue": "2026-03-04T09:00:00Z",
            "auditeurs": [inactif.id],
        },
        format="json",
    )
    assert r.status_code == 400
    assert "auditeurs.0" in r.json()["errors"]
    api_client.force_authenticate(users["rai"])
    r = api_client.post(
        "/api/v1/mission-assignments/",
        {"mission": str(m.id), "utilisateur": inactif.id, "role_mission": "AUDITEUR"},
        format="json",
    )
    assert r.status_code == 400
    r = api_client.post(
        f"/api/v1/missions/{m.id}/replace-chief/", {"utilisateur": inactif.id}, format="json"
    )
    assert r.status_code == 400


def test_m7_budget_nul_coherent_entre_schema_et_validation(
    api_client: APIClient, rai: User
) -> None:
    from tests.factories import MissionFactory

    MissionFactory()
    api_client.force_authenticate(rai)
    r = api_client.post(
        "/api/v1/missions/",
        {"titre": "T", "type": "ASSURANCE", "budget_jours": None},
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["budget_jours"] == "0.0"
    r = api_client.patch(
        f"/api/v1/missions/{r.json()['id']}/", {"budget_jours": "5.0"}, format="json"
    )
    assert r.json()["budget_jours"] == "5.0"
    r = api_client.patch(
        f"/api/v1/missions/{r.json()['id']}/", {"budget_jours": None}, format="json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["budget_jours"] == "0.0"


def test_m2_la_creation_documente_le_404(api_client: APIClient) -> None:
    import yaml

    schema = yaml.safe_load(api_client.get("/api/schema/").content)
    for chemin in ("/api/v1/meetings/", "/api/v1/interviews/", "/api/v1/mission-risks/"):
        assert "404" in schema["paths"][chemin]["post"]["responses"], chemin


def test_m8_budget_requetes_entretiens_cote_audite(
    api_client: APIClient, equipe_complete: Equipe, django_assert_max_num_queries
) -> None:
    m, users = equipe_complete
    for _ in range(6):
        entretien = EntretienFactory(mission=m)
        entretien.auditeurs.add(users["chef"])
        entretien.interlocuteurs.add(users["audite_affecte"])
    api_client.force_authenticate(users["audite_affecte"])
    with django_assert_max_num_queries(5):
        r = api_client.get(f"/api/v1/interviews/?mission={m.id}")
    assert r.status_code == 200
    assert r.json()["count"] == 6
