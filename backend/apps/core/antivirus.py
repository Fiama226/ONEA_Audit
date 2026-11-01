"""Analyse antivirus : moteur `aucun` (développement) ou `clamav` (démon clamd, INSTREAM).

Le client n'utilise que la bibliothèque standard ; ClamAV tourne dans un conteneur séparé
(GPL-2.0, aucun lien de code avec l'application). Réglages lus à chaque appel :
`ANTIVIRUS_MOTEUR` (`aucun`, `clamav` ; `clamd` est un synonyme), `ANTIVIRUS_CLAMD_HOTE`,
`ANTIVIRUS_CLAMD_PORT`, `ANTIVIRUS_ECHEC_FERME` (défaut vrai) et `ANTIVIRUS_TAILLE_MAX_OCTETS`
(défaut : taille maximale des pièces, 50 Mo). Politique par défaut (échec fermé) : si l'analyse
est indisponible, le fichier est refusé (503), jamais accepté sans analyse. Avec
`ANTIVIRUS_ECHEC_FERME=false` (choix explicite), l'indisponibilité est journalisée en ERROR et le
fichier accepté ; une détection (FOUND) ou un fichier trop gros sont toujours refusés.
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
MSG_TROP_GROS: Final = "Le fichier est trop volumineux pour être analysé par l'antivirus."
MOTEURS_CLAMD: Final = frozenset({"clamd", "clamav"})


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
    if "size limit exceeded" in texte.lower():
        logger.warning("Fichier trop gros pour clamd : %s", texte[:200])
        raise FichierRefuseError(MSG_TROP_GROS)
    if not texte.endswith("OK"):
        logger.warning("Réponse antivirus inattendue : %s", texte[:200])
        raise AntivirusIndisponibleError


def _taille(flux: Any) -> int:
    flux.seek(0, 2)
    taille = int(flux.tell())
    flux.seek(0)
    return taille


def analyser(flux: Any) -> None:
    """Analyse le flux (replacé au début) ; 400 si infecté ou trop gros, 503 si indisponible."""
    moteur = str(settings.ANTIVIRUS_MOTEUR)
    if moteur == "aucun":
        return
    if moteur not in MOTEURS_CLAMD:  # garde-fou : les réglages valident déjà la valeur
        raise AntivirusIndisponibleError
    if _taille(flux) > int(settings.ANTIVIRUS_TAILLE_MAX_OCTETS):
        raise FichierRefuseError(MSG_TROP_GROS)
    try:
        _analyser_clamd(flux)
    except AntivirusIndisponibleError:
        if getattr(settings, "ANTIVIRUS_ECHEC_FERME", True):
            raise
        logger.error("Antivirus indisponible, fichier accepté sans analyse (échec ouvert)")
    finally:
        flux.seek(0)
