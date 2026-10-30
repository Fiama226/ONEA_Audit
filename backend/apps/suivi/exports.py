"""Exports CSV / XLSX du registre du suivi (R18) : aucune logique dans les vues.

Conventions de `programmation.exports` : CSV UTF-8 avec BOM, séparateur « ; », fins de ligne CRLF ;
toute valeur texte est neutralisée (`neutraliser_formule`) en CSV comme en XLSX, et les cellules
texte du classeur sont typées « texte » (un « = » initial n'est jamais une formule).
Plafond : 5 000 lignes, sinon 422.
"""

import csv
import io
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, cast

from django.db.models import QuerySet
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from apps.constats.models import PrioriteRecommandation
from apps.core.exceptions import RegleMetierError
from apps.referentiel.exports import CREATEUR, TYPE_CSV, TYPE_XLSX, nettoyer, neutraliser_formule

from .models import StatutRecommandationSuivi, StatutSuivi
from .services.commun import aujourd_hui as aujourd_hui_local
from .services.commun import en_retard, jours_retard

__all__ = [
    "LIMITE_LIGNES",
    "TYPE_CSV",
    "TYPE_XLSX",
    "exporter_actions",
    "exporter_recommandations",
    "nom_fichier",
]

LIMITE_LIGNES = 5000
MSG_LIMITE = "Affinez les filtres : l'export est limité à 5 000 lignes."
FORMATS = ("csv", "xlsx")
_FORMAT_DATE = "DD/MM/YYYY"

COLONNES_ACTIONS: list[str] = [
    "Mission",
    "Constat",
    "Recommandation",
    "Priorité",
    "Entité",
    "Action",
    "Indicateur",
    "Responsable",
    "Échéance initiale",
    "Échéance",
    "Reports",
    "Statut",
    "En retard",
    "Jours de retard",
    "Dernière activité",
]
COLONNES_RECOMMANDATIONS: list[str] = [
    "Mission",
    "Constat",
    "Entité",
    "Recommandation",
    "Priorité",
    "Statut de suivi",
    "Risque accepté",
    "Actions",
    "Actions closes",
    "Actions en retard",
    "Prochaine échéance",
]
_LARGEURS_ACTIONS = (16, 16, 50, 11, 14, 50, 30, 24, 14, 14, 9, 22, 10, 10, 18)
_LARGEURS_RECOMMANDATIONS = (16, 16, 14, 60, 11, 18, 10, 9, 12, 12, 14)

Valeur = str | int | date | datetime | None


def _txt(valeur: str | None) -> str:
    return neutraliser_formule(nettoyer(valeur or ""))


def _jour(valeur: date | datetime | None) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y")


def _borner(queryset: QuerySet[Any]) -> list[Any]:
    """Lit au plus `LIMITE_LIGNES` + 1 lignes : au-delà, l'export est refusé (422)."""
    lignes = list(queryset[: LIMITE_LIGNES + 1])
    if len(lignes) > LIMITE_LIGNES:
        raise RegleMetierError(MSG_LIMITE)
    return lignes


def _ecrire(
    fmt: str,
    titre: str,
    colonnes: Sequence[str],
    largeurs: Sequence[int],
    lignes: Sequence[Sequence[Valeur]],
    colonnes_dates: Sequence[int],
) -> bytes:
    if fmt == "csv":
        tampon = io.StringIO(newline="")
        ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
        ecrivain.writerow(colonnes)
        for ligne in lignes:
            ecrivain.writerow(
                [
                    _jour(v) if isinstance(v, date | datetime) else ("" if v is None else v)
                    for v in ligne
                ]
            )
        return tampon.getvalue().encode("utf-8-sig")
    classeur = Workbook()
    classeur.properties.creator = CREATEUR
    feuille = cast(Worksheet, classeur.active)
    feuille.title = titre
    for index, nom in enumerate(colonnes, 1):
        cellule = feuille.cell(row=1, column=index, value=nom)
        cellule.font = Font(bold=True)
        cellule.alignment = Alignment(vertical="top", wrap_text=True)
    for rang, ligne in enumerate(lignes, 2):
        for col, valeur in enumerate(ligne, 1):
            if isinstance(valeur, datetime):
                valeur = timezone.localtime(valeur).replace(tzinfo=None)
            cellule = feuille.cell(row=rang, column=col, value=valeur)
            if isinstance(valeur, str):
                cellule.data_type = "s"  # texte pur : jamais une formule
        for col in colonnes_dates:
            feuille.cell(row=rang, column=col).number_format = _FORMAT_DATE
    feuille.freeze_panes = "A2"
    feuille.auto_filter.ref = f"A1:{get_column_letter(len(colonnes))}{max(len(lignes) + 1, 1)}"
    for index, largeur in enumerate(largeurs, 1):
        feuille.column_dimensions[get_column_letter(index)].width = largeur
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def _controler_format(fmt: str) -> None:
    if fmt not in FORMATS:
        raise ValueError(fmt)


def exporter_actions(queryset: QuerySet[Any], fmt: str) -> bytes:
    """Actions du registre (`queryset` déjà filtré par droits et filtres de l'utilisateur)."""
    _controler_format(fmt)
    aujourd_hui = aujourd_hui_local()
    lignes: list[list[Valeur]] = []
    for s in _borner(queryset):
        reco = s.recommandation
        jours = jours_retard(s, aujourd_hui)
        lignes.append(
            [
                _txt(s.mission.reference),
                _txt(reco.constat.reference),
                _txt(reco.libelle),
                str(PrioriteRecommandation(reco.priorite).label),
                _txt(s.entite.code),
                _txt(s.action.libelle),
                _txt(s.action.indicateur),
                _txt(s.responsable.get_full_name() or s.responsable.username),
                s.echeance_initiale,
                s.echeance,
                s.nombre_reports,
                str(StatutSuivi(s.statut).label),
                "Oui" if en_retard(s, aujourd_hui) else "Non",
                jours if jours is not None else "",
                s.derniere_activite_le,
            ]
        )
    return _ecrire(
        fmt, "Actions", COLONNES_ACTIONS, _LARGEURS_ACTIONS, lignes, colonnes_dates=(9, 10, 15)
    )


def exporter_recommandations(queryset: QuerySet[Any], fmt: str) -> bytes:
    """Recommandations du registre (annotées par `registre.annoter_registre`)."""
    _controler_format(fmt)
    lignes: list[list[Valeur]] = []
    for r in _borner(queryset):
        lignes.append(
            [
                _txt(r.mission.reference),
                _txt(r.constat.reference),
                _txt(r.constat.entite.code),
                _txt(r.libelle),
                str(PrioriteRecommandation(r.priorite).label),
                str(StatutRecommandationSuivi(r.statut_suivi).label),
                "Oui" if r.nb_acceptations else "Non",
                r.actions_total,
                r.actions_closes,
                r.actions_en_retard,
                r.prochaine_echeance,
            ]
        )
    return _ecrire(
        fmt,
        "Recommandations",
        COLONNES_RECOMMANDATIONS,
        _LARGEURS_RECOMMANDATIONS,
        lignes,
        colonnes_dates=(11,),
    )


def nom_fichier(prefixe: str, fmt: str) -> str:
    """`suivi-actions-AAAAMMJJ.xlsx` (date du jour, fuseau de l'application)."""
    return f"{prefixe}-{aujourd_hui_local():%Y%m%d}.{fmt}"
