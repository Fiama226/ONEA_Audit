"""Client Gotenberg : conversion d'un document Word (docx) en PDF."""

import requests
from django.conf import settings

CONNECT_TIMEOUT = 5
PDFA_PROFIL = "PDF/A-2b"


class GotenbergIndisponibleError(Exception):
    """Gotenberg injoignable, trop lent ou en erreur serveur (réessayable)."""


class ConversionPdfError(Exception):
    """Gotenberg a refusé le document ou renvoyé une réponse qui n'est pas un PDF."""


def convertir_en_pdf(docx: bytes, *, nom: str = "document.docx", pdfa: bool | None = None) -> bytes:
    """Convertit ``docx`` en PDF (PDF/A-2b si ``pdfa``, sinon ``settings.DOCUMENTS_PDFA``)."""
    if pdfa is None:
        pdfa = bool(getattr(settings, "DOCUMENTS_PDFA", True))
    url = f"{getattr(settings, 'GOTENBERG_URL', 'http://localhost:3000')}/forms/libreoffice/convert"
    timeout = (CONNECT_TIMEOUT, getattr(settings, "GOTENBERG_TIMEOUT", 60))
    data = {"pdfa": PDFA_PROFIL} if pdfa else {}
    try:
        reponse = requests.post(
            url,
            files={"files": (nom, docx)},
            data=data,
            timeout=timeout,
            allow_redirects=False,
        )
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise GotenbergIndisponibleError("Le service de conversion PDF est indisponible.") from exc
    except requests.RequestException as exc:
        raise ConversionPdfError("Échec de la requête de conversion PDF.") from exc

    if reponse.status_code >= 500:
        raise GotenbergIndisponibleError(
            f"Le service de conversion PDF a répondu {reponse.status_code}."
        )
    if reponse.status_code != 200:
        raise ConversionPdfError(f"Conversion PDF refusée (code {reponse.status_code}).")
    if not reponse.content.startswith(b"%PDF-"):
        raise ConversionPdfError("La réponse du service de conversion n'est pas un PDF.")
    return reponse.content
