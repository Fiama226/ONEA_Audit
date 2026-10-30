"""Contrôle des fichiers déposés comme pièces justificatives (entrée non fiable).

Le type est déduit de l'extension (liste blanche) et confirmé par la signature d'octets ; le
`content-type` annoncé par le client n'est jamais utilisé. Le nom du client ne sert qu'à
l'affichage (`nom_affichable`) : la clé de stockage est générée par le stockage.
"""

import re
import unicodedata

from django.conf import settings

from apps.core.exceptions import RegleMetierError

MSG_TYPE = "Ce type de fichier n'est pas accepté."
MSG_CONTENU = "Le contenu du fichier ne correspond pas à son extension."
MSG_VIDE = "Le fichier est vide."
MSG_TAILLE = "Le fichier dépasse la taille maximale de 50 Mo."

_PDF = (b"%PDF-",)
_PNG = (b"\x89PNG\r\n\x1a\n",)
_JPEG = (b"\xff\xd8\xff",)
_TIFF = (b"II*\x00", b"MM\x00*")
_ZIP = (b"PK\x03\x04",)
_OLE = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)
_TEXTE: tuple[bytes, ...] = ()  # pas de signature : contrôle d'absence d'octets nuls

# extension -> (type MIME, signatures acceptées)
EXTENSIONS_AUTORISEES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "pdf": ("application/pdf", _PDF),
    "png": ("image/png", _PNG),
    "jpg": ("image/jpeg", _JPEG),
    "jpeg": ("image/jpeg", _JPEG),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _ZIP,
    ),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _ZIP),
    "odt": ("application/vnd.oasis.opendocument.text", _ZIP),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", _ZIP),
    "doc": ("application/msword", _OLE),
    "xls": ("application/vnd.ms-excel", _OLE),
    "txt": ("text/plain", _TEXTE),
    "csv": ("text/csv", _TEXTE),
    "eml": ("message/rfc822", _TEXTE),
    "msg": ("application/vnd.ms-outlook", _OLE),
    "tif": ("image/tiff", _TIFF),
    "tiff": ("image/tiff", _TIFF),
}

# Octets de contrôle (hors tabulation, retours à la ligne, saut de page) : absents d'un texte.
OCTETS_BINAIRES = bytes(b for b in range(32) if b not in (9, 10, 12, 13)) + b"\x7f"

_NOM_PAR_DEFAUT = "fichier"
_NOM_MAX = 255
_SEPARATEURS = re.compile(r"[\\/]")


def _extension(nom: str) -> str:
    base = _SEPARATEURS.split(nom)[-1]
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def type_contenu(nom: str) -> str:
    """Type MIME servi au téléchargement : fixé par l'extension (liste blanche), sinon binaire."""
    definition = EXTENSIONS_AUTORISEES.get(_extension(nom))
    return definition[0] if definition is not None else "application/octet-stream"


def taille_maximale() -> int:
    return int(settings.PIECE_TAILLE_MAX_OCTETS)


def contient_binaire(bloc: bytes) -> bool:
    """Vrai si `bloc` contient un octet nul ou de contrôle (contenu non textuel)."""
    return len(bloc.translate(None, OCTETS_BINAIRES)) != len(bloc)


def controler_fichier(nom: str, en_tete: bytes, taille: int, *, binaire: bool = False) -> str:
    """Valide le fichier avant toute écriture ; renvoie le type MIME (celui de l'extension).

    `binaire` : le balayage du contenu entier (`contient_binaire`, fait par l'appelant pendant
    qu'il le lit) a trouvé des octets non textuels ; il ne concerne que csv, txt et eml.
    Un texte reste du texte : du HTML dans un .txt n'est sûr que servi en pièce jointe avec
    `nosniff` (en-têtes posés au téléchargement) ; le type vient toujours de l'extension.
    """
    if taille <= 0:
        raise RegleMetierError(MSG_VIDE, {"fichier": [MSG_VIDE]})
    if taille > taille_maximale():
        raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})
    definition = EXTENSIONS_AUTORISEES.get(_extension(nom))
    if definition is None:
        raise RegleMetierError(MSG_TYPE, {"fichier": [MSG_TYPE]})
    mime, signatures = definition
    conforme = (
        any(en_tete.startswith(s) for s in signatures)
        if signatures
        else not (binaire or contient_binaire(en_tete))
    )
    if not conforme:
        raise RegleMetierError(MSG_CONTENU, {"fichier": [MSG_CONTENU]})
    return mime


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
