import pytest
from rest_framework.test import APIClient

from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from tests.factories import LigneMARCFactory

from .fixtures_api import EquipeVI, equipe_complete, equipe_en_vi, travaux_ouverts  # noqa: F401


@pytest.mark.parametrize(
    ("qui", "lire_marc", "ecrire_marc", "avis"),
    [
        ("rai", 200, 201, 403),
        ("chef", 200, 201, 403),
        ("auditeur_non_confirme", 200, 403, 403),
        ("audite_affecte", 200, 403, 201),
        ("auditeur_non_affecte", 404, 404, 404),
        ("admin", 403, 403, 403),
        ("dg", 403, 403, 403),
    ],
)
def test_matrice_droits_analyse(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
    qui: str,
    lire_marc: int,
    ecrire_marc: int,
    avis: int,
) -> None:
    m, users, risque = equipe_en_vi
    api_client.force_authenticate(users[qui])
    assert api_client.get(f"/api/v1/marc-lines/?mission={m.id}").status_code == lire_marc
    r = api_client.post(
        "/api/v1/marc-lines/", {"mission": str(m.id), "risque": str(risque.id)}, format="json"
    )
    assert r.status_code == ecrire_marc, r.json()
    r = api_client.post(
        f"/api/v1/audit-frameworks/{m.id}/opinions/", {"avis": "ACCORD"}, format="json"
    )
    assert r.status_code == avis, r.json()


def test_audite_avant_diffusion_403_et_synthese_vide(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
) -> None:
    m, users, risque = equipe_en_vi
    with travaux_ouverts(m):
        LigneMARCFactory(mission=m, risque=risque)
    EtapeMission.objects.filter(mission=m, numero=6).update(statut=StatutEtape.A_FAIRE)
    api_client.force_authenticate(users["audite_affecte"])
    r = api_client.get(f"/api/v1/marc-lines/?mission={m.id}")
    assert r.status_code == 403
    assert r.json()["detail"] == "Le référentiel d'audit n'est pas encore diffusé aux audités."
    assert api_client.get(f"/api/v1/strengths-weaknesses/?mission={m.id}").status_code == 403
    r = api_client.get(f"/api/v1/audit-frameworks/{m.id}/")
    assert r.status_code == 200
    corps = r.json()
    assert corps["nb_lignes"] == 0
    assert corps["mes_droits"]["voir_referentiel"] is False
    assert corps["avis"] == []
    assert api_client.get(f"/api/v1/audit-frameworks/{m.id}/snapshot/").status_code == 403


@pytest.mark.parametrize(
    "route",
    ["analysis-questionnaires", "process-descriptions", "segregation-grids", "audit-objectives"],
)
def test_audite_ne_voit_pas_les_travaux(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
    route: str,
) -> None:
    m, users, _ = equipe_en_vi
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.get(f"/api/v1/{route}/?mission={m.id}").status_code == 403


def test_liste_sans_mission_400(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    _, users, _ = equipe_en_vi
    api_client.force_authenticate(users["rai"])
    for route in (
        "analysis-questionnaires",
        "analysis-questions",
        "process-descriptions",
        "segregation-grids",
        "marc-lines",
        "strengths-weaknesses",
        "audit-objectives",
    ):
        r = api_client.get(f"/api/v1/{route}/")
        assert r.status_code == 400, route
        champ = "questionnaire" if route == "analysis-questions" else "mission"
        assert r.json()["errors"][champ] == ["Ce paramètre est obligatoire."]


def test_api_gel_422_sur_chaque_route_analyse(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
) -> None:
    m, users, risque = equipe_en_vi
    with travaux_ouverts(m):
        ligne = LigneMARCFactory(mission=m, risque=risque)
    api_client.force_authenticate(users["chef"])
    corps = {"mission": str(m.id), "risque": str(risque.id)}
    Mission.objects.filter(pk=m.pk).update(
        statut=StatutMission.SUSPENDUE, statut_avant_suspension=StatutMission.EN_PLANIFICATION
    )
    for r in (
        api_client.post("/api/v1/marc-lines/", corps, format="json"),
        api_client.patch(f"/api/v1/marc-lines/{ligne.id}/", {"operation": "X"}, format="json"),
        api_client.delete(f"/api/v1/marc-lines/{ligne.id}/"),
        api_client.post("/api/v1/marc-lines/initialize/", {"mission": str(m.id)}, format="json"),
    ):
        assert r.status_code == 422, r.json()
        assert r.json()["detail"]
    Mission._base_manager.filter(pk=m.pk).update(
        statut=StatutMission.EN_PLANIFICATION, statut_avant_suspension=""
    )
    EtapeMission.objects.filter(mission=m, numero=6).update(statut=StatutEtape.TERMINEE)
    for r in (
        api_client.post("/api/v1/marc-lines/", corps, format="json"),
        api_client.patch(f"/api/v1/marc-lines/{ligne.id}/", {"operation": "X"}, format="json"),
        api_client.delete(f"/api/v1/marc-lines/{ligne.id}/"),
    ):
        assert r.status_code == 422, r.json()
        assert r.json()["detail"]
