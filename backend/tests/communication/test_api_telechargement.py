# ruff: noqa: F811, F401
"""Téléchargement du rapport diffusé : périmètre, intégrité, journal de consultation."""

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from apps.communication.models import DestinataireDiffusion, Rapport
from apps.communication.services.diffusion import diffuser
from apps.documents.models import ConsultationDocument, DocumentVersion, StatutPdf
from apps.documents.stockage import cle_version, ecrire
from config.documents_settings import configuration_stockage
from tests.accomplissement.fixtures_api import client_de
from tests.communication.fixtures_api import RAPPORTS, EquipeRapport, equipe
from tests.communication.support_t8 import (
    admin,
    creer_version,
    dg,
    rapport_diffuse,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.documents.conftest import chemin_fichier

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7 rapport final"
DOCX = b"PK docx rapport final"


@pytest.fixture(autouse=True)
def stockage_tmp(tmp_path: Path, settings: Any) -> Path:
    settings.DOCUMENTS_ROOT = str(tmp_path)
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(tmp_path)}
        ),
    }
    return tmp_path


def _version(
    rapport: Rapport, type_document: str = "RAPPORT_FINAL", pdf: bytes = PDF, docx: bytes = DOCX
) -> DocumentVersion:
    """Version PRETE du rapport avec de vrais fichiers (empreintes SHA-256 comprises)."""
    cle = uuid4()
    return creer_version(
        rapport,
        type_document,
        fichier_pdf=ecrire(cle_version(cle, 1, "pdf"), pdf),
        empreinte_pdf=hashlib.sha256(pdf).hexdigest(),
        fichier_docx=ecrire(cle_version(cle, 1, "docx"), docx),
        empreinte_docx=hashlib.sha256(docx).hexdigest(),
    )


@pytest.fixture
def rapport_telechargeable(rapport_valide: Rapport, rai: Any) -> Rapport:
    _version(rapport_valide)
    _version(rapport_valide, "NOTE_SYNTHETIQUE", b"%PDF-1.7 note", b"PK docx note")
    diffuser(rapport_valide, by=rai)
    return Rapport.objects.get(pk=rapport_valide.pk)


def _telecharger(e: EquipeRapport, qui: str, rapport: Rapport, query: str = "format=pdf") -> Any:
    return client_de(e.users[qui]).get(f"{RAPPORTS}{rapport.pk}/download/?{query}")


def test_dg_telecharge_version_diffusee_journalisee(
    equipe: EquipeRapport, rapport_telechargeable: Rapport
) -> None:
    r = _telecharger(equipe, "dg", rapport_telechargeable)
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert r["Cache-Control"] == "private, no-store"
    assert b"".join(r.streaming_content) == PDF
    consultation = ConsultationDocument.objects.get()
    assert consultation.utilisateur == equipe.users["dg"] and consultation.format == "PDF"
    ligne = DestinataireDiffusion.objects.get(
        rapport=rapport_telechargeable, utilisateur=equipe.users["dg"]
    )
    assert ligne.premiere_consultation_le is not None


def test_formats_et_documents(equipe: EquipeRapport, rapport_telechargeable: Rapport) -> None:
    docx = _telecharger(equipe, "rai", rapport_telechargeable, "format=docx")
    assert b"".join(docx.streaming_content) == DOCX
    note = _telecharger(equipe, "rai", rapport_telechargeable, "format=pdf&document=note")
    assert b"".join(note.streaming_content) == b"%PDF-1.7 note"
    assert _telecharger(equipe, "rai", rapport_telechargeable, "format=odt").status_code == 400
    assert _telecharger(equipe, "rai", rapport_telechargeable, "document=annexe").status_code == 400
    # défaut : le rapport en PDF
    assert (
        b"".join(_telecharger(equipe, "rai", rapport_telechargeable, "").streaming_content) == PDF
    )


def test_perimetre_du_telechargement(
    equipe: EquipeRapport, rapport_telechargeable: Rapport
) -> None:
    for qui in ("rai", "chef", "auditeur", "audite", "dg"):
        assert _telecharger(equipe, qui, rapport_telechargeable).status_code == 200, qui
    assert _telecharger(equipe, "admin", rapport_telechargeable).status_code == 403
    assert _telecharger(equipe, "non_affecte", rapport_telechargeable).status_code == 404
    assert _telecharger(equipe, "audite_non_affecte", rapport_telechargeable).status_code == 404


def test_telechargement_version_non_diffusee_404(
    equipe: EquipeRapport, rapport_valide: Rapport
) -> None:
    _version(rapport_valide)
    for qui in ("rai", "chef", "auditeur", "audite", "dg"):
        assert _telecharger(equipe, qui, rapport_valide).status_code == 404, qui
    assert ConsultationDocument.objects.count() == 0


def test_telechargement_altere_409(equipe: EquipeRapport, rapport_telechargeable: Rapport) -> None:
    version = rapport_telechargeable.diffusion.version_rapport
    chemin = chemin_fichier(str(version.fichier_pdf.name))
    chemin.write_bytes(b"contenu altere")
    r = _telecharger(equipe, "dg", rapport_telechargeable)
    assert r.status_code == 409
    # le fichier Word reste lisible, et rien n'est marqué consulté pour la version altérée
    assert _telecharger(equipe, "dg", rapport_telechargeable, "format=docx").status_code == 200
    ligne = DestinataireDiffusion.objects.get(
        rapport=rapport_telechargeable, utilisateur=equipe.users["dg"]
    )
    assert ConsultationDocument.objects.filter(format="PDF").count() == 0
    assert ligne.premiere_consultation_le is not None  # posée par le téléchargement Word


def test_note_absente_404(equipe: EquipeRapport, rapport_valide: Rapport, rai: Any) -> None:
    _version(rapport_valide)
    diffuser(rapport_valide, by=rai)
    rapport = Rapport.objects.get(pk=rapport_valide.pk)
    assert _telecharger(equipe, "rai", rapport, "document=note").status_code == 404
    assert _telecharger(equipe, "rai", rapport, "document=rapport").status_code == 200
