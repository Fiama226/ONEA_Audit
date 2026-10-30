"""Exports CSV / XLSX des taux de mise en oeuvre (aucune logique dans les vues)."""

import csv
import io
from typing import Any, cast

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from apps.referentiel.exports import CREATEUR, TYPE_CSV, TYPE_XLSX, nettoyer, neutraliser_formule

__all__ = ["COLONNES", "TYPE_CSV", "TYPE_XLSX", "exporter_csv", "exporter_xlsx", "nom_fichier"]

COLONNES: list[str] = [
    "Direction",
    "Libellé",
    "Actions",
    "Clôturées",
    "Abandonnées",
    "Taux de mise en oeuvre (%)",
    "Échues",
    "Clôturées échues",
    "Taux des échues (%)",
]
_LARGEURS = (14, 40, 10, 12, 13, 24, 10, 16, 20)
_TOTAL = "Total"


def _pourcent_fr(taux: float | None) -> str:
    return "" if taux is None else f"{taux * 100:.1f}".replace(".", ",")


def _lignes(donnees: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    lignes = [(d["code"], d["libelle"], d) for d in donnees["taux_par_direction"]]
    lignes.append((_TOTAL, "Toutes directions", donnees["taux"]))
    return lignes


def _texte(valeur: str, *, neutraliser: bool) -> str:
    valeur = nettoyer(valeur)
    return neutraliser_formule(valeur) if neutraliser else valeur


def exporter_csv(donnees: dict[str, Any]) -> bytes:
    """CSV UTF-8 avec BOM, séparateur « ; », fins de ligne CRLF."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(COLONNES)
    for code, libelle, t in _lignes(donnees):
        ecrivain.writerow(
            [
                _texte(code, neutraliser=True),
                _texte(libelle, neutraliser=True),
                t["total"],
                t["cloturees"],
                t["abandonnees"],
                _pourcent_fr(t["taux"]),
                t["echues"],
                t["cloturees_echues"],
                _pourcent_fr(t["taux_echues"]),
            ]
        )
    return tampon.getvalue().encode("utf-8-sig")


def exporter_xlsx(donnees: dict[str, Any]) -> bytes:
    classeur = Workbook()
    classeur.properties.creator = CREATEUR
    feuille = cast(Worksheet, classeur.active)
    feuille.title = "Taux"
    feuille["A1"] = f"Taux de mise en oeuvre des recommandations {donnees['annee']}"
    feuille["A1"].font = Font(bold=True, size=14)
    entete = 3
    for index, nom in enumerate(COLONNES, 1):
        c = feuille.cell(row=entete, column=index, value=nom)
        c.font = Font(bold=True)
        c.alignment = Alignment(vertical="top", wrap_text=True)
    lignes = _lignes(donnees)
    for i, (code, libelle, t) in enumerate(lignes):
        rang = entete + 1 + i
        valeurs: list[str | int | float | None] = [
            _texte(code, neutraliser=False),
            _texte(libelle, neutraliser=False),
            t["total"],
            t["cloturees"],
            t["abandonnees"],
            t["taux"],
            t["echues"],
            t["cloturees_echues"],
            t["taux_echues"],
        ]
        for col, valeur in enumerate(valeurs, 1):
            c = feuille.cell(row=rang, column=col, value=valeur)
            if isinstance(valeur, str):
                c.data_type = "s"  # texte pur : un « = » initial n'est jamais une formule
        for col in (6, 9):
            feuille.cell(row=rang, column=col).number_format = "0.0%"
        if code == _TOTAL:
            for col in range(1, len(COLONNES) + 1):
                feuille.cell(row=rang, column=col).font = Font(bold=True)
    feuille.freeze_panes = f"A{entete + 1}"
    for index, largeur in enumerate(_LARGEURS, 1):
        feuille.column_dimensions[get_column_letter(index)].width = largeur
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def nom_fichier(annee: int, extension: str) -> str:
    return f"taux-mise-en-oeuvre-{annee}.{extension}"
