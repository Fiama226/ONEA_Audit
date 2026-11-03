"""Signature électronique PAdES (lot 7 bis, pyHanko, licence MIT).

Le certificat de l'ONEA (PKCS#12) est lu dans la configuration (`SIGNATURE_PKCS12_FILE`, phrase
secrète par `env_secret`) ; il n'est jamais copié en base ni dans le stockage des documents. Le
PDF produit par Gotenberg est signé par ajout incrémental (le fichier d'origine n'est pas
réécrit, donc compatible PDF/A) et rangé en écriture unique sous une clé distincte. Le PDF
d'origine reste intact et vérifiable par son empreinte.
"""

import hashlib
import logging
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from asn1crypto import pem
from asn1crypto import x509 as asn1_x509
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, timestamps, validation
from pyhanko.sign.diff_analysis import ModificationLevel
from pyhanko.stamp import TextStampStyle
from pyhanko_certvalidator import ValidationContext

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer
from apps.documents.integrite import IntegriteError, verifier_empreinte
from apps.documents.models import DocumentVersion, StatutPdf
from apps.documents.stockage import cle_signature, ecrire_avec_empreinte, lire
from apps.users.models import User

from .electronique import ResultatVerification
from .models import SignatureElectronique

logger = logging.getLogger(__name__)

MSG_NON_CONFIGUREE = (
    "La signature électronique n'est pas configurée sur cette plateforme : "
    "le certificat de l'ONEA n'a pas été fourni."
)
MSG_CERTIFICAT = "Le certificat de signature est illisible ou sa phrase secrète est erronée."
MSG_PDF = "Le PDF du document n'est pas disponible : la signature est impossible."
MSG_DEJA = "Ce document est déjà signé."
MSG_NON_SIGNE = "Le document n'est pas signé électroniquement."

_BOITE = (40, 30, 400, 90)  # cadre visible en bas de la dernière page (points PDF)


def _charger_signataire() -> signers.SimpleSigner:
    chemin = str(getattr(settings, "SIGNATURE_PKCS12_FILE", ""))
    if not chemin:
        raise RegleMetierError(MSG_NON_CONFIGUREE)
    phrase = str(getattr(settings, "SIGNATURE_PKCS12_PASSPHRASE", ""))
    try:
        signataire = signers.SimpleSigner.load_pkcs12(  # type: ignore[no-untyped-call]
            chemin, passphrase=phrase.encode("utf-8") if phrase else None
        )
    except Exception as exc:  # noqa: BLE001 - fichier absent, corrompu ou phrase erronée
        logger.error("Certificat de signature illisible (%s).", type(exc).__name__)
        raise RegleMetierError(MSG_CERTIFICAT) from exc
    if signataire is None or signataire.signing_cert is None:
        raise RegleMetierError(MSG_CERTIFICAT)
    result: signers.SimpleSigner = signataire
    return result


def _ancres(signataire: signers.SimpleSigner) -> list[asn1_x509.Certificate]:
    """Ancres de confiance : bundle PEM configuré, sinon le certificat de signature lui-même."""
    chemin = str(getattr(settings, "SIGNATURE_ANCRES_CONFIANCE", ""))
    if not chemin:
        return [signataire.signing_cert] if signataire.signing_cert else []
    try:
        contenu = Path(chemin).read_bytes()
    except OSError as exc:
        raise RegleMetierError(
            "Les ancres de confiance de la signature électronique sont illisibles."
        ) from exc
    return [
        asn1_x509.Certificate.load(octets) for _, _, octets in pem.unarmor(contenu, multiple=True)
    ]


def _horodateur() -> timestamps.HTTPTimeStamper | None:
    url = str(getattr(settings, "SIGNATURE_TSA_URL", ""))
    return timestamps.HTTPTimeStamper(url) if url else None


def _echapper(texte: str) -> str:
    return texte.replace("%", "%%")


def _pdf_source(version: DocumentVersion) -> bytes:
    if version.statut_pdf != StatutPdf.PRET or not version.fichier_pdf:
        raise RegleMetierError(MSG_PDF)
    contenu = lire(str(version.fichier_pdf.name))
    verifier_empreinte(contenu, version.empreinte_pdf, f"pdf {version.pk}")
    return contenu


def signature_de(version: DocumentVersion) -> SignatureElectronique | None:
    return SignatureElectronique.objects.filter(version=version).first()


def lire_pdf_signe(signature: SignatureElectronique) -> bytes:
    """Contenu du PDF signé, après contrôle de son empreinte (IntegriteError -> 409)."""
    contenu = lire(signature.cle_stockage)
    verifier_empreinte(contenu, signature.empreinte_pdf_signe, f"pdf signé {signature.pk}")
    return contenu


class SignatairePades:
    """Implémentation PAdES du point d'extension `SignataireElectronique`."""

    def est_signee(self, version: DocumentVersion) -> bool:
        return signature_de(version) is not None

    def signer(
        self,
        version: DocumentVersion,
        *,
        by: User,
        raison: str = "",
        lieu: str = "",
    ) -> SignatureElectronique:
        """Signe le PDF de `version` ; une seule signature par version, écriture unique."""
        if signature_de(version) is not None:
            raise RegleMetierError(MSG_DEJA)
        signataire = _charger_signataire()
        source = _pdf_source(version)
        maintenant = timezone.now()
        nom = by.get_full_name() or by.get_username()
        raison = raison.strip() or f"Validation par {nom}"
        texte = _echapper(
            f"Validé par {nom}\nSigné électroniquement le "
            f"{maintenant.astimezone(UTC):%d/%m/%Y à %H:%M} UTC\nONEA - Audit interne"
        )
        meta = signers.PdfSignatureMetadata(
            field_name="SignatureRAI",
            reason=raison,
            location=lieu.strip() or None,
            md_algorithm="sha256",
        )
        horodateur = _horodateur()
        signeur = signers.PdfSigner(
            meta,
            signer=signataire,
            timestamper=horodateur,
            stamp_style=TextStampStyle(stamp_text=texte),
            new_field_spec=fields.SigFieldSpec("SignatureRAI", on_page=-1, box=_BOITE),
        )
        try:
            ecrivain = IncrementalPdfFileWriter(BytesIO(source))
            sortie = BytesIO()
            signeur.sign_pdf(ecrivain, output=sortie)
        except RegleMetierError:
            raise
        except Exception as exc:  # noqa: BLE001 - PDF inexploitable ou horodatage injoignable
            logger.error("Signature PAdES impossible (%s).", type(exc).__name__, exc_info=True)
            raise RegleMetierError(
                "La signature du document a échoué : le PDF est inexploitable ou le serveur "
                "d'horodatage est injoignable."
            ) from exc
        contenu = sortie.getvalue()
        cert = signataire.signing_cert
        if cert is None:  # garanti par _charger_signataire
            raise RegleMetierError(MSG_CERTIFICAT)
        with transaction.atomic():
            cle, empreinte = ecrire_avec_empreinte(cle_signature(version.pk), contenu)
            signature = SignatureElectronique(
                version=version,
                signe_par=by,
                signe_le=maintenant,
                sujet=cert.subject.human_friendly[:500],
                emetteur=cert.issuer.human_friendly[:500],
                numero_serie=str(cert.serial_number),
                empreinte_certificat=hashlib.sha256(cert.dump()).hexdigest(),
                raison=raison[:300],
                lieu=lieu.strip()[:200],
                cle_stockage=cle,
                empreinte_pdf_signe=empreinte,
                taille=len(contenu),
                horodatage_tsa=horodateur is not None,
            )
            try:
                enregistrer(signature, by=by, creation=True)
            except IntegrityError as exc:  # pragma: no cover - course entre deux signatures
                raise RegleMetierError(MSG_DEJA) from exc
        return signature

    def verifier(self, version: DocumentVersion) -> ResultatVerification:
        signature = signature_de(version)
        if signature is None:
            return ResultatVerification(False, "", None, MSG_NON_SIGNE)
        try:
            contenu = lire_pdf_signe(signature)
        except IntegriteError:
            return ResultatVerification(
                False, signature.sujet, signature.signe_le, "Le PDF signé a été altéré."
            )
        except OSError:
            return ResultatVerification(
                False, signature.sujet, signature.signe_le, "Le PDF signé est introuvable."
            )
        return self._valider(contenu, signature)

    def _valider(self, contenu: bytes, signature: SignatureElectronique) -> ResultatVerification:
        try:
            ancres = _ancres(_charger_signataire())
            lecteur = PdfFileReader(BytesIO(contenu))
            signatures = lecteur.embedded_regular_signatures
            if not signatures:
                return ResultatVerification(
                    False, signature.sujet, signature.signe_le, "Aucune signature dans le PDF."
                )
            contexte = ValidationContext(trust_roots=ancres, allow_fetching=False)
            statut: Any = validation.validate_pdf_signature(
                signatures[-1], signer_validation_context=contexte
            )
        except RegleMetierError as exc:
            return ResultatVerification(False, signature.sujet, signature.signe_le, exc.message)
        except Exception as exc:  # noqa: BLE001 - PDF mal formé : invalide, jamais une erreur 500
            logger.warning("Vérification PAdES impossible (%s).", type(exc).__name__)
            return ResultatVerification(
                False, signature.sujet, signature.signe_le, "La signature est illisible."
            )
        sujet = statut.signing_cert.subject.human_friendly
        horodatage: datetime | None = statut.signer_reported_dt or signature.signe_le
        motif = ""
        if not statut.intact:
            motif = "Le document a été modifié après sa signature."
        elif not statut.valid:
            motif = "La signature est invalide."
        elif not statut.trusted:
            motif = "Le certificat du signataire n'est pas reconnu (ancre de confiance)."
        elif statut.modification_level not in (None, ModificationLevel.NONE):
            motif = "Le document a été modifié après sa signature."
        return ResultatVerification(motif == "", sujet, horodatage, motif)
