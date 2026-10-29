"""Document generation: request (synchronous), rendering and PDF conversion (worker), download.

Atomicity (D8/D9): the number, the `Document` row and the `EN_ATTENTE` version are created in
the request transaction, so a rollback releases the number (no gap). Once committed, a number
is never reassigned, even when the generation fails: a new request makes a new version of the
same document. In the worker, a file is written before the row is updated; if the worker dies
in between, the retry finds the (complete, write-once) file and reuses it.
"""

import hashlib
import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.missions.gardes import STATUTS_FIGES
from apps.users.models import User

from .. import pdf
from ..exceptions import ContratNonRespecteError, IntegriteError
from ..models import (
    ConsultationDocument,
    Document,
    DocumentVersion,
    FormatFichier,
    GabaritDocument,
    StatutGabarit,
    StatutGeneration,
    StatutPdf,
)
from ..moteur.contrats import ecarts_contexte, empreinte_json
from ..moteur.exceptions import RenduError
from ..moteur.registre import type_document as type_enregistre
from ..moteur.rendu import rendre_docx
from ..numerotation import attribuer_numero
from ..stockage import (
    EspaceInsuffisantError,
    FichierExistantError,
    StockageIndisponibleError,
    cle_version,
    ecrire_avec_empreinte,
    lire,
)

logger = logging.getLogger(__name__)

DELAI_BLOCAGE = timedelta(minutes=15)
_MO = 1024 * 1024
_ORGANISATION_DEFAUT = {
    "nom": "Office National de l'Eau et de l'Assainissement",
    "sigle": "ONEA",
    "departement": "Département Audit Interne",
}
# Volatile entries of the `document` block, left out of the context fingerprint (D8).
_VOLATILES = ("genere_le", "genere_par", "version")
_EN_COURS = (StatutGeneration.EN_ATTENTE, StatutGeneration.EN_COURS)


def _nom_utilisateur(user: User) -> str:
    return user.get_full_name() or user.username


def empreinte_contexte(contexte: dict[str, Any]) -> str:
    """Fingerprint of the data of a context (the volatile `document` entries excluded)."""
    document = {k: v for k, v in contexte.get("document", {}).items() if k not in _VOLATILES}
    return empreinte_json({**contexte, "document": document})


def _verifier_quota() -> None:
    quota = int(getattr(settings, "DOCUMENTS_QUOTA_MO", 0))
    if quota <= 0:
        return
    versions = DocumentVersion.all_objects.aggregate(a=Sum("taille_docx"), b=Sum("taille_pdf"))
    gabarits = GabaritDocument.all_objects.aggregate(a=Sum("taille"))
    total = (versions["a"] or 0) + (versions["b"] or 0) + (gabarits["a"] or 0)
    if total >= quota * _MO:
        raise RegleMetierError(
            "Le quota de stockage des documents est atteint : contactez l'administrateur."
        )


def _document_sous_verrou(type_document: str, objet: Any, mission: Any, by: User) -> Document:
    """Existing document of the object (row locked) or a new one with the next number."""
    content_type = ContentType.objects.get_for_model(objet)
    filtre = {
        "type_document": type_document,
        "content_type": content_type,
        "object_id": objet.pk,
    }
    document: Document | None = Document.objects.select_for_update().filter(**filtre).first()
    if document is not None:
        return document
    numero, annee, sequence = attribuer_numero(type_document, mission=mission)
    # The advisory lock is held: a concurrent request may have created it while we waited.
    concurrent: Document | None = Document.objects.select_for_update().filter(**filtre).first()
    if concurrent is not None:
        return concurrent
    nouveau: Document = Document.objects.create(
        mission=mission,
        numero=numero,
        annee=annee,
        sequence=sequence,
        created_by=by,
        **filtre,
    )
    return nouveau


@transaction.atomic
def demander_generation(*, type_document: str, objet_id: Any, by: User) -> DocumentVersion:
    """Capture the context and queue the generation of a new version (rights: see the view)."""
    from .. import tasks

    t = type_enregistre(type_document)
    fournisseur = t.fournisseur
    objet = fournisseur.objet(objet_id)
    if raison := fournisseur.raison_non_generable(objet):
        raise RegleMetierError(raison)
    mission = fournisseur.mission_de(objet)
    if mission.statut in STATUTS_FIGES:
        raise RegleMetierError(
            f"La mission {mission.reference} est {mission.get_statut_display().lower()} : "
            "aucun document ne peut être généré."
        )
    gabarit = GabaritDocument.objects.filter(
        type_document=type_document, statut=StatutGabarit.ACTIF
    ).first()
    if gabarit is None:
        raise RegleMetierError("Aucun gabarit actif pour ce type de document.")
    if gabarit.contrat_version != t.contrat.version:
        raise RegleMetierError(
            "Le gabarit actif a été validé pour une version antérieure du contrat : "
            "l'administrateur doit le réactiver."
        )
    _verifier_quota()

    document = _document_sous_verrou(type_document, objet, mission, by)
    versions = list(document.versions.order_by("-numero_version"))
    if any(v.statut in _EN_COURS for v in versions):
        raise RegleMetierError("Une génération est déjà en cours.")
    numero_version = (versions[0].numero_version if versions else 0) + 1

    maintenant = timezone.localtime()
    contexte: dict[str, Any] = {
        "onea": dict(getattr(settings, "DOCUMENTS_ORGANISATION", _ORGANISATION_DEFAUT)),
        "document": {
            "numero": document.numero,
            "version": str(numero_version),
            "type": t.libelle,
            "genere_le": maintenant.strftime("%d/%m/%Y"),
            "genere_par": _nom_utilisateur(by),
        },
        **fournisseur.contexte(objet),
    }
    if ecarts := ecarts_contexte(t.contrat, contexte):
        logger.error("Contexte non conforme au contrat %s : %s", t.contrat.code, ecarts)
        raise ContratNonRespecteError(" ".join(ecarts))
    empreinte = empreinte_contexte(contexte)
    derniere = next((v for v in versions if v.statut != StatutGeneration.ECHEC), None)
    if derniere and derniere.empreinte_contexte == empreinte and derniere.gabarit_id == gabarit.pk:
        raise RegleMetierError(
            "Le document est déjà à jour : aucune donnée n'a changé depuis la version "
            f"{derniere.numero_version}."
        )

    version: DocumentVersion = DocumentVersion.objects.create(
        document=document,
        numero_version=numero_version,
        gabarit=gabarit,
        contexte=contexte,
        empreinte_contexte=empreinte,
        confirmation=fournisseur.confirmation(objet),
        demandee_par=by,
        created_by=by,
    )
    transaction.on_commit(lambda: tasks.generer_version.delay(str(version.pk)))
    return version


def _echec(version_id: str, message: str) -> None:
    with transaction.atomic():
        version = DocumentVersion.objects.select_for_update().get(pk=version_id)
        if version.statut in (StatutGeneration.PRETE, StatutGeneration.ECHEC):
            return
        version.statut = StatutGeneration.ECHEC
        version.erreur = message
        version.save(update_fields=["statut", "erreur", "updated_at"])


def executer_generation(version_id: str) -> None:
    """Worker side: render, store and mark the version ready (idempotent)."""
    from .. import tasks

    with transaction.atomic():
        version = (
            DocumentVersion.objects.select_for_update()
            .select_related("document", "gabarit")
            .get(pk=version_id)
        )
        if version.statut in (StatutGeneration.PRETE, StatutGeneration.ECHEC):
            return
        version.statut = StatutGeneration.EN_COURS
        version.debut_traitement = timezone.now()
        version.save(update_fields=["statut", "debut_traitement", "updated_at"])
    t = type_enregistre(version.document.type_document)
    cle = cle_version(version.document_id, version.numero_version, "docx")
    try:
        try:
            contenu = rendre_docx(
                lire(str(version.gabarit.fichier.name)), version.contexte, t.contrat
            )
            _, empreinte = ecrire_avec_empreinte(cle, contenu)
        except FichierExistantError:
            contenu = lire(cle)  # left by an interrupted attempt: complete (atomic write)
            empreinte = hashlib.sha256(contenu).hexdigest()
    except RenduError as exc:
        _echec(version_id, str(exc))
        return
    except (EspaceInsuffisantError, StockageIndisponibleError) as exc:
        _echec(version_id, exc.message)
        return
    with transaction.atomic():
        version = DocumentVersion.objects.select_for_update().get(pk=version_id)
        version.fichier_docx = cle
        version.empreinte_docx = empreinte
        version.taille_docx = len(contenu)
        version.statut = StatutGeneration.PRETE
        version.statut_pdf = StatutPdf.EN_COURS
        version.genere_le = timezone.now()
        version.debut_traitement = timezone.now()
        version.save()
        transaction.on_commit(lambda: tasks.convertir_pdf.delay(version_id))


def marquer_echec_pdf(version_id: str, raison: str) -> None:
    with transaction.atomic():
        version = DocumentVersion.objects.select_for_update().get(pk=version_id)
        if version.statut_pdf != StatutPdf.EN_COURS:
            return
        version.statut_pdf = StatutPdf.ECHEC
        version.erreur_pdf = (
            f"La conversion PDF a échoué : {raison}. Le document Word reste disponible."
        )
        version.save(update_fields=["statut_pdf", "erreur_pdf", "updated_at"])


def executer_conversion(version_id: str) -> None:
    """Worker side: convert the Word file to PDF (idempotent). Raises on Gotenberg outage."""
    version = DocumentVersion.objects.select_related("document").get(pk=version_id)
    if version.statut != StatutGeneration.PRETE or version.statut_pdf != StatutPdf.EN_COURS:
        return
    cle = cle_version(version.document_id, version.numero_version, "pdf")
    try:
        contenu = pdf.convertir_en_pdf(
            lire(str(version.fichier_docx.name)),
            nom=f"{version.document.numero.replace('/', '-')}.docx",
        )
        _, empreinte = ecrire_avec_empreinte(cle, contenu)
    except FichierExistantError:
        contenu = lire(cle)
        empreinte = hashlib.sha256(contenu).hexdigest()
    except pdf.ConversionPdfError as exc:
        marquer_echec_pdf(version_id, str(exc).rstrip("."))
        return
    except (EspaceInsuffisantError, StockageIndisponibleError) as exc:
        marquer_echec_pdf(version_id, exc.message.rstrip("."))
        return
    with transaction.atomic():
        version = DocumentVersion.objects.select_for_update().get(pk=version_id)
        version.fichier_pdf = cle
        version.empreinte_pdf = empreinte
        version.taille_pdf = len(contenu)
        version.statut_pdf = StatutPdf.PRET
        version.pdf_le = timezone.now()
        version.erreur_pdf = ""
        version.save()


def balayer() -> int:
    """Fail generations and conversions stuck for more than 15 minutes; return the count."""
    limite = timezone.now() - DELAI_BLOCAGE
    nombre = DocumentVersion.objects.filter(
        statut=StatutGeneration.EN_ATTENTE, created_at__lt=limite
    ).update(statut=StatutGeneration.ECHEC, erreur="La génération a été interrompue : relancez-la.")
    nombre += DocumentVersion.objects.filter(
        statut=StatutGeneration.EN_COURS, debut_traitement__lt=limite
    ).update(statut=StatutGeneration.ECHEC, erreur="La génération a été interrompue : relancez-la.")
    nombre += DocumentVersion.objects.filter(
        statut=StatutGeneration.PRETE, statut_pdf=StatutPdf.EN_COURS, debut_traitement__lt=limite
    ).update(
        statut_pdf=StatutPdf.ECHEC,
        erreur_pdf="La conversion PDF a été interrompue : relancez-la. "
        "Le document Word reste disponible.",
    )
    return nombre


def relancer_pdf(version: DocumentVersion, *, by: User) -> DocumentVersion:
    """Queue the PDF conversion again after a failure."""
    from .. import tasks

    with transaction.atomic():
        courante = DocumentVersion.objects.select_for_update().get(pk=version.pk)
        if courante.statut_pdf != StatutPdf.ECHEC:
            raise RegleMetierError("Le PDF ne peut être relancé que si la conversion a échoué.")
        courante.statut_pdf = StatutPdf.EN_COURS
        courante.erreur_pdf = ""
        courante.debut_traitement = timezone.now()
        courante.updated_by = by
        courante.save()
        transaction.on_commit(lambda: tasks.convertir_pdf.delay(str(courante.pk)))
    result: DocumentVersion = courante
    return result


def _verifier_fichier(cle: str, attendue: str) -> bool:
    try:
        return hashlib.sha256(lire(cle)).hexdigest() == attendue
    except (OSError, ValueError):
        return False


def verifier_integrite(version: DocumentVersion) -> dict[str, bool | None]:
    """SHA-256 check of the stored files; None when the file does not exist (yet)."""
    return {
        "docx": _verifier_fichier(str(version.fichier_docx.name), version.empreinte_docx)
        if version.fichier_docx
        else None,
        "pdf": _verifier_fichier(str(version.fichier_pdf.name), version.empreinte_pdf)
        if version.fichier_pdf
        else None,
    }


def ouvrir_version(
    version: DocumentVersion,
    *,
    format: str,
    by: User,
    adresse_ip: str | None,  # noqa: A002
) -> tuple[bytes, str]:
    """Return (content, file name) of a version after an integrity check; trace the access."""
    if format not in FormatFichier.values:
        raise RegleMetierError("Format inconnu.")
    if version.statut != StatutGeneration.PRETE:
        raise RegleMetierError("Le document n'est pas encore généré.")
    if format == FormatFichier.PDF:
        if version.statut_pdf != StatutPdf.PRET:
            raise RegleMetierError("Le PDF n'est pas encore disponible.")
        cle, attendue, extension = str(version.fichier_pdf.name), version.empreinte_pdf, "pdf"
    else:
        cle, attendue, extension = str(version.fichier_docx.name), version.empreinte_docx, "docx"
    try:
        contenu = lire(cle)
    except OSError:
        contenu = b""
        reel = ""
    else:
        reel = hashlib.sha256(contenu).hexdigest()
    if reel != attendue:
        logger.critical(
            "Intégrité compromise : version %s, fichier %s absent ou altéré.", version.pk, cle
        )
        raise IntegriteError
    ConsultationDocument.objects.create(
        version=version,
        utilisateur=by,
        le=timezone.now(),
        format=format,
        adresse_ip=adresse_ip,
        created_by=by,
    )
    nom = f"{version.document.numero.replace('/', '-')}_v{version.numero_version}.{extension}"
    return contenu, nom
