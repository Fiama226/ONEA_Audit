import pytest

from apps.accomplissement.models import StatutFiche
from apps.core.consultations import Consultation
from tests.accomplissement.fixtures_api import Equipe, client_de
from tests.accomplissement.fixtures_fiches import pdf

pytestmark = pytest.mark.django_db


def test_cycle_complet_de_la_fiche(equipe_api: Equipe) -> None:
    e = equipe_api
    auditeur = client_de(e.users["auditeur"])
    f1 = e.fiche1.pk
    r = auditeur.patch(
        f"/api/v1/test-sheets/{f1}/",
        {"resultat": "RAS", "conclusion": "SATISFAISANT", "taille_testee": 5},
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert "SOUMETTRE" in r.json()["actions_possibles"]
    # Sans pièce ni justification : 422.
    assert auditeur.post(f"/api/v1/test-sheets/{f1}/submit/").status_code == 422
    r = auditeur.post(
        "/api/v1/evidence/",
        {"fiche": str(f1), "fichier": pdf(), "libelle": "Facture"},
        format="multipart",
    )
    assert r.status_code == 201, r.json()
    r = auditeur.post(f"/api/v1/test-sheets/{f1}/submit/")
    assert r.status_code == 200 and r.json()["statut"] == "SOUMIS"
    # Le valideur ne peut être l'auteur ; le RAI valide, puis rouvre avec motif.
    assert auditeur.post(f"/api/v1/test-sheets/{f1}/validate/").status_code == 403
    rai = client_de(e.users["rai"])
    r = rai.post(f"/api/v1/test-sheets/{f1}/return/", {}, format="json")
    assert r.status_code == 400
    r = rai.post(f"/api/v1/test-sheets/{f1}/return/", {"motif": "Précisez"}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "RENVOYE"
    assert r.json()["motif_renvoi"] == "Précisez"
    assert auditeur.post(f"/api/v1/test-sheets/{f1}/submit/").status_code == 200
    r = rai.post(f"/api/v1/test-sheets/{f1}/validate/")
    assert r.status_code == 200 and r.json()["statut"] == "VALIDE"
    assert r.json()["validee_par"] == e.users["rai"].pk
    r = rai.post(f"/api/v1/test-sheets/{f1}/reopen/", {"motif": "Erreur"}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "BROUILLON"
    detail = rai.get(f"/api/v1/test-sheets/{f1}/").json()
    assert [ev["type"] for ev in detail["evenements"]] == [
        "SOUMISE",
        "RENVOYEE",
        "SOUMISE",
        "VALIDEE",
        "ROUVERTE",
    ]
    assert len(detail["pieces"]) == 1
    assert detail["constats"] == []


def test_creation_et_suppression_de_fiche(equipe_api: Equipe) -> None:
    e = equipe_api
    rai = client_de(e.users["rai"])
    # Le test 1 a déjà une fiche : 422.
    r = rai.post("/api/v1/test-sheets/", {"test": str(e.test1.pk)}, format="json")
    assert r.status_code == 422
    r = rai.post("/api/v1/test-sheets/", {}, format="json")
    assert r.status_code == 400
    # Suppression d'un brouillon vide.
    assert (
        client_de(e.users["autre"]).delete(f"/api/v1/test-sheets/{e.fiche1.pk}/").status_code == 403
    )
    assert (
        client_de(e.users["auditeur"]).delete(f"/api/v1/test-sheets/{e.fiche1.pk}/").status_code
        == 204
    )
    r = rai.post("/api/v1/test-sheets/", {"test": str(e.test1.pk)}, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["statut"] == StatutFiche.BROUILLON


def test_filtres_de_la_liste(equipe_api: Equipe) -> None:
    e = equipe_api
    m = e.mission.pk
    rai = client_de(e.users["rai"])
    assert rai.get("/api/v1/test-sheets/").status_code == 400
    ids = lambda q: {  # noqa: E731
        f["id"] for f in rai.get(f"/api/v1/test-sheets/?mission={m}&{q}").json()["results"]
    }
    assert ids("a_valider=true") == {str(e.fiche2.pk)}
    assert ids("statut=BROUILLON") == {str(e.fiche1.pk)}
    assert ids(f"auteur={e.users['auditeur'].pk}") == {str(e.fiche1.pk)}
    assert ids("conclusion=SATISFAISANT") == {str(e.fiche2.pk)}
    mien = client_de(e.users["autre"]).get(f"/api/v1/test-sheets/?mission={m}&mine=true")
    assert {f["id"] for f in mien.json()["results"]} == {str(e.fiche2.pk)}
    ligne = rai.get(f"/api/v1/test-sheets/?mission={m}").json()["results"][0]
    assert "pieces" not in ligne and "evenements" not in ligne
    assert {"test_code", "objectif_code", "auteur_detail", "constats"} <= set(ligne)


def test_retrieve_journalise_la_consultation_sauf_head(equipe_api: Equipe) -> None:
    e = equipe_api
    c = client_de(e.users["superviseur"])
    assert c.head(f"/api/v1/test-sheets/{e.fiche2.pk}/").status_code == 200
    assert Consultation.objects.count() == 0
    assert c.get(f"/api/v1/test-sheets/{e.fiche2.pk}/").status_code == 200
    entree = Consultation.objects.get()
    assert (entree.object_id, entree.par, entree.action) == (
        e.fiche2.pk,
        e.users["superviseur"],
        "CONSULTATION",
    )
    # Un refus ne journalise rien.
    client_de(e.users["audite"]).get(f"/api/v1/test-sheets/{e.fiche2.pk}/")
    client_de(e.users["non_affecte"]).get(f"/api/v1/test-sheets/{e.fiche2.pk}/")
    assert Consultation.objects.count() == 1


def test_403_avant_400_sur_fiche(equipe_api: Equipe) -> None:
    e = equipe_api
    r = client_de(e.users["autre"]).patch(
        f"/api/v1/test-sheets/{e.fiche1.pk}/", {"taille_testee": -4}, format="json"
    )
    assert r.status_code == 403
    r = client_de(e.users["auditeur"]).patch(
        f"/api/v1/test-sheets/{e.fiche1.pk}/", {"taille_testee": -4}, format="json"
    )
    assert r.status_code == 400


def test_suppression_refusee_avec_piece_ou_historique(equipe_api: Equipe) -> None:
    e = equipe_api
    auditeur = client_de(e.users["auditeur"])
    r = auditeur.post(
        "/api/v1/evidence/",
        {"fiche": str(e.fiche1.pk), "fichier": pdf(), "libelle": "Facture"},
        format="multipart",
    )
    assert r.status_code == 201
    r = auditeur.delete(f"/api/v1/test-sheets/{e.fiche1.pk}/")
    assert r.status_code == 422
    assert "sans pièce ni historique" in r.json()["detail"]
    # Fiche soumise (historique) : refusée aussi.
    r = client_de(e.users["autre"]).delete(f"/api/v1/test-sheets/{e.fiche2.pk}/")
    assert r.status_code == 422


def test_suppression_droit_avant_fenetre(equipe_api: Equipe) -> None:
    from django.core.exceptions import PermissionDenied

    from apps.accomplissement.services.fiches import supprimer_fiche
    from apps.core.exceptions import RegleMetierError
    from apps.missions.models import StatutEtape
    from tests.missions.conftest import forcer_etapes

    e = equipe_api
    forcer_etapes(e.mission, {12: StatutEtape.VALIDEE})
    with pytest.raises(PermissionDenied):
        supprimer_fiche(e.fiche1, by=e.users["autre"])  # 403 avant le refus de fenêtre
    with pytest.raises(RegleMetierError):
        supprimer_fiche(e.fiche1, by=e.users["auditeur"])
