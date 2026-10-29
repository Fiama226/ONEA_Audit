import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.documents.exceptions import (
    ConsultationImmuableError,
    DocumentFigeError,
    GabaritFigeError,
    VersionFigeeError,
)
from apps.documents.models import (
    ConsultationDocument,
    Document,
    DocumentVersion,
    FormatFichier,
    GabaritDocument,
    StatutGabarit,
    StatutPdf,
)
from apps.users.models import User


def test_version_prete_immuable(version_prete: DocumentVersion, rai: User) -> None:
    version_prete.contexte = {"x": 1}
    with pytest.raises(VersionFigeeError, match="définitive"):
        version_prete.save()
    with pytest.raises(VersionFigeeError):
        DocumentVersion.objects.filter(pk=version_prete.pk).update(empreinte_docx="0" * 64)
    with pytest.raises(VersionFigeeError):
        version_prete.soft_delete(by=rai)
    with pytest.raises(VersionFigeeError):
        DocumentVersion.objects.filter(pk=version_prete.pk).update(deleted_at=timezone.now())


def test_bulk_update_refuse_sur_version_prete(version_prete: DocumentVersion) -> None:
    version_prete.erreur = "x"
    with pytest.raises(VersionFigeeError):
        DocumentVersion.objects.bulk_update([version_prete], ["erreur"])


def test_champs_pdf_modifiables_une_seule_fois(version_prete: DocumentVersion) -> None:
    DocumentVersion.objects.filter(pk=version_prete.pk).update(statut_pdf=StatutPdf.EN_COURS)
    version_prete.refresh_from_db()
    version_prete.fichier_pdf = "versions/x/v001.pdf"
    version_prete.empreinte_pdf = "b" * 64
    version_prete.taille_pdf = 10
    version_prete.statut_pdf = StatutPdf.PRET
    version_prete.save()
    version_prete.refresh_from_db()
    assert version_prete.statut_pdf == StatutPdf.PRET
    version_prete.empreinte_pdf = "c" * 64
    with pytest.raises(VersionFigeeError):
        version_prete.save()
    with pytest.raises(VersionFigeeError):
        DocumentVersion.objects.filter(pk=version_prete.pk).update(fichier_pdf="autre.pdf")
    version_prete.refresh_from_db()
    assert version_prete.empreinte_pdf == "b" * 64


def test_save_sans_changement_sur_version_prete(version_prete: DocumentVersion) -> None:
    version_prete.save()  # nothing changed: allowed
    version_prete.save(update_fields=["statut_pdf"])


def test_un_seul_gabarit_actif_par_type(gabarit_actif_test: GabaritDocument) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        GabaritDocument.objects.create(
            type_document="TEST_DOC",
            version=2,
            statut=StatutGabarit.ACTIF,
            fichier="gabarits/test_doc/002-x.docx",
            nom_original="b.docx",
            taille=1,
            empreinte="d" * 64,
            contrat_version=1,
        )
    GabaritDocument.objects.create(
        type_document="TEST_DOC",
        version=2,
        fichier="gabarits/test_doc/002-x.docx",
        nom_original="b.docx",
        taille=1,
        empreinte="d" * 64,
        contrat_version=1,
    )


def test_fichier_gabarit_immuable(gabarit_actif_test: GabaritDocument) -> None:
    gabarit_actif_test.empreinte = "e" * 64
    with pytest.raises(GabaritFigeError):
        gabarit_actif_test.save()
    with pytest.raises(GabaritFigeError):
        GabaritDocument.objects.filter(pk=gabarit_actif_test.pk).update(taille=1)
    gabarit_actif_test.refresh_from_db()
    gabarit_actif_test.statut = StatutGabarit.ARCHIVE
    gabarit_actif_test.save()


def test_numero_document_unique_meme_supprime(version_prete: DocumentVersion, rai: User) -> None:
    document = version_prete.document
    numero = document.numero
    document.soft_delete(by=rai)
    with pytest.raises(IntegrityError), transaction.atomic():
        Document.objects.create(
            type_document="AUTRE",
            mission=document.mission,
            content_type=document.content_type,
            object_id=document.object_id,
            numero=numero,
            annee=2026,
            sequence=2,
        )


def test_un_document_actif_par_objet(version_prete: DocumentVersion) -> None:
    d = version_prete.document
    with pytest.raises(IntegrityError), transaction.atomic():
        Document.objects.create(
            type_document=d.type_document,
            mission=d.mission,
            content_type=d.content_type,
            object_id=d.object_id,
            numero="AUTRE/1",
            annee=2026,
            sequence=2,
        )


def test_consultation_ajout_seul_et_cible_unique(
    version_prete: DocumentVersion, gabarit_actif_test: GabaritDocument, rai: User
) -> None:
    c = ConsultationDocument.objects.create(
        version=version_prete, utilisateur=rai, le=timezone.now(), format=FormatFichier.DOCX
    )
    ConsultationDocument.objects.create(
        gabarit=gabarit_actif_test, utilisateur=rai, le=timezone.now(), format=FormatFichier.DOCX
    )
    c.format = FormatFichier.PDF
    with pytest.raises(ConsultationImmuableError):
        c.save()
    with pytest.raises(ConsultationImmuableError):
        ConsultationDocument.objects.filter(pk=c.pk).update(format="PDF")
    with pytest.raises(ConsultationImmuableError):
        c.soft_delete(by=rai)
    for cibles in (
        {},
        {"version": version_prete, "gabarit": gabarit_actif_test},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            ConsultationDocument.objects.create(
                utilisateur=rai, le=timezone.now(), format=FormatFichier.PDF, **cibles
            )


def test_identite_et_numero_du_document_figes(version_prete: DocumentVersion) -> None:
    d = version_prete.document
    d.numero = "AUTRE/9"
    with pytest.raises(DocumentFigeError):
        d.save()
    with pytest.raises(DocumentFigeError):
        Document.objects.filter(pk=d.pk).update(sequence=9)
    with pytest.raises(DocumentFigeError):
        Document.objects.bulk_update([d], ["annee"])
    d.refresh_from_db()
    d.save()


def test_bulk_create_update_conflicts_refuse(version_prete: DocumentVersion) -> None:
    with pytest.raises(VersionFigeeError):
        DocumentVersion.objects.bulk_create(
            [version_prete],
            update_conflicts=True,
            update_fields=["erreur"],
            unique_fields=["document", "numero_version"],
        )
    with pytest.raises(GabaritFigeError):
        GabaritDocument.objects.bulk_create(
            [version_prete.gabarit],
            update_conflicts=True,
            update_fields=["commentaire"],
            unique_fields=["type_document", "version"],
        )
