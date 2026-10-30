"""Contrôle des fichiers déposés comme pièces justificatives (entrée non fiable).

Le type est déduit de l'extension (liste blanche) et confirmé par la signature d'octets ; le
`content-type` annoncé par le client n'est jamais utilisé. Le nom du client ne sert qu'à
l'affichage (`nom_affichable`) : la clé de stockage est générée par le stockage.
"""

import re
import unicodedata

from django.conf import settings

from apps.core.exceptions import RegleMetierError
from apps.core.fichiers import (
    DEFINITIONS,
    MSG_CONTENU,
    MSG_TYPE,
    MSG_VIDE,
    FichierRefuseError,
    contient_binaire,
    controler_entete,
    extension_de,
)

__all__ = [
    "EXTENSIONS_AUTORISEES",
    "MSG_CONTENU",
    "MSG_TAILLE",
    "MSG_TYPE",
    "MSG_VIDE",
    "contient_binaire",
    "controler_fichier",
    "nom_affichable",
    "taille_maximale",
    "type_contenu",
]

MSG_TAILLE = "Le fichier dépasse la taille maximale de 50 Mo."

# Liste d'extensions du lot 6 (conservée) ; les signatures d'octets vivent dans `core.fichiers`.
EXTENSIONS_AUTORISEES: frozenset[str] = frozenset(DEFINITIONS)

_NOM_PAR_DEFAUT = "fichier"
_NOM_MAX = 255
_SEPARATEURS = re.compile(r"[\\/]")


def type_contenu(nom: str) -> str:
    """Type MIME servi au téléchargement : fixé par l'extension (liste blanche), sinon binaire."""
    definition = DEFINITIONS.get(extension_de(nom))
    return definition[0] if definition is not None else "application/octet-stream"


def taille_maximale() -> int:
    return int(settings.PIECE_TAILLE_MAX_OCTETS)


def controler_fichier(nom: str, en_tete: bytes, taille: int, *, binaire: bool = False) -> str:
    """Valide le fichier sur son en-tête avant toute écriture ; renvoie le type MIME.

    Délègue à `core.fichiers` ; les refus restent des 422 pour les pièces (contrat du lot 6).
    `binaire` : le balayage du contenu entier a trouvé des octets non textuels (csv, txt, eml).
    """
    try:
        return controler_entete(
            nom,
            en_tete,
            taille,
            extensions=EXTENSIONS_AUTORISEES,
            taille_max=taille_maximale(),
            binaire=binaire,
        ).mime
    except FichierRefuseError as exc:
        raise en_422(exc) from exc


def en_422(exc: FichierRefuseError) -> RegleMetierError:
    """Un refus de contenu d'une pièce reste une erreur métier 422 (contrat du lot 6)."""
    return RegleMetierError(exc.message, exc.errors)


def nom_affichable(nom: str) -> str:
    """Base du nom seulement, sans caractère de contrôle, 255 caractères au plus."""
    base = unicodedata.normalize("NFC", _SEPARATEURS.split(nom)[-1])
    base = "".join(
        c for c in base if unicodedata.category(c) not in ("Cc", "Cf", "Cs", "Zl", "Zp")
    ).strip()
    if base in ("", ".", ".."):
        return _NOM_PAR_DEFAUT
    if len(base) > _NOM_MAX:
        racine, point, extension = base.rpartition(".")
        if point and 0 < len(extension) <= 10:
            return racine[: _NOM_MAX - len(extension) - 1] + "." + extension
        return base[:_NOM_MAX]
    return base
