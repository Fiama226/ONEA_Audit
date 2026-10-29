"""Template (gabarit) services: upload, activation, preview and download."""

import hashlib

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer
from apps.users.models import User

from ..models import (
    ConsultationDocument,
    DocumentVersion,
    FormatFichier,
    GabaritDocument,
    StatutGabarit,
)
from ..moteur.analyse import analyser_gabarit
from ..moteur.exceptions import RenduError
from ..moteur.registre import type_document
from ..moteur.rendu import rendre_docx
from ..pdf import ConversionPdfError, GotenbergIndisponibleError, convertir_en_pdf
from ..stockage import cle_gabarit, ecrire, lire

MSG_PDF_INDISPONIBLE = "Le service de conversion PDF est indisponible : réessayez plus tard."


def _contenu(gabarit: GabaritDocument) -> bytes:
    return lire(gabarit.fichier.name or "")


def _utilise_octets() -> int:
    gabarits = GabaritDocument.all_objects.aggregate(t=Sum("taille"))["t"] or 0
    versions = DocumentVersion.all_objects.aggregate(d=Sum("taille_docx"), p=Sum("taille_pdf"))
    return int(gabarits + (versions["d"] or 0) + (versions["p"] or 0))


def _controler_quota(ajout: int) -> None:
    quota_mo: int = settings.DOCUMENTS_QUOTA_MO
    if quota_mo and _utilise_octets() + ajout > quota_mo * 1024 * 1024:
        raise RegleMetierError(
            "Le quota de stockage des documents est atteint : contactez l'administrateur."
        )


@transaction.atomic
def deposer_gabarit(
    *,
    type_document: str,
    contenu: bytes,
    nom_original: str,
    by: User,
    commentaire: str = "",
    provisoire: bool = False,
) -> GabaritDocument:
    from ..moteur.registre import type_document as trouver

    t = trouver(type_document)
    # D4: analyse before any write
    balises = analyser_gabarit(
        contenu,
        t.contrat,
        nom_fichier=nom_original,
        taille_max_mo=settings.DOCUMENTS_MAX_GABARIT_MO,
    )
    _controler_quota(len(contenu))
    existants = GabaritDocument.all_objects.select_for_update().filter(type_document=t.code)
    list(existants.values_list("pk", flat=True))  # take the row locks
    version = (existants.aggregate(m=Max("version"))["m"] or 0) + 1
    empreinte = hashlib.sha256(contenu).hexdigest()
    cle = ecrire(cle_gabarit(t.code, version, empreinte), contenu)
    gabarit = GabaritDocument(
        type_document=t.code,
        version=version,
        statut=StatutGabarit.DEPOSE,
        fichier=cle,
        nom_original=nom_original,
        taille=len(contenu),
        empreinte=empreinte,
        balises=sorted(balises),
        contrat_version=t.contrat.version,
        provisoire=provisoire,
        commentaire=commentaire,
    )
    enregistrer(gabarit, by=by, creation=True)
    return gabarit


@transaction.atomic
def activer_gabarit(gabarit: GabaritDocument, *, by: User) -> GabaritDocument:
    verrou = GabaritDocument.all_objects.select_for_update().filter(
        type_document=gabarit.type_document
    )
    list(verrou.values_list("pk", flat=True))
    gabarit.refresh_from_db()
    if gabarit.statut == StatutGabarit.ACTIF:
        return gabarit
    t = type_document(gabarit.type_document)
    balises = analyser_gabarit(
        _contenu(gabarit),
        t.contrat,
        nom_fichier=gabarit.nom_original,
        taille_max_mo=settings.DOCUMENTS_MAX_GABARIT_MO,
    )
    for precedent in verrou.filter(statut=StatutGabarit.ACTIF):
        precedent.statut = StatutGabarit.ARCHIVE
        enregistrer(precedent, by=by)
    gabarit.statut = StatutGabarit.ACTIF
    gabarit.active_par = by
    gabarit.active_le = timezone.now()
    gabarit.contrat_version = t.contrat.version
    gabarit.balises = sorted(balises)
    enregistrer(gabarit, by=by)
    return gabarit


def gabarit_actif(type_document_code: str) -> GabaritDocument:
    t = type_document(type_document_code)
    gabarit: GabaritDocument | None = GabaritDocument.objects.filter(
        type_document=t.code, statut=StatutGabarit.ACTIF
    ).first()
    if gabarit is None:
        raise RegleMetierError(
            f"Aucun gabarit actif pour « {t.libelle} » : l'administrateur doit en déposer un."
        )
    return gabarit


def apercu_gabarit(gabarit: GabaritDocument, *, format: str) -> tuple[bytes, str]:  # noqa: A002
    t = type_document(gabarit.type_document)
    base = f"apercu-{t.code.lower()}-v{gabarit.version}"
    try:
        docx = rendre_docx(_contenu(gabarit), t.contrat.exemple, t.contrat)
    except RenduError as exc:
        raise RegleMetierError(str(exc)) from exc
    if format == "docx":
        return docx, f"{base}.docx"
    if format != "pdf":
        raise RegleMetierError("Format inconnu : choisissez docx ou pdf.")
    try:
        return convertir_en_pdf(docx, nom=f"{base}.docx"), f"{base}.pdf"
    except (GotenbergIndisponibleError, ConversionPdfError) as exc:
        raise RegleMetierError(MSG_PDF_INDISPONIBLE) from exc


def fichier_gabarit(
    gabarit: GabaritDocument, *, by: User, adresse_ip: str | None
) -> tuple[bytes, str]:
    contenu = _contenu(gabarit)
    ConsultationDocument.objects.create(
        gabarit=gabarit,
        utilisateur=by,
        le=timezone.now(),
        format=FormatFichier.DOCX,
        adresse_ip=adresse_ip,
        created_by=by,
    )
    return contenu, gabarit.nom_original
