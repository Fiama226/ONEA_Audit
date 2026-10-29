"""Verification of untrusted Word templates before they are stored or activated.

The template is never executed here: the archive is parsed defensively (hardened XML parser,
allowlist of part types, controlled external links, forbidden fields) and the tags are checked
statically against the contract by `balises.AnalyseBalises`. Real rendering happens later,
bounded, in `rendu.rendre_docx`, whose output is scanned again by `controle_ooxml`.
"""

import io
import zipfile
from typing import Any, Final

from docxtpl import DocxTemplate
from jinja2 import TemplateSyntaxError
from lxml import etree

from .bac_a_sable import environnement_jinja
from .balises import AnalyseBalises
from .contrats import Contrat
from .controle_ooxml import (
    MSG_MACROS,
    MSG_NON_DOCX,
    ids_hyperliens_externes,
    nom_des_relations,
    parseur,
    verifier_xml,
)
from .exceptions import GabaritInvalideError

MAX_ENTREES: Final = 2000
MAX_OCTETS_DECOMPRESSES: Final = 50 * 1024 * 1024
_BLOC: Final = 64 * 1024
_MAGIC_OLE: Final = b"\xd0\xcf\x11\xe0"

MSG_DOC: Final = (
    "Les fichiers .doc ne sont pas acceptés : enregistrez le gabarit au format .docx "
    "(Word ou LibreOffice), puis déposez-le à nouveau."
)
MSG_DECOMPRESSE: Final = "Le fichier est trop volumineux une fois décompressé."
MSG_ELEMENT: Final = "Le fichier contient un élément non pris en charge : {nom}."
MSG_IMBRIQUE: Final = "Erreur de syntaxe dans les balises : expression trop imbriquée."

_NS_CT: Final = "{http://schemas.openxmlformats.org/package/2006/content-types}"
_TYPES_XML: Final = ("application/xml", "text/xml")
_PREFIXES_AUTORISES: Final = (
    "image/",
    "application/vnd.openxmlformats-officedocument.",
    "application/vnd.openxmlformats-package.",
    "application/vnd.ms-word.",
    "application/vnd.ms-office.",  # drawingml, chart styles/colors, classification labels...
)
_TYPES_AUTORISES: Final = frozenset({"application/x-fontdata", *_TYPES_XML})
_MOTS_MACRO: Final = ("macroenabled", "vbaproject")
_MOTS_REFUSES: Final = ("activex", "oleobject", "officedocument.package", "embeddings")
# The properties docxtpl renders (docxtpl.render_properties).
_PROPRIETES: Final = ("author", "comments", "identifier", "language", "subject", "title")


def _lire_borne(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limite: int) -> bytes | None:
    """Read a whole entry, or None when it exceeds `limite` bytes once decompressed."""
    morceaux: list[bytes] = []
    total = 0
    with archive.open(info) as flux:
        while bloc := flux.read(_BLOC):
            total += len(bloc)
            if total > limite:
                return None
            morceaux.append(bloc)
    return b"".join(morceaux)


def _compter(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limite: int) -> int | None:
    total = 0
    with archive.open(info) as flux:
        while bloc := flux.read(_BLOC):
            total += len(bloc)
            if total > limite:
                return None
    return total


def _nom_suspect(nom: str) -> bool:
    return nom.startswith("/") or "\\" in nom or ".." in nom.split("/") or "\x00" in nom


def _types_de_contenu(donnees: bytes) -> tuple[dict[str, str], dict[str, str]] | None:
    """(defaults by extension, overrides by part name), or None when unparsable."""
    try:
        racine = etree.fromstring(donnees, parseur())
    except etree.XMLSyntaxError:
        return None
    defauts: dict[str, str] = {}
    surcharges: dict[str, str] = {}
    for element in racine:
        if element.tag == f"{_NS_CT}Default":
            defauts[element.get("Extension", "").lower()] = element.get("ContentType", "")
        elif element.tag == f"{_NS_CT}Override":
            surcharges[element.get("PartName", "")] = element.get("ContentType", "")
    return defauts, surcharges


def _est_xml(nom: str, type_contenu: str) -> bool:
    return (
        type_contenu.endswith("+xml")
        or type_contenu in _TYPES_XML
        or nom.lower().endswith((".xml", ".rels"))
    )


def _type_refuse(nom: str, type_contenu: str | None) -> str | None:
    if not type_contenu:
        return MSG_ELEMENT.format(nom=nom)
    bas = type_contenu.lower()
    if any(mot in bas for mot in _MOTS_MACRO):
        return MSG_MACROS
    if any(mot in bas for mot in _MOTS_REFUSES):
        return MSG_ELEMENT.format(nom=nom)
    if bas in _TYPES_AUTORISES or bas.startswith(_PREFIXES_AUTORISES):
        return None
    return MSG_ELEMENT.format(nom=nom)


def _verifier_archive(contenu: bytes) -> str | None:
    """Return an error message when the archive is not a safe .docx, else None."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTREES:
                return MSG_DECOMPRESSE
            noms = [i.filename for i in infos]
            if len(set(noms)) != len(noms) or any(_nom_suspect(n) for n in noms):
                return MSG_NON_DOCX
            if "[Content_Types].xml" not in noms or "word/document.xml" not in noms:
                return MSG_NON_DOCX
            if any("vbaproject" in n.lower() for n in noms):
                return MSG_MACROS
            restant = MAX_OCTETS_DECOMPRESSES
            brut = _lire_borne(archive, archive.getinfo("[Content_Types].xml"), restant)
            if brut is None:
                return MSG_DECOMPRESSE
            restant -= len(brut)
            types = _types_de_contenu(brut)
            if types is None:
                return MSG_NON_DOCX
            defauts, surcharges = types
            probleme = verifier_xml("[Content_Types].xml", brut, set())
            if probleme:
                return probleme
            noms_presents = set(noms)
            for info in infos:
                nom = info.filename
                if nom == "[Content_Types].xml" or info.is_dir():
                    continue
                extension = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
                type_contenu = surcharges.get(f"/{nom}", defauts.get(extension))
                if not nom.startswith("[trash]/"):
                    probleme = _type_refuse(nom, type_contenu)
                    if probleme:
                        return probleme
                if _est_xml(nom, type_contenu or ""):
                    donnees = _lire_borne(archive, info, restant)
                    if donnees is None:
                        return MSG_DECOMPRESSE
                    restant -= len(donnees)
                    ids: set[str] = set()
                    relations = nom_des_relations(nom)
                    if nom.startswith("word/") and relations in noms_presents:
                        brut_rels = _lire_borne(archive, archive.getinfo(relations), 5_000_000)
                        ids = ids_hyperliens_externes(brut_rels)
                    svg = (type_contenu or "").lower() == "image/svg+xml" or nom.lower().endswith(
                        ".svg"
                    )
                    probleme = verifier_xml(nom, donnees, ids, svg=svg)
                    if probleme:
                        return probleme
                else:
                    taille = _compter(archive, info, restant)
                    if taille is None:
                        return MSG_DECOMPRESSE
                    restant -= taille
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError):
        return MSG_NON_DOCX
    return None


def _sources_jinja(modele: DocxTemplate) -> list[str]:
    """Every XML/text source docxtpl renders: body, headers, footers, footnotes, properties."""
    modele.init_docx()
    sources = [modele.patch_xml(modele.get_xml())]
    for uri in (modele.HEADER_URI, modele.FOOTER_URI):
        for _cle, partie in modele.get_headers_footers(uri):
            sources.append(modele.patch_xml(modele.get_part_xml(partie)))
    for partie in modele.docx.part.package.iter_parts():
        if partie.content_type.endswith("wordprocessingml.footnotes+xml"):
            blob: Any = partie.blob
            texte = blob.decode("utf-8") if isinstance(blob, bytes) else str(blob)
            sources.append(modele.patch_xml(texte))
    proprietes = modele.docx.core_properties
    for nom in _PROPRIETES:
        valeur = getattr(proprietes, nom, "")
        if valeur:
            sources.append(valeur)
    return sources


def analyser_gabarit(
    contenu: bytes, contrat: Contrat, *, nom_fichier: str, taille_max_mo: int
) -> frozenset[str]:
    """Check a template against D4 and return its root tags; raise with every error found."""
    nom = nom_fichier.lower()
    if nom.endswith(".doc") or contenu[:4] == _MAGIC_OLE:
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

    env = environnement_jinja()
    analyse = AnalyseBalises(env, contrat)
    try:
        modele = DocxTemplate(io.BytesIO(contenu))
        sources = _sources_jinja(modele)
    except Exception as exc:
        raise GabaritInvalideError([MSG_NON_DOCX]) from exc
    for source in sources:
        try:
            analyse.analyser(source)
        except TemplateSyntaxError as exc:
            raise GabaritInvalideError(
                [f"Erreur de syntaxe dans les balises : {exc.message}."]
            ) from exc
        except RecursionError as exc:
            raise GabaritInvalideError([MSG_IMBRIQUE]) from exc
    if analyse.erreurs:
        raise GabaritInvalideError(sorted(analyse.erreurs))
    return frozenset(analyse.racines)
