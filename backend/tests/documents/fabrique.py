"""Helpers to build small .docx files and a minimal tag contract for the document tests."""

import io
import zipfile

from docx import Document

from apps.documents.moteur.contrats import EXEMPLE_COMMUN, Champ, Contrat, TypeChamp


def docx_avec(
    *paragraphes: str,
    lignes_tableau: list[list[str]] | None = None,
    entete: str | None = None,
    pied: str | None = None,
    titre: str | None = None,
) -> bytes:
    """Build a .docx with paragraphs, an optional table (one list per row), header/footer/title."""
    doc = Document()
    if entete is not None:
        doc.sections[0].header.paragraphs[0].text = entete
    if pied is not None:
        doc.sections[0].footer.paragraphs[0].text = pied
    if titre is not None:
        doc.core_properties.title = titre
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
    for section in doc.sections:
        morceaux.extend(p.text for p in section.header.paragraphs)
        morceaux.extend(p.text for p in section.footer.paragraphs)
    for table in doc.tables:
        for ligne in table.rows:
            morceaux.extend(cellule.text for cellule in ligne.cells)
    return "\n".join(morceaux)


def avec_entrees(
    contenu: bytes,
    entrees: dict[str, bytes],
    types: dict[str, str] | None = None,
    *,
    types_par_defaut: str | None = "image/png",
) -> bytes:
    """Return a copy of a .docx with extra (or replaced) entries.

    Each added entry gets an Override content type: `types[nom]`, else `types_par_defaut`
    (no Override at all when that is None).
    """
    types = types or {}
    tampon = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(contenu)) as src:
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                if item.filename in entrees:
                    continue
                data = src.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    overrides = b""
                    for nom in entrees:
                        ct = types.get(nom, types_par_defaut)
                        if ct and nom != "[Content_Types].xml":
                            overrides += (
                                f'<Override PartName="/{nom}" ContentType="{ct}"/>'.encode()
                            )
                    data = data.replace(b"</Types>", overrides + b"</Types>")
                dst.writestr(item.filename, data)
            for nom, data in entrees.items():
                dst.writestr(nom, data)
    return tampon.getvalue()


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
