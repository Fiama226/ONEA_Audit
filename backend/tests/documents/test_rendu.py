import io

import pytest
from docx import Document

from apps.documents.moteur.exceptions import RenduError
from apps.documents.moteur.rendu import rendre_docx

from .fabrique import CONTRAT_TEST, docx_avec, texte_docx


def test_texte_utilisateur_rendu_litteralement() -> None:
    gabarit = docx_avec("Objet : {{ mission.titre }}", "{{ notes }}")
    ctx = CONTRAT_TEST.exemple | {
        "mission": {
            **CONTRAT_TEST.exemple["mission"],
            "titre": "Achats & <w:p> {{ 7*7 }} {% if %} – Ouaga 💧",
        },
        "notes": "ligne 1\nligne 2",
    }
    texte = texte_docx(rendre_docx(gabarit, ctx, CONTRAT_TEST))
    assert "Achats & <w:p> {{ 7*7 }} {% if %} – Ouaga 💧" in texte
    assert "ligne 1" in texte and "ligne 2" in texte and "49" not in texte


def test_tableau_tr_for() -> None:
    gabarit = docx_avec(
        lignes_tableau=[["{%tr for l in equipe %}"], ["{{ l.nom }}"], ["{%tr endfor %}"]]
    )
    ctx = CONTRAT_TEST.exemple | {
        "equipe": [
            {"nom": "Un", "role": "r"},
            {"nom": "Deux", "role": "r"},
            {"nom": "Trois", "role": "r"},
        ]
    }
    sortie = rendre_docx(gabarit, ctx, CONTRAT_TEST)
    table = Document(io.BytesIO(sortie)).tables[0]
    assert [r.cells[0].text for r in table.rows] == ["Un", "Deux", "Trois"]


def test_rendu_refuse_contexte_non_conforme() -> None:
    with pytest.raises(RenduError):
        rendre_docx(docx_avec("x"), {"mission": {}}, CONTRAT_TEST)


def test_rendu_bac_a_sable() -> None:
    gabarit = docx_avec("{{ mission.titre.__class__.__mro__ }}")
    with pytest.raises(RenduError):
        rendre_docx(gabarit, CONTRAT_TEST.exemple, CONTRAT_TEST)
