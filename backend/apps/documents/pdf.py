"""Client Gotenberg : conversion d'un document Word (docx) en PDF."""

import time

import requests
from django.conf import settings

CONNECT_TIMEOUT = 5
PDFA_PROFIL = "PDF/A-2b"
# Cold start of LibreOffice inside Gotenberg can answer 503 for ~30 s: bounded retry.
RETRIES = 2
BACKOFF_SECONDS = 15


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
    reponse: requests.Response | None = None
    for tentative in range(RETRIES + 1):
        if tentative:
            time.sleep(BACKOFF_SECONDS * tentative)
        try:
            reponse = requests.post(
                url,
                files={"files": (nom, docx)},
                data=data,
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise GotenbergIndisponibleError(
                "Le service de conversion PDF est indisponible."
            ) from exc
        except requests.ConnectionError as exc:
            if tentative == RETRIES:
                raise GotenbergIndisponibleError(
                    "Le service de conversion PDF est indisponible."
                ) from exc
            continue
        except requests.RequestException as exc:
            raise ConversionPdfError("Échec de la requête de conversion PDF.") from exc
        if reponse.status_code != 503:
            break

    if reponse is None:  # pragma: no cover - the loop always sets or raises
        raise GotenbergIndisponibleError("Le service de conversion PDF est indisponible.")
    if reponse.status_code >= 500:
        raise GotenbergIndisponibleError(
            f"Le service de conversion PDF a répondu {reponse.status_code}."
        )
    if reponse.status_code != 200:
        raise ConversionPdfError(f"Conversion PDF refusée (code {reponse.status_code}).")
    if not reponse.content.startswith(b"%PDF-"):
        raise ConversionPdfError("La réponse du service de conversion n'est pas un PDF.")
    return reponse.content
