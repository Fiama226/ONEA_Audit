from auditlog.models import LogEntry

from apps.documents.models import (
    ConsultationDocument,
    Document,
    DocumentVersion,
    FormatNumerotation,
    GabaritDocument,
    StatutGeneration,
    StatutPdf,
)
from apps.documents.numerotation import format_de


def test_valeurs_par_defaut(version_prete: DocumentVersion) -> None:
    assert version_prete.statut == StatutGeneration.PRETE
    assert version_prete.statut_pdf == StatutPdf.NON_DEMANDE
    assert version_prete.document.versions.get() == version_prete


def test_cinq_modeles_audites(
    version_prete: DocumentVersion, gabarit_actif_test: GabaritDocument
) -> None:
    format_de("TEST_DOC")
    for modele in (GabaritDocument, Document, DocumentVersion, FormatNumerotation):
        assert LogEntry.objects.get_for_model(modele).exists(), modele
    from auditlog.registry import auditlog

    assert auditlog.contains(ConsultationDocument)
