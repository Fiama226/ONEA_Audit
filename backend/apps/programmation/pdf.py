"""Export PDF du programme annuel d'audit interne (paysage A4).

Reproduit le modèle d'impression fourni par l'ONEA : cartouche (logo, titre, code et
version), tableau des missions prévues, bloc de visas « Elaboré / Vérifié / Approuvé par ».
Le tableau répète son en-tête à chaque page et ne coupe jamais une ligne ; la pagination
« Page x / y » et la date d'édition (Africa/Ouagadougou) figurent en pied de page.
"""

import io
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .models import LigneProgramme, ProgrammeAnnuel

__all__ = ["TYPE_PDF", "date_edition", "exporter_pdf", "periode"]

TYPE_PDF = "application/pdf"
# Logo ONEA : à remplacer par le logo officiel retenu pour l'application (voir branche logo).
LOGO = Path(__file__).resolve().parent / "assets" / "logo-onea.jpg"
FUSEAU = ZoneInfo("Africa/Ouagadougou")

# Références du formulaire (cartouche en haut à droite du modèle ONEA).
CODE_DOCUMENT = "01"
VERSION_DOCUMENT = 1

PAGE = landscape(A4)
MARGE_X = 24.1
MARGE_HAUT = 34.3
MARGE_BAS = 34.0
LARGEUR = PAGE[0] - 2 * MARGE_X
GRIS_ENTETE = colors.Color(0.9098, 0.9098, 0.9098)
# N° d'ordre, Code, Domaine d'intervention, Objet, Chef de mission, Auditeurs, Date.
_FIXES = (51.0, 56.7, 113.4, 240.9, 99.3, 113.3)
LARGEURS = (*_FIXES, LARGEUR - sum(_FIXES))

_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_LEFT)
_GRAS = ParagraphStyle("gras", parent=_BASE, fontName="Helvetica-Bold")
_ITAL = ParagraphStyle("ital", parent=_BASE, fontName="Helvetica-Oblique")
_ENTETE = ParagraphStyle("entete", parent=_GRAS, alignment=TA_CENTER)
_CENTRE = ParagraphStyle("centre", parent=_BASE, alignment=TA_CENTER)
_CENTRE_GRAS = ParagraphStyle("centre_gras", parent=_GRAS, alignment=TA_CENTER)
_TITRE = ParagraphStyle(
    "titre", fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_CENTER
)
_REF = ParagraphStyle(
    "ref", fontName="Helvetica-Bold", fontSize=10, leading=14, alignment=TA_CENTER
)


def _p(texte: str, style: ParagraphStyle) -> Paragraph:
    """Paragraphe dont le texte est toujours échappé (aucun balisage interprété)."""
    return Paragraph(escape(texte).replace("\n", "<br/>"), style)


def periode(debut: date, fin: date) -> str:
    """« 01/05 au 15/05/2026 » (même année), sinon dates complètes ; un jour : « 01/05/2026 »."""
    if debut == fin:
        return debut.strftime("%d/%m/%Y")
    if debut.year == fin.year:
        return f"{debut.strftime('%d/%m')} au {fin.strftime('%d/%m/%Y')}"
    return f"{debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"


def date_edition(maintenant: datetime | None = None) -> str:
    instant = maintenant or datetime.now(UTC)
    return instant.astimezone(FUSEAU).strftime("%d/%m/%Y")


def code_ligne(ligne: LigneProgramme) -> str:
    return f"{ligne.programme.annee}-{ligne.numero:06d}"


class _CanvasPagine(Canvas):  # type: ignore[misc]  # reportlab is untyped
    """Canvas à deux passes : numérote « Page x / y » et date l'édition en pied de page."""

    def __init__(self, *args: Any, edite_le: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._etats: list[dict[str, Any]] = []
        self._edite_le = edite_le

    def showPage(self) -> None:  # noqa: N802 - API ReportLab
        self._etats.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._etats)
        for etat in self._etats:
            self.__dict__.update(etat)
            self.setFont("Helvetica", 9)
            self.drawRightString(PAGE[0] - MARGE_X, 15, f"Page {self._pageNumber} / {total}")
            self.drawString(MARGE_X, 15, f"Édité le {self._edite_le}")
            super().showPage()
        super().save()


def _cartouche(annee: int) -> Table:
    logo: Flowable = Image(str(LOGO), width=80, height=80) if LOGO.exists() else Spacer(1, 1)
    refs: list[Flowable] = [
        _p(f"Code : {CODE_DOCUMENT}", _REF),
        Spacer(1, 14),
        _p(f"Version {VERSION_DOCUMENT}", _REF),
    ]
    table = Table(
        [[logo, _p(f"PROGRAMME ANNUEL D'AUDIT INTERNE {annee}", _TITRE), refs]],
        colWidths=[127.6, LARGEUR - 255.2, 127.6],
        rowHeights=[92.4],
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.2, colors.black),
                ("LINEAFTER", (0, 0), (1, 0), 1.2, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ]
        )
    )
    return table


def _tableau(lignes: list[LigneProgramme]) -> Table:
    entete = [
        _p("N°\nd'ordre", _ENTETE),
        _p("Code", _ENTETE),
        _p("Domaine\nd'intervention", _ENTETE),
        _p("Objet", _ENTETE),
        _p("Chef de mission", _ENTETE),
        _p("Auditeurs", _ENTETE),
        _p("Date prévisionnelle", _ENTETE),
    ]
    donnees: list[list[Paragraph]] = [entete]
    for lg in lignes:
        donnees.append(
            [
                _p(str(lg.numero), _CENTRE_GRAS),
                _p(code_ligne(lg), _CENTRE_GRAS),
                _p(lg.processus.libelle, _BASE),
                _p(lg.titre, _BASE),
                _p("", _CENTRE),  # aucune affectation liée à la ligne dans nos données
                _p("", _CENTRE),
                _p(periode(lg.debut_prevu, lg.fin_prevue), _CENTRE),
            ]
        )
    table = Table(donnees, colWidths=LARGEURS, repeatRows=1, splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), GRIS_ENTETE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
                # Colonne « Code » : même césure que le modèle (2026-000 / 001).
                ("LEFTPADDING", (1, 1), (1, -1), 7),
                ("RIGHTPADDING", (1, 1), (1, -1), 7),
            ]
        )
    )
    return table


def _visas() -> Table:
    def bloc(titre: str, fonction: str) -> list[Flowable]:
        return [
            _p(titre, _GRAS),
            _p(fonction, _ITAL),
            Spacer(1, 12),
            Paragraph("<b>Date :</b> _______________", _BASE),
            _p("Visa :", _GRAS),
            Spacer(1, 36),
            Paragraph("<b>Nom :</b> ___________________", _BASE),
        ]

    largeur = LARGEUR / 3
    table = Table(
        [
            [
                bloc("Elaboré par :", "Le chef du Département Audit Interne"),
                bloc("Vérifié par :", "Le Directeur Général"),
                bloc("Approuvé par :", "Le Président du Comité d'audit"),
            ]
        ],
        colWidths=[largeur] * 3,
        rowHeights=[128],
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("LINEAFTER", (0, 0), (1, 0), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def exporter_pdf(programme: ProgrammeAnnuel, *, maintenant: datetime | None = None) -> bytes:
    lignes = list(
        LigneProgramme.objects.filter(programme=programme)
        .select_related("processus", "programme")
        .order_by("numero")
    )
    tampon = io.BytesIO()
    edite_le = date_edition(maintenant)
    doc = BaseDocTemplate(
        tampon,
        pagesize=PAGE,
        leftMargin=MARGE_X,
        rightMargin=MARGE_X,
        topMargin=MARGE_HAUT,
        bottomMargin=MARGE_BAS,
        title=f"Programme annuel d'audit interne {programme.annee}",
        author="ONEA - Département Audit Interne",
        creator="Plateforme d'audit interne ONEA",
    )
    cadre = Frame(
        MARGE_X,
        MARGE_BAS,
        LARGEUR,
        PAGE[1] - MARGE_HAUT - MARGE_BAS,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="programme", frames=[cadre], pagesize=PAGE)])
    histoire: list[Flowable] = [
        _cartouche(programme.annee),
        Spacer(1, 8.5),
        _tableau(lignes),
        Spacer(1, 14.2),
        KeepTogether([_visas()]),
    ]

    def fabrique(*args: Any, **kwargs: Any) -> _CanvasPagine:
        return _CanvasPagine(*args, edite_le=edite_le, **kwargs)

    doc.build(histoire, canvasmaker=fabrique)
    return tampon.getvalue()
