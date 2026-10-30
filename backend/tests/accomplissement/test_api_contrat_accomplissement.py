from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accomplissement.models import PieceJustificative
from apps.analyse.models import ObjectifAudit
from apps.missions.models import StatutEtape
from tests.accomplissement.factories import PieceFactory, TestPrevuFactory
from tests.accomplissement.fixtures_api import Equipe, client_de
from tests.accomplissement.fixtures_fiches import pdf
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _requetes(c, url):  # type: ignore[no-untyped-def]
    with CaptureQueriesContext(connection) as ctx:
        r = c.get(url)
    assert r.status_code == 200, r.json()
    return len(ctx), r.json()


def test_listes_requetes_bornees(equipe_api: Equipe) -> None:
    e = equipe_api
    programme = e.test1.programme
    forcer_etapes(e.mission, {8: StatutEtape.EN_COURS})
    for _ in range(38):
        TestPrevuFactory(mission=e.mission, programme=programme)
    forcer_etapes(e.mission, {8: StatutEtape.TERMINEE})
    rai = client_de(e.users["rai"])
    n, corps = _requetes(rai, f"/api/v1/planned-tests/?mission={e.mission.pk}&page_size=50")
    assert corps["count"] == 40 and len(corps["results"]) == 40
    assert n <= 5, n
    n, corps = _requetes(rai, f"/api/v1/test-sheets/?mission={e.mission.pk}")
    assert corps["count"] == 2
    assert n <= 5, n
    for _ in range(5):
        PieceFactory(fiche=e.fiche1, mission=e.mission, deposee_par=e.users["auditeur"])
    n, corps = _requetes(rai, f"/api/v1/evidence/?fiche={e.fiche1.pk}")
    assert corps["count"] == 5
    assert n <= 4, n  # fiche -> mission visible, comptage, lignes (+ contexte)


def test_erreurs_au_format_unique(equipe_api: Equipe) -> None:
    e = equipe_api
    rai = client_de(e.users["rai"])
    auditeur = client_de(e.users["auditeur"])
    cas = [
        auditeur.post(
            "/api/v1/evidence/",
            {"fiche": str(e.fiche1.pk), "libelle": "x"},
            format="multipart",
        ),  # 400 fichier absent
        rai.get("/api/v1/test-sheets/00000000-0000-0000-0000-000000000000/"),  # 404
        rai.post(
            "/api/v1/test-sheets/", {"test": str(e.test1.pk)}, format="json"
        ),  # 422 déjà une fiche
        client_de(e.users["non_affecte"]).get(f"/api/v1/test-sheets/{e.fiche1.pk}/"),  # 404
    ]
    for reponse, statut in zip(cas, (400, 404, 422, 404), strict=True):
        assert reponse.status_code == statut
        assert set(reponse.json()) == {"detail", "errors"}
    piece = PieceFactory(fiche=e.fiche1, mission=e.mission, deposee_par=e.users["auditeur"])
    PieceJustificative.objects.filter(pk=piece.pk)  # existe
    import pathlib  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    racine = pathlib.Path(settings.STOCKAGE_PREUVES["OPTIONS"]["RACINE"])
    (racine / piece.cle_stockage).chmod(0o600)
    (racine / piece.cle_stockage).write_bytes(b"altere")
    r = rai.get(f"/api/v1/evidence/{piece.pk}/download/")
    assert r.status_code == 409 and set(r.json()) == {"detail", "errors"}


def test_api_contrat_synthese(equipe_api: Equipe) -> None:
    """JSON exact de la synthèse (recopié dans les fixtures MSW du lot 6, T11)."""
    e = equipe_api
    libelles = list(
        ObjectifAudit.objects.filter(mission=e.mission)
        .order_by("numero")
        .values_list("libelle", flat=True)
    )
    e.mission.budget_jours = Decimal("5.0")
    e.mission.save()
    r = client_de(e.users["rai"]).get(f"/api/v1/work-programs/summary/?mission={e.mission.pk}")
    assert r.status_code == 200
    auditeurs = r.json()["auditeurs"]
    assert r.json() == {
        "objectifs": [
            {"code": "OA-01", "libelle": libelles[0], "nb_tests": 1, "charge": "0.0"},
            {"code": "OA-02", "libelle": libelles[1], "nb_tests": 1, "charge": "0.0"},
        ],
        "auditeurs": auditeurs,
        "total_charge": "0.0",
        "budget_jours": "5.0",
        "depassement_budget": False,
        "tests_sans_auditeur": [],
    }
    assert [set(a) for a in auditeurs] == [{"utilisateur", "nb_tests", "charge"}] * 2
    assert set(auditeurs[0]["utilisateur"]) == {
        "id",
        "username",
        "nom_complet",
        "role",
        "direction_code",
        "fonction",
    }


def test_schema_expose_les_routes_accomplissement(api_client, db) -> None:  # type: ignore[no-untyped-def]
    chemins = api_client.get("/api/schema/?format=json").json()
    paths = chemins["paths"]
    for chemin in (
        "/api/v1/work-programs/",
        "/api/v1/work-programs/{id}/",
        "/api/v1/work-programs/summary/",
        "/api/v1/work-programs/snapshots/",
        "/api/v1/work-programs/snapshots/{id}/",
        "/api/v1/planned-tests/{id}/abandon/",
        "/api/v1/test-sheets/{id}/submit/",
        "/api/v1/test-sheets/{id}/validate/",
        "/api/v1/test-sheets/{id}/return/",
        "/api/v1/test-sheets/{id}/reopen/",
        "/api/v1/evidence/",
        "/api/v1/evidence/{id}/download/",
    ):
        assert chemin in paths, chemin
    composants = chemins["components"]["schemas"]
    for nom in (
        "ProgrammeDeTravail",
        "TestPrevu",
        "SyntheseProgrammeTravail",
        "InstantaneResume",
        "Instantane",
        "FicheDeTest",
        "PieceJustificative",
        "DepotPieceRequest",
        "NatureTestEnum",
        "MethodeSelectionEnum",
        "StatutTestEnum",
        "StatutFicheEnum",
        "ConclusionTestEnum",
        "TypeEvenementFicheEnum",
    ):
        assert nom in composants, nom
    telechargement = paths["/api/v1/evidence/{id}/download/"]["get"]["responses"]["200"]
    assert "application/octet-stream" in telechargement["content"]
    _ = pdf  # utilisé par les autres modules de tests
