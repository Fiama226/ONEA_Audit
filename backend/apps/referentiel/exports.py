"""Exports CSV / XLSX d'une cartographie des risques (aucune logique dans les vues)."""

import csv
import io
from typing import cast

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import (
    CartographieVersion,
    NiveauRisque,
    PrioriteRisque,
    ReponseRisque,
    Risque,
    StatutCartographie,
)
from .services import matrice

COLONNES: list[str] = [
    "Code",
    "Processus",
    "Objet auditable",
    "Risque",
    "Description",
    "Probabilité",
    "Impact",
    "Score",
    "Niveau",
    "Vulnérabilité",
    "Réponse",
    "Priorité",
    "Objectif de contrôle",
    "Dispositif de contrôle interne",
]

CREATEUR = "ONEA — Département Audit Interne"
TYPE_CSV = "text/csv; charset=utf-8"
TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Remplissages de la charte graphique (niveaux de risque).
_FOND_NIVEAU = {
    NiveauRisque.FAIBLE.value: "CFE8D8",
    NiveauRisque.MOYEN.value: "FFE8B3",
    NiveauRisque.ELEVE.value: "F8C9C4",
}
_DECLENCHEURS_FORMULE = ("=", "+", "-", "@", "\t", "\r")


def neutraliser_formule(valeur: str) -> str:
    """Préfixe d'une apostrophe tout texte qu'un tableur interpréterait comme une formule."""
    if valeur.startswith(_DECLENCHEURS_FORMULE):
        return "'" + valeur
    return valeur


def _risques(version: CartographieVersion) -> list[Risque]:
    return list(
        Risque.objects.filter(version=version)
        .select_related("processus", "objet_auditable")
        .order_by("numero")
    )


def _libelle_enum(enum: type[NiveauRisque] | type[ReponseRisque], valeur: str) -> str:
    return str(enum(valeur).label) if valeur else ""


def _ligne(r: Risque) -> list[str | int]:
    return [
        neutraliser_formule(r.code),
        neutraliser_formule(r.processus.libelle),
        neutraliser_formule(r.objet_auditable.libelle if r.objet_auditable else ""),
        neutraliser_formule(r.libelle),
        neutraliser_formule(r.description),
        r.probabilite,
        r.impact,
        r.score,
        _libelle_enum(NiveauRisque, r.niveau),
        neutraliser_formule(r.vulnerabilite),
        _libelle_enum(ReponseRisque, r.reponse),
        str(PrioriteRisque(r.priorite).label),
        neutraliser_formule(r.objectif_controle),
        neutraliser_formule(r.dispositif_controle),
    ]


def exporter_csv(version: CartographieVersion) -> bytes:
    """CSV UTF-8 avec BOM, séparateur « ; », fins de ligne CRLF (ouverture directe dans Excel)."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(COLONNES)
    for r in _risques(version):
        ecrivain.writerow(_ligne(r))
    return tampon.getvalue().encode("utf-8-sig")


def exporter_xlsx(version: CartographieVersion) -> bytes:
    """Classeur à deux feuilles : « Risques » (liste filtrable) et « Matrice » (5x5)."""
    classeur = Workbook()
    classeur.properties.creator = CREATEUR

    feuille = cast(Worksheet, classeur.active)
    feuille.title = "Risques"
    feuille.append(COLONNES)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
        cellule.alignment = Alignment(vertical="top", wrap_text=True)
    for r in _risques(version):
        feuille.append(_ligne(r))
    feuille.freeze_panes = "A2"
    feuille.auto_filter.ref = f"A1:{get_column_letter(len(COLONNES))}{feuille.max_row}"
    for index, largeur in enumerate((14, 30, 30, 40, 50, 12, 9, 8, 10, 40, 12, 14, 40, 40), 1):
        feuille.column_dimensions[get_column_letter(index)].width = largeur

    grille = classeur.create_sheet("Matrice")
    grille["B1"] = "Impact"
    grille.merge_cells("B1:F1")
    grille["B1"].font = Font(bold=True)
    grille["B1"].alignment = Alignment(horizontal="center")
    grille["A2"] = "Probabilité"
    grille["A2"].font = Font(bold=True)
    for impact in range(1, 6):
        c = grille.cell(row=2, column=1 + impact, value=impact)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    for case in matrice(version):
        ligne = 3 + (5 - case.probabilite)
        if case.impact == 1:
            axe = grille.cell(row=ligne, column=1, value=case.probabilite)
            axe.font = Font(bold=True)
            axe.alignment = Alignment(horizontal="center", vertical="center")
        c = grille.cell(row=ligne, column=1 + case.impact, value="\n".join(case.codes))
        c.fill = PatternFill("solid", fgColor=_FOND_NIVEAU[case.niveau])
        c.alignment = Alignment(wrap_text=True, vertical="top", horizontal="center")
    grille.column_dimensions["A"].width = 14
    for col in "BCDEF":
        grille.column_dimensions[col].width = 22
    for ligne in range(3, 8):
        grille.row_dimensions[ligne].height = 60

    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def nom_fichier(version: CartographieVersion, extension: str) -> str:
    suffixe = "-brouillon" if version.statut == StatutCartographie.BROUILLON else ""
    return f"cartographie-{version.annee}{suffixe}.{extension}"
