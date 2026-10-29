"""Provisional Word templates generated from a contract (until the official ONEA ones arrive)."""

import io

from docx import Document

from .contrats import Champ, TypeChamp
from .registre import TypeDocument

_SCALAIRES = (TypeChamp.TEXTE, TypeChamp.TEXTE_LONG)


def _ajouter_champ(doc, champ: Champ, chemin: str) -> None:  # type: ignore[no-untyped-def]
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
            valeurs[i].text = "{{ ligne." + scalaires[i].nom + " }}" if scalaires else "{{ ligne }}"
        table.add_row().cells[0].text = "{%tr endfor %}"


def construire_gabarit_provisoire(t: TypeDocument) -> bytes:
    """Build a valid .docx (passes `analyser_gabarit`) listing every tag of the contract."""
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
    return tampon.getvalue()
