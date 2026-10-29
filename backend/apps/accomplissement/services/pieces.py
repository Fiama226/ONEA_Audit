"""Pièces justificatives : dépôt contrôlé, écriture unique, empreinte SHA-256.

Entrée non fiable : tout est validé AVANT la moindre écriture de fichier (taille déclarée puis
octets réellement lus, liste blanche d'extensions, signature d'octets, nom nettoyé). Le fichier
est écrit en dernier, dans la transaction, juste avant la ligne de base ; la clé est générée par
le stockage. Le contrat de stockage ne permet ni écrasement ni suppression : si la ligne de base
échoue après l'écriture, le fichier orphelin est consigné dans le journal (jamais effacé).
"""

import hashlib
import logging
from typing import Any, BinaryIO, cast

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.users.models import User

from .. import droits_fiches as droits
from ..fichiers import (
    MSG_TAILLE,
    controler_fichier,
    nom_affichable,
    taille_maximale,
)
from ..gardes import ETAPE_FICHES
from ..managers import prochain_numero
from ..models import FicheDeTest, PieceJustificative
from ..stockage import BLOC, stockage_preuves
from .fiches import MSG_XII, exiger_fiche_modifiable, ouvrir_fenetre

logger = logging.getLogger(__name__)

_LONGUEUR_EN_TETE = 16
MSG_LIBELLE = "Le libellé est obligatoire."


def _lire_en_tete_et_empreinte(fichier: "UploadedFile[Any]") -> tuple[bytes, str, int]:
    """Lit le fichier une fois : en-tête, SHA-256 et taille réelle (plafonnée avant le bout)."""
    maximum = taille_maximale()
    if fichier.size is not None and fichier.size > maximum:
        raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})
    fichier.seek(0)
    empreinte = hashlib.sha256()
    taille = 0
    en_tete = b""
    while bloc := fichier.read(BLOC):
        if not en_tete:
            en_tete = bloc[:_LONGUEUR_EN_TETE]
        taille += len(bloc)
        if taille > maximum:  # la taille annoncée peut mentir
            raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})
        empreinte.update(bloc)
    fichier.seek(0)
    return en_tete, empreinte.hexdigest(), taille


@transaction.atomic
def deposer_piece(
    fiche: FicheDeTest,
    *,
    fichier: "UploadedFile[Any]",
    libelle: str,
    by: User,
    description: str = "",
) -> PieceJustificative:
    libelle = libelle.strip()
    nom = nom_affichable(fichier.name or "")
    en_tete, sha256, taille = _lire_en_tete_et_empreinte(fichier)
    type_mime = controler_fichier(fichier.name or "", en_tete, taille)
    if not libelle:
        raise refuser(MSG_LIBELLE, libelle=MSG_LIBELLE)

    mission = ouvrir_fenetre(fiche.mission, ETAPE_FICHES, MSG_XII)
    droits.exiger_contributeur(by, mission)
    fiche = relire(fiche)
    if fiche.mission_id != mission.pk:
        message = "Cette fiche n'appartient pas à la mission."
        raise refuser(message, fiche=message)
    exiger_fiche_modifiable(fiche)

    # Nouvel envoi des mêmes octets (réessai) : on renvoie la pièce existante.
    existante: PieceJustificative | None = PieceJustificative.objects.filter(
        fiche=fiche, empreinte_sha256=sha256
    ).first()
    if existante is not None:
        return existante

    piece = PieceJustificative(
        mission=mission,
        fiche=fiche,
        numero=prochain_numero(PieceJustificative, mission.pk),
        libelle=libelle[:200],
        description=description.strip(),
        taille_octets=taille,
        type_mime=type_mime,
        nom_fichier_original=nom,
        deposee_par=by,
        empreinte_sha256=sha256,
        cle_stockage="en-attente",  # remplacée par la clé du stockage juste après l'écriture
    )
    # Écriture du fichier en dernier : plus aucun contrôle ne peut échouer avant la ligne.
    stocke = stockage_preuves().deposer(
        cast(BinaryIO, fichier), prefixe=f"preuves/{mission.pk}", taille_max=taille_maximale()
    )
    try:
        if stocke.sha256 != sha256 or stocke.taille != taille:
            raise RegleMetierError("Le fichier a changé pendant le dépôt : déposez-le à nouveau.")
        piece.cle_stockage = stocke.cle
        enregistrer(piece, by=by, creation=True)
    except BaseException:
        logger.error(  # noqa: TRY400
            "Fichier orphelin conservé (jamais effacé) : cle=%s sha256=%s fiche=%s",
            stocke.cle,
            stocke.sha256,
            fiche.pk,
        )
        raise
    return piece


@transaction.atomic
def modifier_piece(piece: PieceJustificative, *, by: User, **changes: Any) -> PieceJustificative:
    mission = ouvrir_fenetre(piece.mission, ETAPE_FICHES, MSG_XII)
    droits.exiger_contributeur(by, mission)
    piece = relire(piece)
    exiger_fiche_modifiable(FicheDeTest.objects.select_for_update().get(pk=piece.fiche_id))
    appliquer(piece, changes, {"libelle", "description"})
    piece.libelle = piece.libelle.strip()
    if not piece.libelle:
        raise refuser(MSG_LIBELLE, libelle=MSG_LIBELLE)
    enregistrer(piece, by=by)
    return piece


@transaction.atomic
def retirer_piece(piece: PieceJustificative, *, by: User) -> None:
    """Suppression logique : le fichier et son empreinte restent conservés."""
    mission = ouvrir_fenetre(piece.mission, ETAPE_FICHES, MSG_XII)
    droits.exiger_contributeur(by, mission)
    piece = relire(piece)
    exiger_fiche_modifiable(FicheDeTest.objects.select_for_update().get(pk=piece.fiche_id))
    piece.soft_delete(by)
