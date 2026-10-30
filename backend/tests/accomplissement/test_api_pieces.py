import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accomplissement.models import PieceJustificative
from tests.accomplissement.fixtures_api import Equipe, client_de
from tests.accomplissement.fixtures_fiches import PDF, pdf

pytestmark = pytest.mark.django_db


def _deposer(c, fiche, fichier=None, libelle="Facture", **extra):  # type: ignore[no-untyped-def]
    return c.post(
        "/api/v1/evidence/",
        {"fiche": str(fiche.pk), "fichier": fichier or pdf(), "libelle": libelle, **extra},
        format="multipart",
    )


def test_depot_liste_modification_retrait(equipe_api: Equipe) -> None:
    e = equipe_api
    c = client_de(e.users["auditeur"])
    r = _deposer(c, e.fiche1, description="Facture de mars")
    assert r.status_code == 201, r.json()
    piece = r.json()
    assert piece["numero"] == 1
    assert piece["nom_fichier_original"] == "facture.pdf"
    assert piece["type_mime"] == "application/pdf"
    assert piece["taille_octets"] == len(PDF)
    assert len(piece["empreinte_sha256"]) == 64
    assert piece["deposee_par"]["id"] == e.users["auditeur"].pk
    assert set(piece["actions_possibles"]) == {"TELECHARGER", "MODIFIER", "RETIRER"}
    assert "cle_stockage" not in piece
    # Mêmes octets : la pièce existante, sans doublon.
    r = _deposer(c, e.fiche1, libelle="Autre libellé")
    assert r.status_code == 200 and r.json()["id"] == piece["id"]
    assert PieceJustificative.objects.count() == 1
    liste = c.get(f"/api/v1/evidence/?fiche={e.fiche1.pk}").json()
    assert [p["id"] for p in liste["results"]] == [piece["id"]]
    assert c.get(f"/api/v1/evidence/?mission={e.mission.pk}").json()["count"] == 1
    assert c.get("/api/v1/evidence/").status_code == 400
    r = c.patch(f"/api/v1/evidence/{piece['id']}/", {"libelle": "Renommée"}, format="json")
    assert r.status_code == 200 and r.json()["libelle"] == "Renommée"
    # Le fichier est immuable : champ ignoré ou refusé, jamais modifié.
    r = c.patch(f"/api/v1/evidence/{piece['id']}/", {"empreinte_sha256": "0" * 64}, format="json")
    assert r.json()["empreinte_sha256"] == piece["empreinte_sha256"]
    assert c.delete(f"/api/v1/evidence/{piece['id']}/").status_code == 204
    assert c.get(f"/api/v1/evidence/{piece['id']}/").status_code == 404


def test_depot_refuse_le_contenu_invalide(equipe_api: Equipe) -> None:
    e = equipe_api
    c = client_de(e.users["auditeur"])
    r = _deposer(c, e.fiche1, SimpleUploadedFile("virus.exe", b"MZ" + b"x" * 50))
    assert r.status_code == 422 and "fichier" in r.json()["errors"]
    r = _deposer(c, e.fiche1, SimpleUploadedFile("faux.pdf", b"<html>pas un pdf</html>"))
    assert r.status_code == 422
    r = _deposer(c, e.fiche1, SimpleUploadedFile("vide.pdf", b""))
    assert r.status_code in (400, 422)
    r = c.post("/api/v1/evidence/", {"fiche": str(e.fiche1.pk), "libelle": "x"}, format="multipart")
    assert r.status_code == 400 and "fichier" in r.json()["errors"]
    r = _deposer(c, e.fiche1, libelle="  ")
    assert r.status_code in (400, 422)


def test_piece_sur_fiche_soumise_ou_autre_fiche(equipe_api: Equipe) -> None:
    e = equipe_api
    assert _deposer(client_de(e.users["autre"]), e.fiche2).status_code == 422  # soumise
    assert _deposer(client_de(e.users["autre"]), e.fiche1).status_code == 403
    r = client_de(e.users["auditeur"]).post(
        "/api/v1/evidence/", {"fiche": "pas-un-uuid", "libelle": "x"}, format="multipart"
    )
    assert r.status_code == 400
