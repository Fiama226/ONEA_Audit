"""Provisional Word templates generated from a contract (until the official ONEA ones arrive)."""

import io
import zipfile
from typing import Any, Final

from docx import Document

from .contrats import Champ, TypeChamp
from .registre import TypeDocument

_SCALAIRES = (TypeChamp.TEXTE, TypeChamp.TEXTE_LONG)
_DATE_FIXE: Final = (2026, 1, 1, 0, 0, 0)


def _ajouter_champ(doc: Any, champ: Champ, chemin: str) -> None:
    if champ.type in _SCALAIRES:
        doc.add_paragraph(f"{champ.description} : {{{{ {chemin} }}}}")
    elif champ.type is TypeChamp.BLOC:
        doc.add_heading(champ.description, level=2)
        for enfant in champ.enfants:
            _ajouter_champ(doc, enfant, f"{chemin}.{enfant.nom}")
    else:
        doc.add_heading(champ.description, level=2)
        scalaires = [e for e in champ.enfants if e.type in _SCALAIRES]
        colonnes = max(len(scalaires), 1)
        table = doc.add_table(rows=0, cols=colonnes)
        table.style = "Table Grid"
        entete = table.add_row().cells
        for i in range(colonnes):
            entete[i].text = scalaires[i].description if scalaires else champ.description
        table.add_row().cells[0].text = f"{{%tr for ligne in {chemin} %}}"
        valeurs = table.add_row().cells
        for i in range(colonnes):
            if scalaires:
                valeurs[i].text = "{{ ligne." + scalaires[i].nom + " }}"
            else:
                # List of plain texts, or of blocks with no scalar field (not detailed here).
                valeurs[i].text = "—" if champ.enfants else "{{ ligne }}"
        table.add_row().cells[0].text = "{%tr endfor %}"


def _figer_dates(contenu: bytes) -> bytes:
    """Rewrite the zip with a fixed timestamp so that equal contracts give equal bytes."""
    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(contenu)) as source:
        with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as cible:
            for info in source.infolist():
                nouveau = zipfile.ZipInfo(info.filename, date_time=_DATE_FIXE)
                nouveau.compress_type = zipfile.ZIP_DEFLATED
                nouveau.external_attr = info.external_attr
                cible.writestr(nouveau, source.read(info.filename))
    return sortie.getvalue()


def construire_gabarit_provisoire(t: TypeDocument) -> bytes:
    """Build a valid, deterministic .docx (passes `analyser_gabarit`) listing every contract tag."""
    doc = Document()
    doc.add_paragraph("ONEA — Département Audit Interne")
    doc.add_paragraph("GABARIT PROVISOIRE — en attente du modèle officiel ONEA")
    doc.add_heading(t.libelle, level=1)
    doc.add_paragraph("Document n° {{ document.numero }} — version {{ document.version }}")
    doc.add_paragraph("Généré le {{ document.genere_le }} par {{ document.genere_par }}")
    for champ in t.contrat.champs:
        _ajouter_champ(doc, champ, champ.nom)
    tampon = io.BytesIO()
    doc.save(tampon)
    return _figer_dates(tampon.getvalue())
