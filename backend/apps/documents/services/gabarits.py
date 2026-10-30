"""Template (gabarit) services: upload, activation, preview and download.

The PDF preview is synchronous (one Gotenberg call in the request); it renders the example
context only, never user data.
"""

import hashlib
import io
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.core import antivirus
from apps.core.exceptions import RegleMetierError
from apps.core.fichiers import controler_televersement
from apps.core.services import enregistrer
from apps.users.models import User

from ..integrite import verifier_empreinte
from ..models import (
    ConsultationDocument,
    FormatFichier,
    GabaritDocument,
    StatutGabarit,
)
from ..moteur.analyse import analyser_gabarit
from ..moteur.exceptions import RenduError
from ..moteur.registre import type_document as trouver_type
from ..moteur.rendu import rendre_docx
from ..pdf import ConversionPdfError, GotenbergIndisponibleError, convertir_en_pdf
from ..stockage import FichierExistantError, cle_gabarit, ecrire, lire
from .quota import controler_quota

MSG_PDF_INDISPONIBLE = "Le service de conversion PDF est indisponible : réessayez plus tard."
LOCK_GABARIT = 0x47414252  # « GABR »
_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


def _contenu(gabarit: GabaritDocument) -> bytes:
    """Stored bytes of a template, verified against its recorded fingerprint."""
    contenu = lire(gabarit.fichier.name or "")
    verifier_empreinte(
        contenu, gabarit.empreinte, f"gabarit {gabarit.type_document} v{gabarit.version}"
    )
    return contenu


def verrouiller_type(code: str) -> None:
    """Serialise the writers of one document type (effective before its first template too)."""
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))", [LOCK_GABARIT, code])


def _nom_sur(nom: str) -> str:
    nom = _CONTROLE.sub("", nom.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    if len(nom) > 255:
        racine, point, ext = nom.rpartition(".")
        nom = f"{racine[: 255 - len(ext) - 1]}.{ext}" if point else nom[:255]
    return nom or "gabarit.docx"


def _ecrire_idempotent(cle: str, contenu: bytes) -> None:
    try:
        ecrire(cle, contenu)
    except FichierExistantError:
        # leftover of a failed attempt: accepted only if byte-identical
        if hashlib.sha256(lire(cle)).digest() != hashlib.sha256(contenu).digest():
            raise


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
    t = trouver_type(type_document)
    nom_original = _nom_sur(nom_original)
    # Contrôle commun (type réel, taille, archive sans macro) puis antivirus, avant toute analyse.
    flux = io.BytesIO(contenu)
    flux.name = nom_original
    if not nom_original.lower().endswith(".doc"):  # .doc : message dédié de l'analyseur
        controler_televersement(
            flux,
            extensions=frozenset({"docx"}),
            taille_max=settings.DOCUMENTS_MAX_GABARIT_MO * 1024 * 1024,
        )
    antivirus.analyser(flux)
    # D4: analyse before any write
    balises = analyser_gabarit(
        contenu,
        t.contrat,
        nom_fichier=nom_original,
        taille_max_mo=settings.DOCUMENTS_MAX_GABARIT_MO,
    )
    controler_quota(len(contenu))
    verrouiller_type(t.code)
    version = (
        GabaritDocument.all_objects.filter(type_document=t.code).aggregate(m=Max("version"))["m"]
        or 0
    ) + 1
    empreinte = hashlib.sha256(contenu).hexdigest()
    cle = cle_gabarit(t.code, version, empreinte)
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
    # validate first: nothing is stored when the data is invalid
    try:
        gabarit.full_clean(validate_constraints=False)
    except ValidationError as e:
        raise RegleMetierError("Données invalides.", dict(e.message_dict)) from e
    _ecrire_idempotent(cle, contenu)  # file last; a retry reuses an identical leftover
    enregistrer(gabarit, by=by, creation=True)
    return gabarit


@transaction.atomic
def activer_gabarit(gabarit: GabaritDocument, *, by: User) -> GabaritDocument:
    verrouiller_type(gabarit.type_document)
    gabarit.refresh_from_db()
    if gabarit.deleted_at is not None:
        raise RegleMetierError("Ce gabarit a été supprimé : il ne peut pas être activé.")
    if gabarit.statut == StatutGabarit.ACTIF:
        return gabarit
    t = trouver_type(gabarit.type_document)
    balises = analyser_gabarit(
        _contenu(gabarit),
        t.contrat,
        nom_fichier=gabarit.nom_original,
        taille_max_mo=settings.DOCUMENTS_MAX_GABARIT_MO,
    )
    precedents = GabaritDocument.all_objects.filter(
        type_document=gabarit.type_document, statut=StatutGabarit.ACTIF
    )
    for precedent in precedents:
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
    t = trouver_type(type_document_code)
    gabarit: GabaritDocument | None = GabaritDocument.objects.filter(
        type_document=t.code, statut=StatutGabarit.ACTIF
    ).first()
    if gabarit is None:
        raise RegleMetierError(
            f"Aucun gabarit actif pour « {t.libelle} » : l'administrateur doit en déposer un."
        )
    return gabarit


def apercu_gabarit(gabarit: GabaritDocument, *, format: str) -> tuple[bytes, str]:  # noqa: A002
    t = trouver_type(gabarit.type_document)
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
