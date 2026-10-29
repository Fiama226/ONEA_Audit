from rest_framework.test import APIClient

from apps.analyse.models import ObjectifAudit
from apps.missions.models import EtapeMission, StatutEtape

from .fixtures_api import EquipeVI, equipe_complete, equipe_en_vii  # noqa: F401


def test_objectifs_initialize_cycle_et_filtres(
    api_client: APIClient,
    equipe_en_vii: EquipeVI,  # noqa: F811
) -> None:
    m, users, _ = equipe_en_vii
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/audit-objectives/initialize/", {"mission": str(m.id)}, format="json"
    )
    assert r.status_code == 200, r.json()
    assert len(r.json()) == 1
    objectif = r.json()[0]
    assert objectif["code"] == "OA-01"
    assert objectif["numero"] == 1
    assert objectif["retenu"] is True
    assert objectif["controle_existant"] == "Double signature."
    oid = objectif["id"]
    # Non retenu sans motif : 422 sur le champ.
    r = api_client.patch(f"/api/v1/audit-objectives/{oid}/", {"retenu": False}, format="json")
    assert r.status_code == 422
    assert "motif_non_test" in r.json()["errors"]
    r = api_client.patch(
        f"/api/v1/audit-objectives/{oid}/",
        {"retenu": False, "motif_non_test": "AUTRES_CONTROLES", "justification": "Couvert."},
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert (
        api_client.get(f"/api/v1/audit-objectives/?mission={m.id}&retenu=false").json()["count"]
        == 1
    )
    assert (
        api_client.get(f"/api/v1/audit-objectives/?mission={m.id}&retenu=true").json()["count"] == 0
    )
    r = api_client.patch(f"/api/v1/audit-objectives/{oid}/", {"numero": 9}, format="json")
    assert r.status_code == 200  # numéro en lecture seule : ignoré
    assert r.json()["numero"] == 1
    assert api_client.delete(f"/api/v1/audit-objectives/{oid}/").status_code == 204


def test_objectif_creation_vi_non_validee_422(
    api_client: APIClient,
    equipe_en_vii: EquipeVI,  # noqa: F811
) -> None:
    m, users, _ = equipe_en_vii
    EtapeMission.objects.filter(mission=m, numero=6).update(statut=StatutEtape.TERMINEE)
    api_client.force_authenticate(users["rai"])
    r = api_client.post(
        "/api/v1/audit-objectives/initialize/", {"mission": str(m.id)}, format="json"
    )
    assert r.status_code == 422
    assert "validé" in r.json()["detail"]


def test_rapport_orientation_lecture_vide_puis_patch(
    api_client: APIClient,
    equipe_en_vii: EquipeVI,  # noqa: F811
) -> None:
    m, users, _ = equipe_en_vii
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.get(f"/api/v1/orientation-reports/{m.id}/")
    assert r.status_code == 200
    assert r.json()["variante"] == "COMPLET"
    assert r.json()["rappel_ordre"]["objectifs"] == m.objectifs
    assert r.json()["etape_close"] is False
    assert (
        api_client.patch(
            f"/api/v1/orientation-reports/{m.id}/", {"contexte": "X"}, format="json"
        ).status_code
        == 403
    )
    api_client.force_authenticate(users["chef"])
    r = api_client.patch(
        f"/api/v1/orientation-reports/{m.id}/",
        {"contexte": "Contexte.", "couverture_ordre": "PARTIELLE"},
        format="json",
    )
    assert r.status_code == 422
    assert "justification_couverture" in r.json()["errors"]
    r = api_client.patch(
        f"/api/v1/orientation-reports/{m.id}/",
        {
            "contexte": "Contexte.",
            "couverture_ordre": "PARTIELLE",
            "justification_couverture": "Exclusion justifiée.",
        },
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert r.json()["contexte"] == "Contexte."
    assert api_client.get(f"/api/v1/orientation-reports/{m.id}/").json()["couverture_ordre"] == (
        "PARTIELLE"
    )
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.get(f"/api/v1/orientation-reports/{m.id}/").status_code == 403


def test_creation_objectif_invalide_est_atomique(
    api_client: APIClient,
    equipe_en_vii: EquipeVI,  # noqa: F811
) -> None:
    """Un 422 à la création ne laisse aucun objectif et ne consomme pas le numéro."""
    m, users, _ = equipe_en_vii
    ligne = m.lignes_marc.get()
    api_client.force_authenticate(users["chef"])
    corps = {"mission": str(m.id), "ligne_marc": str(ligne.id)}
    r = api_client.post("/api/v1/audit-objectives/", {**corps, "retenu": False}, format="json")
    assert r.status_code == 422
    assert "motif_non_test" in r.json()["errors"]
    assert ObjectifAudit.all_objects.filter(mission=m).count() == 0
    r = api_client.post("/api/v1/audit-objectives/", corps, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["numero"] == 1
