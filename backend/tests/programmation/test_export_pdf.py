"""Export PDF du programme annuel : reproduit le modèle d'impression du client ONEA."""

import io
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.programmation import pdf
from apps.programmation.models import LigneProgramme
from apps.users.models import Role
from tests.factories import ProcessusFactory, make_user

from .factories import LigneProgrammeFactory, programme


def _ligne(**kw: Any) -> LigneProgramme:
    return cast(LigneProgramme, LigneProgrammeFactory(**kw))


def _lire(contenu: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(contenu))


def _texte(lecteur: PdfReader) -> str:
    return "\n".join(p.extract_text() for p in lecteur.pages)


def test_pdf_paysage_a4_titre_colonnes_et_logo(db: None) -> None:
    prog = programme(annee=2026)
    _ligne(
        programme=prog,
        numero=1,
        titre="Mission d'audit des achats",
        processus=ProcessusFactory(libelle="Gestion éclairée des achats"),
        debut_prevu=date(2026, 5, 1),
        fin_prevue=date(2026, 5, 15),
    )
    lecteur = _lire(pdf.exporter_pdf(prog))
    assert len(lecteur.pages) == 1
    page = lecteur.pages[0]
    assert round(float(page.mediabox.width)) == 842
    assert round(float(page.mediabox.height)) == 595
    texte = _texte(lecteur)
    assert "PROGRAMME ANNUEL D'AUDIT INTERNE 2026" in texte
    for colonne in ("Code", "Domaine", "d'intervention", "Objet", "Chef de mission", "Auditeurs"):
        assert colonne in texte
    assert "Date prévisionnelle" in texte
    assert "Code : 01" in texte
    assert "Version 1" in texte
    assert "2026-000001" in "".join(texte.split())
    assert "Gestion éclairée des achats" in texte.replace("\n", " ")
    assert "01/05 au 15/05/2026" in texte
    assert "Elaboré par :" in texte
    assert "Vérifié par :" in texte
    assert "Approuvé par :" in texte
    assert "Le Président du Comité d'audit" in texte
    assert "Page 1 / 1" in texte
    assert len(list(page.images)) == 1  # logo ONEA


def test_periode_sur_deux_annees_et_edition_date_ouagadougou(db: None) -> None:
    assert pdf.periode(date(2026, 5, 1), date(2026, 5, 15)) == "01/05 au 15/05/2026"
    assert pdf.periode(date(2026, 12, 1), date(2027, 1, 15)) == "01/12/2026 au 15/01/2027"
    assert pdf.periode(date(2026, 5, 1), date(2026, 5, 1)) == "01/05/2026"
    from datetime import UTC, datetime

    # 23h30 UTC le 31/12 = 23h30 à Ouagadougou (UTC+0) ; instant 00:10 UTC reste le même jour.
    assert pdf.date_edition(datetime(2026, 12, 31, 23, 30, tzinfo=UTC)) == "31/12/2026"


def test_pdf_multi_pages_entete_repete_et_pagination(db: None) -> None:
    prog = programme(annee=2026)
    for i in range(1, 61):
        _ligne(programme=prog, numero=i, titre=f"Mission numéro {i}")
    lecteur = _lire(pdf.exporter_pdf(prog))
    n = len(lecteur.pages)
    assert n >= 3
    for index, page in enumerate(lecteur.pages, 1):
        texte = page.extract_text()
        assert f"Page {index} / {n}" in texte
        assert "Date prévisionnelle" in texte  # en-tête répété
        assert round(float(page.mediabox.width)) == 842  # toujours paysage
    # Chaque ligne apparaît une seule fois (aucune coupure ni doublon).
    complet = _texte(lecteur)
    for i in (1, 30, 60):
        assert complet.count(f"Mission numéro {i}\n") + complet.count(f"Mission numéro {i} ") == 1
    # Le bloc de signatures n'est que sur la dernière page.
    assert "Approuvé par" in lecteur.pages[-1].extract_text()
    assert "Approuvé par" not in lecteur.pages[0].extract_text()


def test_pdf_echappe_le_balisage_et_garde_les_accents(db: None) -> None:
    prog = programme(annee=2026)
    _ligne(
        programme=prog,
        numero=1,
        titre='<b>Gras</b> <img src="file:///etc/passwd"/> & œuvre « Eau » – Étude',
        processus=ProcessusFactory(libelle="<font size=40>Énorme</font>"),
    )
    lecteur = _lire(pdf.exporter_pdf(prog))
    texte = _texte(lecteur).replace("\n", " ")
    assert "<b>Gras</b>" in texte
    assert '<img src="file:///etc/passwd"/>' in texte
    assert "& œuvre « Eau » – Étude" in texte
    assert "<font size=40>Énorme</font>" in texte
    assert len(list(lecteur.pages[0].images)) == 1  # aucune image injectée


def test_pdf_sans_ligne_et_mot_tres_long(db: None) -> None:
    prog = programme(annee=2026)
    assert len(_lire(pdf.exporter_pdf(prog)).pages) == 1
    _ligne(programme=prog, numero=1, titre="X" * 300)
    assert len(_lire(pdf.exporter_pdf(prog)).pages) == 1


def test_ordre_des_lignes_par_numero(db: None) -> None:
    prog = programme(annee=2026)
    _ligne(
        programme=prog,
        numero=2,
        titre="Seconde",
        debut_prevu=date(2026, 1, 5),
        fin_prevue=date(2026, 1, 6),
    )
    _ligne(
        programme=prog,
        numero=1,
        titre="Première",
        debut_prevu=date(2026, 6, 5),
        fin_prevue=date(2026, 6, 6),
    )
    texte = _texte(_lire(pdf.exporter_pdf(prog)))
    assert texte.index("Première") < texte.index("Seconde")


@pytest.fixture
def auth_rai(api_client: APIClient, db: None) -> APIClient:
    api_client.force_authenticate(make_user(Role.RAI))
    return api_client


def test_endpoint_export_pdf(auth_rai: APIClient) -> None:
    lg = _ligne(charge_prevue_jours=Decimal("3"))
    resp = auth_rai.get(f"/api/v1/audit-plans/{lg.programme_id}/export/?type=pdf")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp["Content-Disposition"].endswith('-brouillon.pdf"')
    assert resp.content.startswith(b"%PDF")


def test_endpoint_export_pdf_refuse_sans_droit(api_client: APIClient, db: None) -> None:
    lg = _ligne()
    assert api_client.get(
        f"/api/v1/audit-plans/{lg.programme_id}/export/?type=pdf"
    ).status_code in (
        401,
        403,
    )
