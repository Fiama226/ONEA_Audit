"""Contrôle commun des fichiers téléversés (entrée non fiable) : type réel, taille, archives.

Règles (D7 du lot 9) :
- l'extension doit être autorisée par l'appelant ET concorder avec la signature d'octets du
  contenu (jamais l'extension seule, jamais le `content-type` annoncé par le client) ;
- les formats texte (txt, csv, eml) n'ont pas de signature : le contenu entier est balayé à la
  recherche d'octets nuls ou de contrôle ;
- OOXML / ODF (zip) : ouverture réelle de l'archive, refus des macros (`vbaProject.bin`), au plus
  2 000 entrées, 200 Mo décompressés, et 20 fois la taille compressée dès 16 Mo (décidé sur
  les tailles déclarées de l'annuaire central : aucun octet n'est décompressé, donc une bombe est
  refusée immédiatement) ;
- fichier vide ou trop gros : refus avant toute écriture.

Le nom du client ne sert qu'à en tirer l'extension : il n'entre jamais dans un chemin.
Ce module est le seul de l'application à connaître les signatures d'octets.
"""

import re
import zipfile
from dataclasses import dataclass
from typing import Any, Final

from .exceptions import RegleMetierError

MO: Final = 1024 * 1024

MSG_TYPE: Final = "Ce type de fichier n'est pas accepté."
MSG_CONTENU: Final = "Le contenu du fichier ne correspond pas à son extension."
MSG_VIDE: Final = "Le fichier est vide."
MSG_MACROS: Final = "Les fichiers contenant des macros ne sont pas acceptés."
MSG_ARCHIVE: Final = (
    "Le fichier est une archive invalide ou trop volumineuse une fois décompressée."
)

MAX_ENTREES: Final = 2000
MAX_DECOMPRESSE: Final = 200 * MO
RATIO_MAX: Final = 20
# Le ratio ne s'applique qu'au-delà de ce volume : un petit document Word légitime dont les
# feuilles de style sont très compressibles (ratio > 20) ne doit pas être refusé.
SEUIL_RATIO: Final = 16 * MO
_LONGUEUR_ENTETE: Final = 16
_BLOC: Final = 64 * 1024

_SIGNATURES: Final[tuple[tuple[str, tuple[bytes, ...]], ...]] = (
    ("pdf", (b"%PDF-",)),
    ("png", (b"\x89PNG\r\n\x1a\n",)),
    ("jpeg", (b"\xff\xd8\xff",)),
    ("tiff", (b"II*\x00", b"MM\x00*")),
    ("zip", (b"PK\x03\x04",)),
    ("ole", (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)),
)

# extension -> (type MIME servi, famille de signature attendue ; None = texte sans signature)
DEFINITIONS: Final[dict[str, tuple[str, str | None]]] = {
    "pdf": ("application/pdf", "pdf"),
    "png": ("image/png", "png"),
    "jpg": ("image/jpeg", "jpeg"),
    "jpeg": ("image/jpeg", "jpeg"),
    "tif": ("image/tiff", "tiff"),
    "tiff": ("image/tiff", "tiff"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "zip",
    ),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "zip"),
    "odt": ("application/vnd.oasis.opendocument.text", "zip"),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", "zip"),
    "doc": ("application/msword", "ole"),
    "xls": ("application/vnd.ms-excel", "ole"),
    "msg": ("application/vnd.ms-outlook", "ole"),
    "txt": ("text/plain", None),
    "csv": ("text/csv", None),
    "eml": ("message/rfc822", None),
}

# Formats à macros : refusés par leur extension avec un message précis.
EXTENSIONS_MACROS: Final = frozenset({"docm", "dotm", "xlsm", "xltm", "xlsb", "pptm", "ppsm"})

# Contenu minimal attendu d'une archive, par extension (le type réel du zip).
_PARTIE_REQUISE: Final = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml"}
_MIMETYPE_ODF: Final = {
    "odt": b"application/vnd.oasis.opendocument.text",
    "ods": b"application/vnd.oasis.opendocument.spreadsheet",
}

# Octets de contrôle (hors tabulation, retours à la ligne, saut de page) : absents d'un texte.
OCTETS_BINAIRES: Final = bytes(b for b in range(32) if b not in (9, 10, 12, 13)) + b"\x7f"
_SEPARATEURS: Final = re.compile(r"[\\/]")


class FichierRefuseError(RegleMetierError):
    """Fichier téléversé refusé : HTTP 400, message français précis sous `errors["fichier"]`."""

    status_http = 400

    def __init__(self, message: str) -> None:
        super().__init__(message, {"fichier": [message]})


@dataclass(frozen=True)
class TypeDetecte:
    """Résultat d'un contrôle réussi."""

    extension: str
    mime: str
    famille: str | None  # famille de signature (pdf, png, zip...) ; None pour un texte
    taille: int


def detecter_type(entete: bytes) -> str | None:
    """Famille de signature des premiers octets (pdf, png, jpeg, tiff, zip, ole), sinon None."""
    for famille, signatures in _SIGNATURES:
        if entete.startswith(signatures):
            return famille
    return None


def est_pdf(octets: bytes) -> bool:
    """Vrai si `octets` commence par la signature d'un PDF."""
    return detecter_type(octets[:_LONGUEUR_ENTETE]) == "pdf"


def extension_de(nom: str) -> str:
    """Extension en minuscules du dernier composant du nom ('' si aucune)."""
    base = _SEPARATEURS.split(nom)[-1]
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def contient_binaire(bloc: bytes) -> bool:
    """Vrai si `bloc` contient un octet nul ou de contrôle (contenu non textuel)."""
    return len(bloc.translate(None, OCTETS_BINAIRES)) != len(bloc)


def _libelle_taille(taille_max: int) -> str:
    return f"{-(-taille_max // MO)} Mo" if taille_max >= MO else f"{taille_max} octets"


def controler_entete(
    nom: str,
    entete: bytes,
    taille: int,
    *,
    extensions: frozenset[str],
    taille_max: int,
    binaire: bool = False,
) -> TypeDetecte:
    """Contrôle sur l'en-tête seul (taille, extension, signature) ; ne lit pas le fichier.

    `binaire` : le balayage du contenu entier, fait par l'appelant, a trouvé des octets non
    textuels (ne concerne que les formats texte).
    """
    if taille <= 0:
        raise FichierRefuseError(MSG_VIDE)
    if taille > taille_max:
        raise FichierRefuseError(
            f"Le fichier dépasse la taille maximale de {_libelle_taille(taille_max)}."
        )
    extension = extension_de(nom)
    if extension in EXTENSIONS_MACROS:
        raise FichierRefuseError(MSG_MACROS)
    if extension not in extensions or extension not in DEFINITIONS:
        raise FichierRefuseError(MSG_TYPE)
    mime, famille = DEFINITIONS[extension]
    if famille is None:
        conforme = not (binaire or contient_binaire(entete))
    else:
        conforme = detecter_type(entete) == famille
    if not conforme:
        raise FichierRefuseError(MSG_CONTENU)
    return TypeDetecte(extension=extension, mime=mime, famille=famille, taille=taille)


def _taille(fichier: Any) -> int:
    fichier.seek(0, 2)
    taille = int(fichier.tell())
    fichier.seek(0)
    return taille


def _nom_suspect(nom: str) -> bool:
    return nom.startswith("/") or "\\" in nom or ".." in nom.split("/") or "\x00" in nom


def _controler_archive(fichier: Any, extension: str, taille: int) -> None:
    """Archive zip réelle, sans macro, bornée, du type annoncé (aucune décompression)."""
    fichier.seek(0)
    try:
        archive = zipfile.ZipFile(fichier)
    except (zipfile.BadZipFile, OSError, EOFError, NotImplementedError, RuntimeError):
        raise FichierRefuseError(MSG_CONTENU) from None
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTREES:
            raise FichierRefuseError(MSG_ARCHIVE)
        decompresse = sum(i.file_size for i in infos)
        if decompresse > MAX_DECOMPRESSE or (
            decompresse > SEUIL_RATIO and decompresse > RATIO_MAX * taille
        ):
            raise FichierRefuseError(MSG_ARCHIVE)
        noms = [i.filename for i in infos]
        if any(_nom_suspect(n) for n in noms):
            raise FichierRefuseError(MSG_ARCHIVE)
        if any("vbaproject" in n.lower() for n in noms):
            raise FichierRefuseError(MSG_MACROS)
        requise = _PARTIE_REQUISE.get(extension)
        if requise is not None and (requise not in noms or "[Content_Types].xml" not in noms):
            raise FichierRefuseError(MSG_CONTENU)
        attendu = _MIMETYPE_ODF.get(extension)
        if attendu is not None:
            if not noms or noms[0] != "mimetype":
                raise FichierRefuseError(MSG_CONTENU)
            with archive.open(infos[0]) as flux:
                if flux.read(len(attendu) + 1) != attendu:
                    raise FichierRefuseError(MSG_CONTENU)
    fichier.seek(0)


def _balayer_texte(fichier: Any) -> bool:
    fichier.seek(0)
    while bloc := fichier.read(_BLOC):
        if contient_binaire(bloc):
            return True
    fichier.seek(0)
    return False


def controler_televersement(
    fichier: Any, *, extensions: frozenset[str], taille_max: int
) -> TypeDetecte:
    """Contrôle complet d'un fichier téléversé (objet à `read`/`seek`/`name`) avant écriture.

    Lève `FichierRefuseError` (400). Le fichier est replacé au début à la sortie.
    """
    taille = _taille(fichier)
    nom = str(getattr(fichier, "name", "") or "")
    fichier.seek(0)
    entete = fichier.read(_LONGUEUR_ENTETE)
    fichier.seek(0)
    detecte = controler_entete(nom, entete, taille, extensions=extensions, taille_max=taille_max)
    if detecte.famille is None:
        if _balayer_texte(fichier):
            raise FichierRefuseError(MSG_CONTENU)
    elif detecte.famille == "zip":
        _controler_archive(fichier, detecte.extension, taille)
    fichier.seek(0)
    return detecte
