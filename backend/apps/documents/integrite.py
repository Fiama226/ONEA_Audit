"""Integrity check of stored files against their recorded SHA-256 fingerprint."""

import hashlib
import hmac
import logging

from apps.core.exceptions import RegleMetierError

logger = logging.getLogger(__name__)


class IntegriteError(RegleMetierError):
    """A stored file no longer matches its recorded fingerprint (conflict, not a user error).

    Mapped to HTTP 409 (not the default 422) through `status_http`, by the shared handler.
    """

    status_http = 409

    def __init__(self) -> None:
        super().__init__(
            "Le fichier stocké est altéré : son empreinte ne correspond plus. "
            "Contactez l'administrateur."
        )


def verifier_empreinte(contenu: bytes, attendue: str, contexte: str) -> None:
    """Raise `IntegriteError` (and log CRITICAL) if SHA-256 of `contenu` differs from `attendue`."""
    reelle = hashlib.sha256(contenu).hexdigest()
    if not hmac.compare_digest(reelle, attendue or ""):
        logger.critical(
            "Empreinte invalide (%s) : attendue %s, calculée %s.", contexte, attendue, reelle
        )
        raise IntegriteError
