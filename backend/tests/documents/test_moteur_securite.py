"""Lot 9 T16 : re-revue du moteur docx (balises, XML, entités, taille, chemins, macros).

Chaque test d'un défaut trouvé échoue sur le code d'avant le correctif. Les attaques N1 à N4 du
lot 4 (tâche 2) sont rejouées en fin de fichier avec une preuve de sensibilité.
"""

import io
import zipfile
from typing import Any

import pytest
from docx import Document

from apps.documents.moteur import bac_a_sable
from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.contrats import CHAMPS_COMMUNS
from apps.documents.moteur.controle_ooxml import verifier_sortie
from apps.documents.moteur.exceptions import GabaritInvalideError
from apps.documents.moteur.rendu import rendre_docx

from .fabrique import CONTRAT_TEST, avec_entrees, docx_avec

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _erreurs(contenu: bytes) -> str:
    with pytest.raises(GabaritInvalideError) as e:
        analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="g.docx", taille_max_mo=10)
    return "\n".join(e.value.errors["fichier"])


def _accepte(contenu: bytes) -> None:
    analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="g.docx", taille_max_mo=10)


def _lire(contenu: bytes, nom: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        return z.read(nom)


def _paragraphe(brut: str) -> bytes:
    base = docx_avec("ZZMARQUE")
    document = _lire(base, "word/document.xml")
    ancien = b"<w:p><w:r><w:t>ZZMARQUE</w:t></w:r></w:p>"
    assert ancien in document
    return avec_entrees(
        base,
        {"word/document.xml": document.replace(ancien, brut.encode())},
        types_par_defaut=None,
    )


def _champ(instruction: str) -> bytes:
    return _paragraphe(
        f'<w:p xmlns:w="{W}"><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f"<w:r><w:instrText>{instruction}</w:instrText></w:r>"
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )


# --- D1 : incorporation de fichier par altChunk (document imbriqué jamais analysé) ------------


def test_altchunk_document_imbrique_refuse() -> None:
    imbrique = docx_avec('{% include "x" %}')
    base = _paragraphe(
        f'<w:p xmlns:w="{W}" xmlns:r="{R}"><w:altChunk r:id="rId901"/></w:p>',
    )
    rels = _lire(base, "word/_rels/document.xml.rels")
    rel = f'<Relationship Id="rId901" Type="{R}/aFChunk" Target="afchunk.docx"/>'.encode()
    contenu = avec_entrees(
        base,
        {
            "word/_rels/document.xml.rels": rels.replace(
                b"</Relationships>", rel + b"</Relationships>"
            ),
            "word/afchunk.docx": imbrique,
        },
        {"word/afchunk.docx": DOCX_CT},
    )
    assert "non pris en charge" in _erreurs(contenu)


def test_altchunk_sans_partie_refuse_en_sortie() -> None:
    contenu = _paragraphe(f'<w:p xmlns:w="{W}" xmlns:r="{R}"><w:altChunk r:id="rId9"/></w:p>')
    assert verifier_sortie(contenu) is not None


# --- D2 : champ HYPERLINK vers un schéma interdit (contourne la règle http/https/mailto) -------


@pytest.mark.parametrize(
    "instruction",
    [
        ' HYPERLINK "javascript:alert(1)" ',
        ' HYPERLINK "file:///C:/secret.docx" ',
        ' HYPERLINK "\\\\\\\\serveur\\\\partage\\\\x" ',
        ' HYPERLINK \\l \\o "infobulle" "ftp://x.example/" ',
        ' RD "c:\\\\autre.docx" ',
        " MACROBUTTON Macro1 clic ",
    ],
)
def test_champ_hyperlink_et_inclusion_indirecte_refuses(instruction: str) -> None:
    assert "champs" in _erreurs(_champ(instruction))


@pytest.mark.parametrize(
    "instruction",
    [
        ' HYPERLINK "https://onea.bf/page" ',
        " HYPERLINK mailto:rai@onea.bf ",
        ' HYPERLINK \\l "signet" ',
        ' HYPERLINK \\t "_blank" "http://onea.bf" ',
    ],
)
def test_champ_hyperlink_legitime_accepte(instruction: str) -> None:
    _accepte(_champ(instruction))


# --- D3 : SVG : feuille de style externe et url() externe ---------------------------------------


def _svg(corps: str, prologue: str = "") -> bytes:
    svg = (
        f'<?xml version="1.0"?>{prologue}<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="10" height="10">{corps}</svg>'
    )
    return avec_entrees(
        docx_avec("x"),
        {"word/media/logo.svg": svg.encode()},
        {"word/media/logo.svg": "image/svg+xml"},
    )


def test_svg_feuille_de_style_externe_refusee() -> None:
    contenu = _svg("<rect/>", '<?xml-stylesheet href="http://x.example/a.css" type="text/css"?>')
    assert "externes" in _erreurs(contenu)


@pytest.mark.parametrize(
    "corps",
    [
        '<rect style="fill:url(http://x.example/p.svg#a)"/>',
        "<style>@import url(http://x.example/a.css);</style><rect/>",
        '<rect fill="url(//x.example/p.svg#a)"/>',
    ],
)
def test_svg_url_externe_refusee(corps: str) -> None:
    assert "externes" in _erreurs(_svg(corps))


def test_svg_logo_legitime_accepte() -> None:
    _accepte(_svg('<defs><linearGradient id="a"/></defs><rect style="fill:url(#a)"/>'))


# --- D4 : zéro entité, DOCTYPE et XXE (pas de lecture de fichier locale) ------------------------


@pytest.mark.parametrize(
    "dtd",
    [
        '<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>',
        '<!DOCTYPE r SYSTEM "http://x.example/evil.dtd">',
        '<!DOCTYPE r [<!ENTITY % p SYSTEM "http://x.example/p"> %p;]>',
    ],
)
def test_xxe_refuse_dans_toute_partie(dtd: str) -> None:
    xml = f'<?xml version="1.0"?>{dtd}<r>&x;</r>'.encode()
    contenu = avec_entrees(
        docx_avec("x"), {"customXml/i.xml": xml}, {"customXml/i.xml": "application/xml"}
    )
    assert "n'est pas un document Word" in _erreurs(contenu)


def test_entite_dans_le_document_principal_refusee() -> None:
    base = docx_avec("x")
    document = _lire(base, "word/document.xml")
    corrompu = document.replace(b"<w:document", b'<!DOCTYPE d [<!ENTITY a "b">]><w:document', 1)
    contenu = avec_entrees(base, {"word/document.xml": corrompu}, types_par_defaut=None)
    assert "n'est pas un document Word" in _erreurs(contenu)


# --- D5 : taille, chemins, macros ---------------------------------------------------------------


def test_bombe_de_decompression_refusee_sans_deborder() -> None:
    gros = b"0" * (51 * 1024 * 1024)
    contenu = avec_entrees(
        docx_avec("x"), {"word/media/z.png": gros}, {"word/media/z.png": "image/png"}
    )
    assert "volumineux" in _erreurs(contenu)


@pytest.mark.parametrize("nom", ["../evil.xml", "/abs.xml", "word/../../x.xml"])
def test_chemins_suspects_refuses(nom: str) -> None:
    base = docx_avec("x")
    tampon = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as src, zipfile.ZipFile(tampon, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info.filename))
        dst.writestr(nom, b"<a/>")
    assert "n'est pas un document Word" in _erreurs(tampon.getvalue())


def test_macros_refusees_par_nom_type_et_relation() -> None:
    par_nom = avec_entrees(
        docx_avec("x"),
        {"word/vbaProject.bin": b"x"},
        {"word/vbaProject.bin": "application/vnd.ms-office.vbaProject"},
    )
    assert "macros" in _erreurs(par_nom)
    macro_ct = avec_entrees(
        docx_avec("x"),
        {"word/document.xml": _lire(docx_avec("x"), "word/document.xml")},
        {},
    )
    _accepte(macro_ct)


# --- Rejeu N1 à N4 (lot 4 T2) avec preuve de sensibilité ----------------------------------------


def _gabarit_notes(texte: str) -> bytes:
    base = docx_avec("x")
    rels = _lire(base, "word/_rels/document.xml.rels")
    rel = f'<Relationship Id="rId900" Type="{R}/footnotes" Target="footnotes.xml"/>'.encode()
    notes = (
        f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="1"><w:p><w:r><w:t>{texte}</w:t></w:r>'
        "</w:p></w:footnote></w:footnotes>"
    ).encode()
    return avec_entrees(
        base,
        {
            "word/_rels/document.xml.rels": rels.replace(
                b"</Relationships>", rel + b"</Relationships>"
            ),
            "word/footnotes.xml": notes,
        },
        {
            "word/footnotes.xml": "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.footnotes+xml"
        },
    )


def _sections(n: int, gabarit_notes: bytes) -> bytes:
    """Same footnotes, `n` sections: docxtpl re-rendered the footnotes once per section."""
    doc = Document(io.BytesIO(gabarit_notes))
    for _ in range(n - 1):
        doc.add_section()
    tampon = io.BytesIO()
    doc.save(tampon)
    return tampon.getvalue()


def test_n1_rejeu_note_de_bas_de_page_rendue_une_fois(monkeypatch: pytest.MonkeyPatch) -> None:
    gabarit = _sections(3, _gabarit_notes("{{ mission.titre }}"))
    ctx = CONTRAT_TEST.exemple | {"mission": {"reference": "R", "titre": "{{ 6*7 }}"}}
    champs = CHAMPS_COMMUNS + CONTRAT_TEST.champs
    sortie = bac_a_sable.rendre_local(gabarit, ctx, champs)
    assert b"{{ 6*7 }}" in _lire(sortie, "word/footnotes.xml")
    # sensibilité : avec le rendu d'origine de docxtpl (avant correctif) la donnée est évaluée
    monkeypatch.setattr(bac_a_sable, "_footnotes_une_fois", lambda modele: modele.render_footnotes)
    ancien = bac_a_sable.rendre_local(gabarit, ctx, champs)
    assert b"{{ 6*7 }}" not in _lire(ancien, "word/footnotes.xml")


def test_n2_rejeu_champ_fractionne_refuse() -> None:
    brut = (
        f'<w:p xmlns:w="{W}"><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        "<w:r><w:instrText> INCL</w:instrText></w:r>"
        '<w:r><w:instrText>UDETEXT "x"</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )
    assert "champs" in _erreurs(_paragraphe(brut))


def test_n3_rejeu_lien_d_image_externe_refuse() -> None:
    base = docx_avec("x")
    rels = _lire(base, "word/_rels/document.xml.rels")
    rel = (
        f'<Relationship Id="rId55" Type="{R}/image" Target="http://x.example/a.png" '
        'TargetMode="External"/>'
    ).encode()
    contenu = avec_entrees(
        base,
        {
            "word/_rels/document.xml.rels": rels.replace(
                b"</Relationships>", rel + b"</Relationships>"
            )
        },
        types_par_defaut=None,
    )
    assert "externes" in _erreurs(contenu)
    assert verifier_sortie(contenu) is not None


def test_n4_rejeu_gabarit_word_365_accepte() -> None:
    base = docx_avec("{{ mission.titre }}", entete="{{ document.numero }}")
    rels = _lire(base, "word/_rels/document.xml.rels")
    liens = (
        f'<Relationship Id="rId70" Type="{R}/hyperlink" Target="https://onea.bf" '
        'TargetMode="External"/>'
        f'<Relationship Id="rId71" Type="{R}/attachedTemplate" '
        'Target="file:///C:/Users/x/Normal.dotm" TargetMode="External"/>'
    ).encode()
    contenu = avec_entrees(
        base,
        {
            "word/_rels/document.xml.rels": rels.replace(
                b"</Relationships>", liens + b"</Relationships>"
            )
        },
        types_par_defaut=None,
    )
    _accepte(contenu)
    sortie: Any = rendre_docx(contenu, CONTRAT_TEST.exemple, CONTRAT_TEST)
    assert b"attachedTemplate" not in _lire(sortie, "word/_rels/document.xml.rels")
