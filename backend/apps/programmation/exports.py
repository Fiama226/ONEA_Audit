"""Exports CSV / XLSX d'un programme annuel (aucune logique dans les vues)."""

import csv
import io
from datetime import date
from decimal import Decimal
from typing import cast

from django.db.models import Prefetch
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from apps.referentiel.exports import CREATEUR, TYPE_CSV, TYPE_XLSX, nettoyer, neutraliser_formule
from apps.referentiel.models import Direction

from .models import LigneProgramme, ProgrammeAnnuel, StatutProgramme, TypeIntervention
from .services import synthese

__all__ = ["COLONNES", "TYPE_CSV", "TYPE_XLSX", "exporter_csv", "exporter_xlsx", "nom_fichier"]

COLONNES: list[str] = [
    "N°",
    "Mission prévue",
    "Type",
    "Processus",
    "Objet auditable",
    "Entités",
    "Début prévu",
    "Fin prévue",
    "Trimestre",
    "Charge prévue (jours)",
    "Justification",
]
_LARGEURS = (6, 45, 14, 30, 30, 24, 14, 14, 11, 12, 50)
_FORMAT_DATE = "DD/MM/YYYY"
_LIGNE_ENTETE = 4  # lignes 1-2 : titre et statut, ligne 3 : vide


def _lignes(programme: ProgrammeAnnuel) -> list[LigneProgramme]:
    return list(
        LigneProgramme.objects.filter(programme=programme)
        .select_related("processus", "objet_auditable")
        .prefetch_related(Prefetch("entites", queryset=Direction.all_objects.order_by("code")))
        .order_by("numero")
    )


def _trimestre(ligne: LigneProgramme) -> str:
    return f"T{(ligne.debut_prevu.month - 1) // 3 + 1}"


def _entites(ligne: LigneProgramme) -> str:
    return ", ".join(d.code for d in ligne.entites.all())


def _decimal_fr(valeur: Decimal | None) -> str:
    return "" if valeur is None else str(valeur).replace(".", ",")


def _texte(valeur: str, *, neutraliser: bool) -> str:
    valeur = nettoyer(valeur)
    return neutraliser_formule(valeur) if neutraliser else valeur


def exporter_csv(programme: ProgrammeAnnuel) -> bytes:
    """CSV UTF-8 avec BOM, séparateur « ; », fins de ligne CRLF (ouverture directe dans Excel)."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(COLONNES)

    def t(valeur: str) -> str:
        return _texte(valeur, neutraliser=True)

    for lg in _lignes(programme):
        ecrivain.writerow(
            [
                lg.numero,
                t(lg.titre),
                str(TypeIntervention(lg.type).label),
                t(lg.processus.libelle),
                t(lg.objet_auditable.libelle if lg.objet_auditable else ""),
                t(_entites(lg)),
                lg.debut_prevu.strftime("%d/%m/%Y"),
                lg.fin_prevue.strftime("%d/%m/%Y"),
                _trimestre(lg),
                _decimal_fr(lg.charge_prevue_jours),
                t(lg.justification),
            ]
        )
    return tampon.getvalue().encode("utf-8-sig")


def exporter_xlsx(programme: ProgrammeAnnuel) -> bytes:
    """Classeur à deux feuilles : « Programme » (liste filtrable) et « Synthèse »."""
    classeur = Workbook()
    classeur.properties.creator = CREATEUR

    feuille = cast(Worksheet, classeur.active)
    feuille.title = "Programme"
    feuille["A1"] = f"Programme annuel d'audit interne {programme.annee}"
    feuille["A1"].font = Font(bold=True, size=14)
    feuille["A2"] = f"Statut : {StatutProgramme(programme.statut).label}"
    for index, nom in enumerate(COLONNES, 1):
        c = feuille.cell(row=_LIGNE_ENTETE, column=index, value=nom)
        c.font = Font(bold=True)
        c.alignment = Alignment(vertical="top", wrap_text=True)

    lignes = _lignes(programme)
    total = Decimal("0")
    for i, lg in enumerate(lignes):
        rang = _LIGNE_ENTETE + 1 + i
        if lg.charge_prevue_jours is not None:
            total += lg.charge_prevue_jours
        valeurs: list[str | int | float | date | None] = [
            lg.numero,
            _texte(lg.titre, neutraliser=False),
            str(TypeIntervention(lg.type).label),
            _texte(lg.processus.libelle, neutraliser=False),
            _texte(lg.objet_auditable.libelle if lg.objet_auditable else "", neutraliser=False),
            _texte(_entites(lg), neutraliser=False),
            lg.debut_prevu,
            lg.fin_prevue,
            _trimestre(lg),
            float(lg.charge_prevue_jours) if lg.charge_prevue_jours is not None else None,
            _texte(lg.justification, neutraliser=False),
        ]
        for col, valeur in enumerate(valeurs, 1):
            c = feuille.cell(row=rang, column=col, value=valeur)
            if isinstance(valeur, str):
                c.data_type = "s"  # texte pur : un « = » initial n'est jamais une formule
        for col in (7, 8):
            feuille.cell(row=rang, column=col).number_format = _FORMAT_DATE
    dernier = _LIGNE_ENTETE + len(lignes)
    feuille.freeze_panes = f"A{_LIGNE_ENTETE + 1}"
    feuille.auto_filter.ref = f"A{_LIGNE_ENTETE}:{get_column_letter(len(COLONNES))}{dernier}"
    ligne_total = dernier + 1
    feuille.cell(row=ligne_total, column=2, value="Total").font = Font(bold=True)
    c = feuille.cell(row=ligne_total, column=10, value=float(total))
    c.font = Font(bold=True)
    for index, largeur in enumerate(_LARGEURS, 1):
        feuille.column_dimensions[get_column_letter(index)].width = largeur

    resume = synthese(programme)
    page = classeur.create_sheet("Synthèse")
    page.append(["Missions prévues", resume.nb_lignes])
    page.append(["Charge totale (jours)", float(resume.charge_totale_jours)])
    page.append([])
    page.append(["Répartition par type", "Missions"])
    for t_ in TypeIntervention:
        page.append([str(t_.label), resume.par_type.get(t_.value, 0)])
    page.append([])
    page.append(["Répartition par trimestre", "Missions"])
    for q in range(1, 5):
        page.append([f"T{q}", resume.par_trimestre.get(q, 0)])
    for rang in (4, 4 + len(TypeIntervention) + 2):
        page.cell(row=rang, column=1).font = Font(bold=True)
        page.cell(row=rang, column=2).font = Font(bold=True)
    page.column_dimensions["A"].width = 30
    page.column_dimensions["B"].width = 12

    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def nom_fichier(programme: ProgrammeAnnuel, extension: str) -> str:
    suffixe = "-brouillon" if programme.statut == StatutProgramme.BROUILLON else ""
    return f"programme-audit-{programme.annee}{suffixe}.{extension}"
