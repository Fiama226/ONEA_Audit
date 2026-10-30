"""Intégrité des pièces : empreinte SHA-256 à chaque lecture, rapprochement disque / base."""

import hashlib
import hmac
import logging
import tempfile
from dataclasses import dataclass
from typing import BinaryIO

from apps.documents.integrite import IntegriteError
from apps.missions.models import Mission

from ..models import PieceJustificative
from ..stockage import BLOC, FichierIntrouvableError, empreinte_fichier, stockage_preuves

logger = logging.getLogger(__name__)

ABSENT = "fichier absent"
ORPHELIN = "fichier orphelin"
_MEMOIRE_MAX = 8 * 1024 * 1024  # au-delà, la copie vérifiée passe par un fichier temporaire


@dataclass(frozen=True)
class EcartIntegrite:
    piece: PieceJustificative | None  # None : fichier sur disque sans ligne en base
    cle: str
    attendu: str
    obtenu: str  # empreinte calculée, « fichier absent » ou « fichier orphelin »


def ouvrir_piece_verifiee(piece: PieceJustificative) -> BinaryIO:
    """Relit le fichier en flux, vérifie son empreinte, puis livre la copie vérifiée.

    Lecture par blocs de 1 Mio, jamais au-delà de `taille_octets` : un fichier plus gros que
    prévu est un écart d'intégrité, sans lecture non bornée. La copie (mémoire puis fichier
    temporaire) est celle qui est servie, ce qui exclut toute course entre vérification et
    envoi. Écart : `IntegriteError` (409) et journal CRITICAL. Fichier absent :
    `FichierIntrouvableError`, aussi journalisé en CRITICAL.
    """
    contexte = f"pièce {piece.pk}"
    copie = tempfile.SpooledTemporaryFile(max_size=_MEMOIRE_MAX)  # noqa: SIM115
    try:
        empreinte = hashlib.sha256()
        lus = 0
        try:
            with stockage_preuves().ouvrir(piece.cle_stockage) as flux:
                while bloc := flux.read(BLOC):
                    lus += len(bloc)
                    if lus > piece.taille_octets:
                        logger.critical(
                            "Fichier plus gros que prévu (%s) : %s octets attendus.",
                            contexte,
                            piece.taille_octets,
                        )
                        raise IntegriteError
                    empreinte.update(bloc)
                    copie.write(bloc)
        except FichierIntrouvableError:
            logger.critical("Fichier de pièce absent : %s, clé %s.", contexte, piece.cle_stockage)
            raise
        obtenue = empreinte.hexdigest()
        if lus != piece.taille_octets or not hmac.compare_digest(
            obtenue, piece.empreinte_sha256 or ""
        ):
            logger.critical(
                "Empreinte invalide (%s) : attendue %s, calculée %s.",
                contexte,
                piece.empreinte_sha256,
                obtenue,
            )
            raise IntegriteError
        copie.seek(0)
    except BaseException:
        copie.close()
        raise
    return copie  # type: ignore[return-value]  # SpooledTemporaryFile se comporte en BinaryIO


def verifier_toutes(mission: Mission | None = None) -> list[EcartIntegrite]:
    """Rapproche disque et base, en lecture seule (rien n'est jamais effacé ni déplacé).

    - pièce dont le fichier est absent ou dont l'empreinte diffère (supprimées logiquement
      incluses) ;
    - fichier présent sur disque sans ligne en base (orphelin : dépôt dont la ligne n'a pas été
      enregistrée, y compris après annulation de la transaction).
    """
    pieces = PieceJustificative.all_objects.select_related("mission").order_by(
        "mission__reference", "numero"
    )
    if mission is not None:
        pieces = pieces.filter(mission=mission)
    stockage = stockage_preuves()
    ecarts: list[EcartIntegrite] = []
    for piece in pieces.iterator():
        try:
            obtenu = empreinte_fichier(stockage, piece.cle_stockage)
        except FichierIntrouvableError:
            obtenu = ABSENT
        if obtenu != piece.empreinte_sha256:
            logger.critical("Écart d'intégrité : pièce %s (%s).", piece.pk, obtenu)
            ecarts.append(EcartIntegrite(piece, piece.cle_stockage, piece.empreinte_sha256, obtenu))

    connues = set(PieceJustificative.all_objects.values_list("cle_stockage", flat=True).iterator())
    prefixe = f"preuves/{mission.pk}/" if mission is not None else ""
    for cle in stockage.cles():
        if cle.startswith(prefixe) and cle not in connues:
            logger.critical("Fichier orphelin (sans pièce en base) : %s.", cle)
            ecarts.append(EcartIntegrite(None, cle, "", ORPHELIN))
    return ecarts
