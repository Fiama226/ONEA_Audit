"""Intégrité des pièces : vérification de l'empreinte SHA-256 à chaque lecture et en lot."""

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from apps.documents.integrite import verifier_empreinte
from apps.missions.models import Mission

from ..models import PieceJustificative
from ..stockage import FichierIntrouvableError, empreinte_fichier, stockage_preuves

logger = logging.getLogger(__name__)

ABSENT = "fichier absent"


@dataclass(frozen=True)
class EcartIntegrite:
    piece: PieceJustificative
    attendu: str
    obtenu: str  # empreinte calculée, ou « fichier absent »


def ouvrir_piece_verifiee(piece: PieceJustificative) -> BinaryIO:
    """Relit le fichier, vérifie son empreinte, puis le rend en lecture.

    Empreinte différente : `IntegriteError` (409) et journal CRITICAL. Fichier absent :
    `FichierIntrouvableError`, journalisé en CRITICAL. Le contenu n'est jamais livré avant
    vérification (50 Mo au plus).
    """
    try:
        with stockage_preuves().ouvrir(piece.cle_stockage) as flux:
            contenu = flux.read()
    except FichierIntrouvableError:
        logger.critical("Fichier de pièce absent : pièce %s, clé %s.", piece.pk, piece.cle_stockage)
        raise
    verifier_empreinte(contenu, piece.empreinte_sha256, f"pièce {piece.pk}")
    return BytesIO(contenu)


def verifier_toutes(mission: Mission | None = None) -> list[EcartIntegrite]:
    """Compare l'empreinte de chaque pièce (supprimées logiquement incluses) à son fichier."""
    pieces = PieceJustificative.all_objects.select_related("mission").order_by(
        "mission__reference", "numero"
    )
    if mission is not None:
        pieces = pieces.filter(mission=mission)
    stockage = stockage_preuves()
    ecarts: list[EcartIntegrite] = []
    for piece in pieces:
        try:
            obtenu = empreinte_fichier(stockage, piece.cle_stockage)
        except FichierIntrouvableError:
            obtenu = ABSENT
        if obtenu != piece.empreinte_sha256:
            logger.critical("Écart d'intégrité : pièce %s (%s).", piece.pk, obtenu)
            ecarts.append(EcartIntegrite(piece, piece.empreinte_sha256, obtenu))
    return ecarts
