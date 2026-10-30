from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import get_resolver

from apps.accomplissement.models import PieceJustificative
from apps.core.consultations import Consultation
from tests.accomplissement.fixtures_api import Equipe, client_de
from tests.accomplissement.fixtures_fiches import PDF, pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def piece(equipe_api: Equipe) -> PieceJustificative:
    r = client_de(equipe_api.users["auditeur"]).post(
        "/api/v1/evidence/",
        {"fiche": str(equipe_api.fiche1.pk), "fichier": pdf(), "libelle": "Facture"},
        format="multipart",
    )
    assert r.status_code == 201, r.json()
    return PieceJustificative.objects.get(pk=r.json()["id"])


def test_upload_multipart_et_telechargement_identique(
    equipe_api: Equipe, piece: PieceJustificative
) -> None:
    r = client_de(equipe_api.users["superviseur"]).get(f"/api/v1/evidence/{piece.pk}/download/")
    assert r.status_code == 200
    assert b"".join(r.streaming_content) == PDF
    assert r["Content-Disposition"] == 'attachment; filename="facture.pdf"'
    assert r["Content-Type"] == "application/pdf"
    assert r["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in r["Cache-Control"]
    assert r["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert r["Content-Length"] == str(len(PDF))


def test_en_tetes_surs_pour_html_et_noms_hostiles(
    equipe_api: Equipe, piece: PieceJustificative
) -> None:
    PieceJustificative._base_manager.filter(pk=piece.pk).update(
        nom_fichier_original='é"\r\nX-Evil: 1/../é.html'
    )
    r = client_de(equipe_api.users["rai"]).get(f"/api/v1/evidence/{piece.pk}/download/")
    assert r.status_code == 200
    assert "\n" not in r["Content-Disposition"] and "\r" not in r["Content-Disposition"]
    assert "X-Evil" not in r
    assert r["Content-Disposition"].startswith("attachment;")
    assert "filename*=utf-8''" in r["Content-Disposition"]
    # Type fixé par l'extension (liste blanche), jamais exécutable dans le navigateur.
    assert r["Content-Type"] == "application/octet-stream"


def test_telechargement_altere_409(
    equipe_api: Equipe, piece: PieceJustificative, tmp_path: Path
) -> None:
    chemin = tmp_path / "preuves" / piece.cle_stockage
    chemin.chmod(0o600)
    chemin.write_bytes(b"%PDF-1.7 altere")
    r = client_de(equipe_api.users["rai"]).get(f"/api/v1/evidence/{piece.pk}/download/")
    assert r.status_code == 409
    assert set(r.json()) == {"detail", "errors"}
    assert Consultation.objects.count() == 0


def test_telechargement_journalise_et_head_non(
    equipe_api: Equipe, piece: PieceJustificative
) -> None:
    c = client_de(equipe_api.users["chef"])
    url = f"/api/v1/evidence/{piece.pk}/download/"
    assert c.head(url).status_code == 200
    assert Consultation.objects.count() == 0
    assert c.get(url).status_code == 200
    entree = Consultation.objects.get()
    assert (entree.object_id, entree.par, entree.action) == (
        piece.pk,
        equipe_api.users["chef"],
        "TELECHARGEMENT",
    )


def test_audite_403_sur_fiches_et_pieces(equipe_api: Equipe, piece: PieceJustificative) -> None:
    c = client_de(equipe_api.users["audite"])
    for url in (
        f"/api/v1/evidence/{piece.pk}/download/",
        f"/api/v1/evidence/{piece.pk}/",
        f"/api/v1/evidence/?fiche={equipe_api.fiche1.pk}",
        f"/api/v1/test-sheets/{equipe_api.fiche1.pk}/",
        f"/api/v1/test-sheets/?mission={equipe_api.mission.pk}",
        f"/api/v1/planned-tests/?mission={equipe_api.mission.pk}",
    ):
        assert c.get(url).status_code == 403, url
    assert Consultation.objects.count() == 0


def test_non_affecte_404_sur_download(equipe_api: Equipe, piece: PieceJustificative) -> None:
    r = client_de(equipe_api.users["non_affecte"]).get(f"/api/v1/evidence/{piece.pk}/download/")
    assert r.status_code == 404


def test_content_length_refuse_avant_lecture(equipe_api: Equipe) -> None:
    c = client_de(equipe_api.users["auditeur"])
    r = c.post(
        "/api/v1/evidence/",
        {"fiche": str(equipe_api.fiche1.pk), "fichier": pdf(), "libelle": "x"},
        format="multipart",
        CONTENT_LENGTH=str(80 * 1024 * 1024),
    )
    assert r.status_code == 422
    assert "50 Mo" in r.json()["errors"]["fichier"][0]
    assert PieceJustificative.objects.count() == 0


def test_taille_reelle_refusee(equipe_api: Equipe, settings) -> None:  # type: ignore[no-untyped-def]
    settings.PIECE_TAILLE_MAX_OCTETS = 100
    r = client_de(equipe_api.users["auditeur"]).post(
        "/api/v1/evidence/",
        {
            "fiche": str(equipe_api.fiche1.pk),
            "fichier": SimpleUploadedFile("gros.pdf", b"%PDF-" + b"x" * 500),
            "libelle": "x",
        },
        format="multipart",
    )
    assert r.status_code == 422


def test_aucun_service_statique_des_fichiers(settings) -> None:  # type: ignore[no-untyped-def]
    assert not getattr(settings, "MEDIA_ROOT", "")  # MEDIA_URL: valeur par défaut de Django
    motifs = [str(p.pattern) for p in get_resolver().url_patterns]
    assert not any("media" in m or "preuves" in m for m in motifs)


def test_fiche_dans_l_url_controlee_avant_d_analyser_le_corps(equipe_api: Equipe) -> None:
    e = equipe_api
    url = f"/api/v1/evidence/?fiche={e.fiche1.pk}"
    # Corps multipart illisible : un non-rédacteur reçoit 403 (jamais d'analyse), un inconnu 404.
    c = client_de(e.users["autre"])
    r = c.generic("POST", url, b"corps-illisible", content_type="multipart/form-data; boundary=x")
    assert r.status_code == 403
    r = client_de(e.users["non_affecte"]).generic(
        "POST", url, b"corps-illisible", content_type="multipart/form-data; boundary=x"
    )
    assert r.status_code == 404
    # Le rédacteur dépose avec la fiche seulement dans l'URL.
    ok = client_de(e.users["auditeur"]).post(
        url, {"fichier": pdf(), "libelle": "Facture"}, format="multipart"
    )
    assert ok.status_code == 201, ok.json()
    # Fiche du corps différente de celle de l'URL : 400.
    r = client_de(e.users["rai"]).post(
        url,
        {"fiche": str(e.fiche2.pk), "fichier": pdf("autre.pdf", PDF + b"z"), "libelle": "x"},
        format="multipart",
    )
    assert r.status_code == 400


def test_nginx_ne_sert_aucune_racine_de_documents() -> None:
    dossier = Path(__file__).resolve().parents[3] / "docker" / "nginx"
    confs = list(dossier.glob("*.conf"))
    assert confs
    autorises = ("/usr/share/nginx/html", "/var/www/static")
    for conf in confs:
        texte = conf.read_text(encoding="utf8")
        for ligne in texte.splitlines():
            directive = ligne.split("#")[0].strip()
            if directive.startswith(("root ", "alias ")):
                # Seuls le front compilé et les statiques Django sont servis.
                assert any(ok in directive for ok in autorises), (conf.name, directive)
        assert "fichiers" not in texte
        assert "preuves" not in texte
        assert "/var/lib/onea" not in texte
