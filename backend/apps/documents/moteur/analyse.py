"""Verification of untrusted Word templates before they are stored or activated."""

import io
import zipfile
from typing import Final

from docxtpl import DocxTemplate
from jinja2 import TemplateSyntaxError

from .contrats import Contrat, balises_racines
from .exceptions import GabaritInvalideError, RenduError
from .rendu import environnement_jinja, rendre_docx

MAX_ENTREES: Final = 2000
MAX_OCTETS_DECOMPRESSES: Final = 50 * 1024 * 1024
_BLOC: Final = 64 * 1024
_MAGIC_OLE: Final = b"\xd0\xcf\x11\xe0"

MSG_NON_DOCX: Final = "Le fichier n'est pas un document Word .docx valide."
MSG_DOC: Final = (
    "Les fichiers .doc ne sont pas acceptés : enregistrez le gabarit au format .docx "
    "(Word ou LibreOffice), puis déposez-le à nouveau."
)
MSG_MACROS: Final = "Les gabarits contenant des macros sont refusés."
MSG_DECOMPRESSE: Final = "Le fichier est trop volumineux une fois décompressé."

# Names Jinja treats as free variables although they are environment globals.
_GLOBALS_JINJA: Final = frozenset({"range", "dict", "lipsum", "cycler", "joiner", "namespace"})


def _verifier_archive(contenu: bytes) -> str | None:
    """Return an error message when the archive is not a safe .docx, else None."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTREES:
                return MSG_DECOMPRESSE
            noms = {i.filename for i in infos}
            if "[Content_Types].xml" not in noms or "word/document.xml" not in noms:
                return MSG_NON_DOCX
            if any(n.lower().endswith("vbaproject.bin") for n in noms):
                return MSG_MACROS
            total = 0
            for info in infos:
                est_xml = info.filename.lower().endswith((".xml", ".rels"))
                debut = b""
                with archive.open(info) as flux:
                    while bloc := flux.read(_BLOC):
                        if not debut:
                            debut = bloc
                        total += len(bloc)
                        if total > MAX_OCTETS_DECOMPRESSES:
                            return MSG_DECOMPRESSE
                        if est_xml and (b"<!ENTITY" in bloc or b"<!DOCTYPE" in bloc):
                            return MSG_NON_DOCX
                if info.filename == "[Content_Types].xml":
                    with archive.open(info) as flux:
                        if b"macroEnabled" in flux.read(MAX_OCTETS_DECOMPRESSES):
                            return MSG_MACROS
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError):
        return MSG_NON_DOCX
    return None


def analyser_gabarit(
    contenu: bytes, contrat: Contrat, *, nom_fichier: str, taille_max_mo: int
) -> frozenset[str]:
    """Check a template against D4 and return its root tags; raise with every error found."""
    nom = nom_fichier.lower()
    if nom.endswith(".doc") or (nom.endswith(".docx") is False and contenu[:4] == _MAGIC_OLE):
        raise GabaritInvalideError([MSG_DOC])
    if nom.endswith(".docm"):
        raise GabaritInvalideError([MSG_MACROS])
    if not nom.endswith(".docx"):
        raise GabaritInvalideError([MSG_NON_DOCX])
    if len(contenu) > taille_max_mo * 1024 * 1024:
        raise GabaritInvalideError([f"Le fichier dépasse {taille_max_mo} Mo."])
    probleme = _verifier_archive(contenu)
    if probleme:
        raise GabaritInvalideError([probleme])

    erreurs: list[str] = []
    env = environnement_jinja()
    try:
        modele = DocxTemplate(io.BytesIO(contenu))
        racines = frozenset(modele.get_undeclared_template_variables(env)) - _GLOBALS_JINJA
    except TemplateSyntaxError as exc:
        raise GabaritInvalideError(
            [f"Erreur de syntaxe dans les balises : {exc.message} (ligne {exc.lineno})."]
        ) from exc
    except Exception as exc:
        raise GabaritInvalideError([MSG_NON_DOCX]) from exc

    for balise in sorted(racines - balises_racines(contrat)):
        erreurs.append(f"Balise inconnue du contrat « {contrat.libelle} » : {balise}.")
    try:
        rendre_docx(contenu, contrat.exemple, contrat)
    except RenduError as exc:
        erreurs.append(
            f"Le rendu d'essai avec les données d'exemple a échoué : {str(exc).rstrip('.')}."
        )
    if erreurs:
        raise GabaritInvalideError(erreurs)
    return racines
