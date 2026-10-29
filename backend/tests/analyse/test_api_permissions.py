from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.analyse.models import EvaluationConception
from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from tests.factories import (
    DescriptionProcessusFactory,
    ForceFaiblesseFactory,
    GrilleSeparationFactory,
    LigneMARCFactory,
    ObjectifAuditFactory,
    QuestionFactory,
    QuestionnaireFactory,
)

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


@pytest.fixture
def travaux_complets(equipe_en_vi: EquipeVI) -> dict[str, Any]:  # noqa: F811
    """Un objet de chaque type, pour viser chaque route d'écriture."""
    m, users, risque = equipe_en_vi
    processus = m.processus.first()
    assert processus is not None
    with travaux_ouverts(m):
        questionnaire = QuestionnaireFactory(mission=m)
        ligne = LigneMARCFactory(
            mission=m,
            risque=risque,
            controle_existant="Double signature.",
            evaluation=EvaluationConception.ADEQUATE,
            cle=True,
        )
        objets = {
            "m": m,
            "users": users,
            "risque": risque,
            "processus": processus,
            "questionnaire": questionnaire,
            "question": QuestionFactory(questionnaire=questionnaire),
            "description": DescriptionProcessusFactory(mission=m, processus=processus),
            "grille": GrilleSeparationFactory(mission=m, processus=processus),
            "ligne": ligne,
            "ff": ForceFaiblesseFactory(mission=m),
            "objectif": ObjectifAuditFactory(mission=m, ligne_marc=ligne),
        }
    return objets


def _routes(o: dict[str, Any]) -> list[tuple[str, str, str, dict[str, Any]]]:
    """(qui, méthode, url, corps) de chaque route d'écriture de l'API d'analyse."""
    m = str(o["m"].id)
    p = str(o["processus"].id)
    api = "/api/v1"
    return [
        ("chef", "post", f"{api}/analysis-questionnaires/", {"mission": m, "type": "QCI"}),
        (
            "chef",
            "patch",
            f"{api}/analysis-questionnaires/{o['questionnaire'].id}/",
            {"titre": "X"},
        ),
        ("chef", "delete", f"{api}/analysis-questionnaires/{o['questionnaire'].id}/", {}),
        (
            "chef",
            "post",
            f"{api}/analysis-questions/",
            {"questionnaire": str(o["questionnaire"].id), "theme": "T", "libelle": "Q ?"},
        ),
        ("chef", "patch", f"{api}/analysis-questions/{o['question'].id}/", {"theme": "Z"}),
        ("chef", "delete", f"{api}/analysis-questions/{o['question'].id}/", {}),
        (
            "chef",
            "post",
            f"{api}/process-descriptions/",
            {"mission": m, "processus": p, "description": "X"},
        ),
        ("chef", "patch", f"{api}/process-descriptions/{o['description'].id}/", {"objectifs": "X"}),
        ("chef", "delete", f"{api}/process-descriptions/{o['description'].id}/", {}),
        (
            "chef",
            "post",
            f"{api}/segregation-grids/",
            {"mission": m, "processus": p, "taches": ["A"], "acteurs": ["B"]},
        ),
        ("chef", "patch", f"{api}/segregation-grids/{o['grille'].id}/", {"commentaire": "X"}),
        ("chef", "delete", f"{api}/segregation-grids/{o['grille'].id}/", {}),
        ("chef", "post", f"{api}/marc-lines/", {"mission": m, "risque": str(o["risque"].id)}),
        ("chef", "post", f"{api}/marc-lines/initialize/", {"mission": m}),
        ("chef", "patch", f"{api}/marc-lines/{o['ligne'].id}/", {"operation": "X"}),
        ("chef", "delete", f"{api}/marc-lines/{o['ligne'].id}/", {}),
        (
            "chef",
            "post",
            f"{api}/strengths-weaknesses/",
            {"mission": m, "type": "FORCE", "libelle": "X"},
        ),
        ("chef", "patch", f"{api}/strengths-weaknesses/{o['ff'].id}/", {"libelle": "Y"}),
        ("chef", "delete", f"{api}/strengths-weaknesses/{o['ff'].id}/", {}),
        (
            "chef",
            "post",
            f"{api}/audit-objectives/",
            {"mission": m, "ligne_marc": str(o["ligne"].id)},
        ),
        ("chef", "post", f"{api}/audit-objectives/initialize/", {"mission": m}),
        ("chef", "patch", f"{api}/audit-objectives/{o['objectif'].id}/", {"libelle": "Y"}),
        ("chef", "delete", f"{api}/audit-objectives/{o['objectif'].id}/", {}),
        ("chef", "patch", f"{api}/orientation-reports/{m}/", {"contexte": "X"}),
        ("audite_affecte", "post", f"{api}/audit-frameworks/{m}/opinions/", {"avis": "ACCORD"}),
    ]


def _geler(mode: str, o: dict[str, Any]) -> None:
    m = o["m"]
    if mode == "suspendue":
        Mission.objects.filter(pk=m.pk).update(
            statut=StatutMission.SUSPENDUE, statut_avant_suspension=StatutMission.EN_PLANIFICATION
        )
    else:
        for numero in (3, 5, 6, 7):
            EtapeMission.objects.filter(mission=m, numero=numero).update(statut=StatutEtape.VALIDEE)


@pytest.mark.parametrize("mode", ["suspendue", "etapes_closes"])
def test_api_gel_422_sur_chaque_route_analyse(
    api_client: APIClient, travaux_complets: dict[str, Any], mode: str
) -> None:
    """Mission suspendue, puis étapes closes : toute écriture répond 422 avec le détail."""
    _geler(mode, travaux_complets)
    for qui, methode, url, corps in _routes(travaux_complets):
        api_client.force_authenticate(travaux_complets["users"][qui])
        r = getattr(api_client, methode)(url, corps, format="json")
        assert r.status_code == 422, (mode, methode, url, r.status_code, r.content[:200])
        assert r.json()["detail"], (mode, methode, url)


def test_avis_avant_diffusion_422(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    m, users, _ = equipe_en_vi
    EtapeMission.objects.filter(mission=m, numero=6).update(statut=StatutEtape.A_FAIRE)
    api_client.force_authenticate(users["audite_affecte"])
    r = api_client.post(
        f"/api/v1/audit-frameworks/{m.id}/opinions/", {"avis": "ACCORD"}, format="json"
    )
    assert r.status_code == 422  # le droit existe (audité affecté), la fenêtre est fermée
