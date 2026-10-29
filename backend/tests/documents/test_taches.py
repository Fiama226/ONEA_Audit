import hashlib
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.documents import pdf
from apps.documents.models import DocumentVersion, GabaritDocument, StatutGeneration
from apps.documents.moteur.registre import TypeDocument
from apps.documents.pdf import ConversionPdfError
from apps.documents.services.generation import demander_generation
from apps.documents.stockage import cle_version, ecrire
from apps.documents.tasks import (
    balayer_generations_bloquees,
    convertir_pdf,
    generer_version,
)
from apps.missions.models import Mission
from apps.users.models import User

from .fabrique import docx_avec

pytestmark = pytest.mark.django_db


def test_noms_des_taches() -> None:
    assert generer_version.name == "documents.generer_version"
    assert convertir_pdf.name == "documents.convertir_pdf"
    assert balayer_generations_bloquees.name == "documents.balayer_generations_bloquees"


def test_generer_version_idempotente(version_prete: DocumentVersion) -> None:
    avant = version_prete.empreinte_docx
    generer_version(str(version_prete.pk))  # PRETE: nothing happens
    version_prete.refresh_from_db()
    assert version_prete.empreinte_docx == avant


def test_generer_version_reprise_apres_ecriture_du_fichier(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    pdf_factice: bytes,
) -> None:
    """A crash after the file was written must not make the retry fail (write-once keys)."""
    v = demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    contenu = docx_avec("Reste d'une exécution interrompue")
    ecrire(cle_version(v.document_id, 1, "docx"), contenu)
    DocumentVersion.all_objects.filter(pk=v.pk).update(statut="EN_COURS")
    generer_version(str(v.pk))
    v.refresh_from_db()
    assert v.statut == "PRETE"
    assert v.empreinte_docx == hashlib.sha256(contenu).hexdigest()


def test_conversion_refusee_marque_echec_pdf(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    monkeypatch.setattr(pdf, "convertir_en_pdf", Mock(side_effect=ConversionPdfError("refusée")))
    with django_capture_on_commit_callbacks(execute=True):
        v = demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    v.refresh_from_db()
    assert v.statut_pdf == "ECHEC"
    assert v.erreur_pdf.startswith("La conversion PDF a échoué :")
    assert v.erreur_pdf.endswith("Le document Word reste disponible.")


def test_balayage_generations_bloquees(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    version_prete: DocumentVersion,
) -> None:
    maintenant = timezone.now()
    base = DocumentVersion.all_objects.get(pk=version_prete.pk)

    def creer(numero: int, debut: Any, statut: str) -> DocumentVersion:
        version: DocumentVersion = DocumentVersion.objects.create(
            document=base.document,
            numero_version=numero,
            statut=statut,
            gabarit=base.gabarit,
            demandee_par=rai,
            debut_traitement=debut,
        )
        return version

    ancienne = creer(2, maintenant - timedelta(minutes=16), StatutGeneration.EN_COURS)
    recente = creer(3, maintenant - timedelta(minutes=5), StatutGeneration.EN_COURS)
    assert balayer_generations_bloquees() == 1
    ancienne.refresh_from_db()
    recente.refresh_from_db()
    assert ancienne.statut == "ECHEC"
    assert ancienne.erreur == "La génération a été interrompue : relancez-la."
    assert recente.statut == "EN_COURS"


def test_balayage_conversion_pdf_bloquee(version_prete: DocumentVersion) -> None:
    DocumentVersion.all_objects.filter(pk=version_prete.pk).update(
        statut_pdf="EN_COURS", debut_traitement=timezone.now() - timedelta(minutes=20)
    )
    assert balayer_generations_bloquees() == 1
    version_prete.refresh_from_db()
    assert version_prete.statut_pdf == "ECHEC"
    assert "relancez-la" in version_prete.erreur_pdf
