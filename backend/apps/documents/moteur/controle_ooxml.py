"""Defensive checks and clean-up of OOXML parts (shared by the upload check and the renderer).

Pure functions on bytes: no Django import, so the rendering subprocess can use them to scan its
own output before handing it to Gotenberg (defence in depth).
"""

import io
import zipfile
from typing import Final

from lxml import etree

MSG_NON_DOCX: Final = "Le fichier n'est pas un document Word .docx valide."
MSG_MACROS: Final = "Les gabarits contenant des macros sont refusés."
MSG_EXTERNE: Final = (
    "Le fichier contient des liens vers des ressources externes (images liées, objets liés) "
    "ou un lien autre que http, https ou mailto : intégrez les images au document et "
    "limitez les liens à des adresses web ou de messagerie."
)
MSG_CHAMPS: Final = (
    "Le fichier contient des champs Word qui chargent des fichiers ou des données "
    "externes (INCLUDETEXT, INCLUDEPICTURE, LINK, DDE, DATABASE) : supprimez-les."
)

NS_REL_PAQUET: Final = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_R: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_VML: Final = "urn:schemas-microsoft-com:vml"
NS_OFFICE: Final = "urn:schemas-microsoft-com:office:office"

# Relationships Word adds to ordinary files and that LibreOffice never needs: removed, not refused.
TYPES_A_RETIRER: Final = ("/attachedtemplate", "/mailmergesource", "/mailmergeheadersource")
_ELEMENTS_A_RETIRER: Final = (f"{NS_W}attachedTemplate", f"{NS_W}mailMerge")
_MOTS_MACRO: Final = ("macroenabled", "vbaproject")
_CHAMPS_DANGEREUX: Final = (
    "INCLUDETEXT",
    "INCLUDEPICTURE",
    "INCLUDE",
    "LINK",
    "DDEAUTO",
    "DDE",
    "IMPORT",
    "DATABASE",
    "EMBED",
)
_SCHEMAS_LIENS: Final = ("http://", "https://", "mailto:")


def parseur() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )


def _instruction_dangereuse(instruction: str) -> bool:
    mots = instruction.split(None, 1)
    return bool(mots) and mots[0].upper() in _CHAMPS_DANGEREUX


def _champs_dangereux(racine: etree._Element) -> bool:
    """Join the `instrText` fragments of each complex field, then look at the field code."""
    pile: list[list[str]] = []
    separes: list[bool] = []
    orphelins: list[str] = []
    for element in racine.iter():
        if not isinstance(element.tag, str):
            continue
        if element.tag == f"{NS_W}fldChar":
            genre = element.get(f"{NS_W}fldCharType")
            if genre == "begin":
                pile.append([])
                separes.append(False)
            elif genre == "separate" and separes:
                separes[-1] = True
            elif genre == "end" and pile:
                separes.pop()
                if _instruction_dangereuse("".join(pile.pop())):
                    return True
        elif element.tag == f"{NS_W}instrText":
            if pile and not separes[-1]:
                pile[-1].append(element.text or "")
            elif not pile:
                orphelins.append(element.text or "")
        elif element.tag == f"{NS_W}fldSimple":
            if _instruction_dangereuse(element.get(f"{NS_W}instr") or ""):
                return True
    if any(_instruction_dangereuse("".join(morceaux)) for morceaux in pile):
        return True
    return _instruction_dangereuse("".join(orphelins))


def ids_hyperliens_externes(donnees_rels: bytes | None) -> set[str]:
    """Ids of the external hyperlink relationships of one .rels part."""
    if not donnees_rels:
        return set()
    try:
        racine = etree.fromstring(donnees_rels, parseur())
    except (etree.XMLSyntaxError, ValueError):
        return set()
    return {
        relation.get("Id", "")
        for relation in racine.iter(f"{NS_REL_PAQUET}Relationship")
        if relation.get("TargetMode") == "External"
        and (relation.get("Type") or "").lower().endswith("/hyperlink")
    }


def nom_des_relations(nom_partie: str) -> str:
    """`word/document.xml` -> `word/_rels/document.xml.rels`."""
    dossier, _, base = nom_partie.rpartition("/")
    return f"{dossier}/_rels/{base}.rels" if dossier else f"_rels/{base}.rels"


def _verifier_relations(racine: etree._Element) -> str | None:
    for relation in racine.iter(f"{NS_REL_PAQUET}Relationship"):
        genre = (relation.get("Type") or "").lower()
        if any(mot in genre for mot in _MOTS_MACRO):
            return MSG_MACROS
        if relation.get("TargetMode") != "External":
            continue
        if genre.endswith("/hyperlink"):
            cible = (relation.get("Target") or "").strip().lower()
            if not cible.startswith(_SCHEMAS_LIENS):
                return MSG_EXTERNE
        elif not genre.endswith(TYPES_A_RETIRER):
            return MSG_EXTERNE
    return None


def _verifier_references(racine: etree._Element, ids_hyperliens: set[str]) -> str | None:
    """No linked image/object: external ids may only be used by `w:hyperlink r:id`."""
    for element in racine.iter():
        if not isinstance(element.tag, str):
            continue
        espace_element = etree.QName(element).namespace
        for cle, valeur in element.attrib.items():
            nom = etree.QName(cle)
            if nom.namespace == NS_R and nom.localname in ("link", "href"):
                return MSG_EXTERNE
            if (
                nom.namespace in (NS_VML, NS_OFFICE)
                or (nom.namespace is None and espace_element == NS_VML)
            ) and nom.localname in ("href", "src", "relid"):
                if valeur and not valeur.startswith("data:"):
                    return MSG_EXTERNE
            if valeur in ids_hyperliens and not (
                element.tag == f"{NS_W}hyperlink"
                and nom.namespace == NS_R
                and nom.localname == "id"
            ):
                return MSG_EXTERNE
    return None


def _verifier_svg(racine: etree._Element) -> str | None:
    """SVG logos: the standard DOCTYPE is tolerated, entity declarations and external links not."""
    docinfo = racine.getroottree().docinfo
    dtd = docinfo.internalDTD
    if dtd is not None and dtd.entities():
        return MSG_NON_DOCX
    if any(True for _ in racine.iter(etree.Entity)):
        return MSG_NON_DOCX
    for element in racine.iter():
        if not isinstance(element.tag, str):
            continue
        for cle, valeur in element.attrib.items():
            if etree.QName(cle).localname == "href" and not valeur.startswith(("#", "data:")):
                return MSG_EXTERNE
    return None


def verifier_xml(
    nom: str, donnees: bytes, ids_hyperliens: set[str], *, svg: bool = False
) -> str | None:
    """Check one XML/rels part; return a French error message or None."""
    try:
        racine = etree.fromstring(donnees, parseur())
    except (etree.XMLSyntaxError, ValueError):
        return MSG_NON_DOCX
    if svg:
        return _verifier_svg(racine)
    docinfo = racine.getroottree().docinfo
    if docinfo.doctype or docinfo.internalDTD is not None or docinfo.externalDTD is not None:
        return MSG_NON_DOCX
    if any(True for _ in racine.iter(etree.Entity)):
        return MSG_NON_DOCX
    if nom.lower().endswith(".rels"):
        return _verifier_relations(racine)
    if nom.startswith("word/"):
        if _champs_dangereux(racine):
            return MSG_CHAMPS
        return _verifier_references(racine, ids_hyperliens)
    return None


def verifier_sortie(contenu: bytes) -> str | None:
    """Scan a (rendered) .docx for forbidden fields, links and relationships."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            noms = set(archive.namelist())

            def lire(nom: str) -> bytes | None:
                return archive.read(nom) if nom in noms else None

            for nom in sorted(noms):
                bas = nom.lower()
                if bas.endswith(".svg"):
                    probleme = verifier_xml(nom, archive.read(nom), set(), svg=True)
                elif bas.endswith((".xml", ".rels")):
                    ids = (
                        ids_hyperliens_externes(lire(nom_des_relations(nom)))
                        if nom.startswith("word/")
                        else set()
                    )
                    probleme = verifier_xml(nom, archive.read(nom), ids)
                else:
                    continue
                if probleme:
                    return probleme
    except (zipfile.BadZipFile, KeyError, OSError, EOFError):
        return MSG_NON_DOCX
    return None


def nettoyer_gabarit(contenu: bytes) -> bytes:
    """Remove `attachedTemplate`/mail-merge relationships and settings; same bytes if none."""
    modifie = False
    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(contenu)) as source:
        with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as cible:
            for info in source.infolist():
                donnees = source.read(info.filename)
                bas = info.filename.lower()
                if bas.endswith(".rels") or bas == "word/settings.xml":
                    try:
                        racine = etree.fromstring(donnees, parseur())
                    except (etree.XMLSyntaxError, ValueError):
                        racine = None
                    if racine is not None:
                        retires = _retirer(racine, bas.endswith(".rels"))
                        if retires:
                            modifie = True
                            donnees = etree.tostring(
                                racine, xml_declaration=True, encoding="UTF-8", standalone=True
                            )
                cible.writestr(info, donnees)
    return sortie.getvalue() if modifie else contenu


def _retirer(racine: etree._Element, est_rels: bool) -> int:
    if est_rels:
        cibles = [
            relation
            for relation in racine.iter(f"{NS_REL_PAQUET}Relationship")
            if relation.get("TargetMode") == "External"
            and (relation.get("Type") or "").lower().endswith(TYPES_A_RETIRER)
        ]
    else:
        cibles = [e for e in racine.iter() if e.tag in _ELEMENTS_A_RETIRER]
    for element in cibles:
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)
    return len(cibles)
