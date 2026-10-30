"""Point d'extension antivirus : moteur `aucun` (défaut) ou client `clamd` (INSTREAM).

Le client n'utilise que la bibliothèque standard. Le moteur est lu à chaque appel dans les
réglages (`ANTIVIRUS_MOTEUR`, `ANTIVIRUS_CLAMD_HOTE`, `ANTIVIRUS_CLAMD_PORT`). Politique : en
cas d'indisponibilité de l'analyse, le fichier est refusé (503), jamais accepté sans analyse.
Le démon doit accepter la taille maximale des fichiers (`StreamMaxLength` >= 50 Mo).
"""

import logging
import socket
import struct
from typing import Any, Final

from django.conf import settings

from .exceptions import RegleMetierError
from .fichiers import FichierRefuseError

logger = logging.getLogger(__name__)

DELAI_SECONDES: Final = 30.0
_BLOC: Final = 64 * 1024
MSG_REFUSE: Final = "Le fichier a été refusé par l'analyse antivirus."
MSG_INDISPONIBLE: Final = "Analyse antivirus indisponible : réessayez plus tard."


class AntivirusIndisponibleError(RegleMetierError):
    """Le moteur d'analyse ne répond pas ou répond une erreur : HTTP 503."""

    status_http = 503

    def __init__(self) -> None:
        super().__init__(MSG_INDISPONIBLE, {"fichier": [MSG_INDISPONIBLE]})


def _analyser_clamd(flux: Any) -> None:
    hote = str(settings.ANTIVIRUS_CLAMD_HOTE)
    port = int(settings.ANTIVIRUS_CLAMD_PORT)
    try:
        with socket.create_connection((hote, port), timeout=DELAI_SECONDES) as sock:
            sock.settimeout(DELAI_SECONDES)
            sock.sendall(b"zINSTREAM\x00")
            while bloc := flux.read(_BLOC):
                sock.sendall(struct.pack("!I", len(bloc)) + bloc)
            sock.sendall(struct.pack("!I", 0))
            reponse = b""
            while len(reponse) < 4096:
                lu = sock.recv(1024)
                if not lu:
                    break
                reponse += lu
                if b"\x00" in reponse or b"\n" in reponse:
                    break
    except OSError as exc:  # injoignable, refus, délai dépassé, connexion coupée
        logger.warning("Antivirus clamd injoignable : %s", type(exc).__name__)
        raise AntivirusIndisponibleError from exc
    texte = reponse.strip(b"\x00\r\n ").decode("ascii", errors="replace")
    if texte.endswith("FOUND"):
        logger.warning("Fichier refusé par l'antivirus : %s", texte)
        raise FichierRefuseError(MSG_REFUSE)
    if not texte.endswith("OK"):
        logger.warning("Réponse antivirus inattendue : %s", texte[:200])
        raise AntivirusIndisponibleError


def analyser(flux: Any) -> None:
    """Analyse le flux (replacé au début) ; lève 400 si infecté, 503 si indisponible."""
    moteur = str(settings.ANTIVIRUS_MOTEUR)
    if moteur == "aucun":
        return
    flux.seek(0)
    try:
        if moteur == "clamd":
            _analyser_clamd(flux)
        else:  # garde-fou : les réglages valident déjà la valeur
            raise AntivirusIndisponibleError
    finally:
        flux.seek(0)
