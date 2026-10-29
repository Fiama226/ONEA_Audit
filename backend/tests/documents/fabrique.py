"""Helpers to build small .docx files and a minimal tag contract for the document tests."""

import io

from docx import Document

from apps.documents.moteur.contrats import EXEMPLE_COMMUN, Champ, Contrat, TypeChamp


def docx_avec(*paragraphes: str, lignes_tableau: list[list[str]] | None = None) -> bytes:
    """Build a .docx with the given paragraphs, then an optional table (one list per row)."""
    doc = Document()
    for texte in paragraphes:
        doc.add_paragraph(texte)
    if lignes_tableau:
        colonnes = max(len(ligne) for ligne in lignes_tableau)
        table = doc.add_table(rows=0, cols=colonnes)
        for ligne in lignes_tableau:
            cellules = table.add_row().cells
            for i, texte in enumerate(ligne):
                cellules[i].text = texte
    tampon = io.BytesIO()
    doc.save(tampon)
    return tampon.getvalue()


def texte_docx(contenu: bytes) -> str:
    """Return paragraphs then table cells of a .docx, separated by newlines."""
    doc = Document(io.BytesIO(contenu))
    morceaux = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for ligne in table.rows:
            morceaux.extend(cellule.text for cellule in ligne.cells)
    return "\n".join(morceaux)


CONTRAT_TEST = Contrat(
    code="TEST",
    libelle="Contrat de test",
    version=1,
    champs=(
        Champ(
            "mission",
            TypeChamp.BLOC,
            "Mission",
            (
                Champ("reference", TypeChamp.TEXTE, "Référence"),
                Champ("titre", TypeChamp.TEXTE, "Titre"),
            ),
        ),
        Champ(
            "equipe",
            TypeChamp.LISTE,
            "Équipe",
            (
                Champ("nom", TypeChamp.TEXTE, "Nom"),
                Champ("role", TypeChamp.TEXTE, "Rôle"),
            ),
        ),
        Champ("notes", TypeChamp.TEXTE_LONG, "Notes"),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": {"reference": "DAI/2026/M01", "titre": "Audit des achats"},
        "equipe": [
            {"nom": "A. Ouédraogo", "role": "Chef de mission"},
            {"nom": "B. Sawadogo", "role": "Auditeur"},
        ],
        "notes": "ligne 1\nligne 2",
    },
)
