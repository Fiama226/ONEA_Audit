"""Second security round: footnote re-render, fields, linked images, real-Word-like files."""

import io
import zipfile

import pytest
from docx import Document

from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.controle_ooxml import verifier_sortie
from apps.documents.moteur.exceptions import GabaritInvalideError, RenduError
from apps.documents.moteur.rendu import _code_depuis_stderr, rendre_docx

from .fabrique import CONTRAT_TEST, avec_entrees, docx_avec

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
FOOTNOTES_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"


def _erreurs(contenu: bytes) -> str:
    with pytest.raises(GabaritInvalideError) as e:
        analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="g.docx", taille_max_mo=10)
    return "\n".join(e.value.errors["fichier"])


def _accepte(contenu: bytes) -> None:
    analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="g.docx", taille_max_mo=10)


def _lire(contenu: bytes, nom: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        return z.read(nom)


def _avec_notes(contenu: bytes, texte: str) -> bytes:
    rels = _lire(contenu, "word/_rels/document.xml.rels")
    rel = f'<Relationship Id="rId900" Type="{R}/footnotes" Target="footnotes.xml"/>'.encode()
    notes = (
        f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="1"><w:p><w:r><w:t>{texte}</w:t></w:r>'
        "</w:p></w:footnote></w:footnotes>"
    ).encode()
    return avec_entrees(
        contenu,
        {
            "word/_rels/document.xml.rels": rels.replace(
                b"</Relationships>", rel + b"</Relationships>"
            ),
            "word/footnotes.xml": notes,
        },
        {"word/footnotes.xml": FOOTNOTES_CT},
    )


def _avec_xml_dans_document(contenu: bytes, ancien: bytes, nouveau: bytes) -> bytes:
    document = _lire(contenu, "word/document.xml")
    assert ancien in document
    return avec_entrees(
        contenu, {"word/document.xml": document.replace(ancien, nouveau)}, types_par_defaut=None
    )


def _avec_lien_externe(contenu: bytes, cible: str, genre: str = "hyperlink") -> bytes:
    rels = _lire(contenu, "word/_rels/document.xml.rels")
    rel = f'<Relationship Id="rId77" Type="{R}/{genre}" Target="{cible}" TargetMode="External"/>'
    return avec_entrees(
        contenu,
        {
            "word/_rels/document.xml.rels": rels.replace(
                b"</Relationships>", rel.encode() + b"</Relationships>"
            )
        },
        types_par_defaut=None,
    )


# --- N1: user data is never evaluated as template code, whatever the number of sections ---


@pytest.mark.parametrize("sections", [1, 2, 3])
def test_donnees_utilisateur_jamais_evaluees(sections: int) -> None:
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "{{ mission.titre }}"
    doc.core_properties.title = "{{ mission.titre }}"
    doc.add_paragraph("{{ mission.titre }}")
    for _ in range(sections - 1):
        doc.add_section()
    tampon = io.BytesIO()
    doc.save(tampon)
    gabarit = _avec_notes(tampon.getvalue(), "{{ mission.titre }}")
    ctx = CONTRAT_TEST.exemple | {"mission": {"reference": "R", "titre": "{{ 6*7 }}"}}
    sortie = rendre_docx(gabarit, ctx, CONTRAT_TEST)
    for partie in ("word/footnotes.xml", "word/document.xml", "word/header1.xml"):
        xml = _lire(sortie, partie).decode()
        assert "{{ 6*7 }}" in xml and "42" not in xml.replace("xml", "")
    assert Document(io.BytesIO(sortie)).core_properties.title == "{{ 6*7 }}"


# --- N2: dangerous fields, safe filter, autoescape, rendered-output scan ----------------


def _champ_en_morceaux(*morceaux: str) -> bytes:
    p = f'<w:p xmlns:w="{W}"><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    p += "".join(f"<w:r><w:instrText>{m}</w:instrText></w:r>" for m in morceaux)
    p += '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    return p.encode()


def _docx_avec_paragraphe(brut: bytes) -> bytes:
    base = docx_avec("ZZMARQUE")
    return _avec_xml_dans_document(base, b"<w:p><w:r><w:t>ZZMARQUE</w:t></w:r></w:p>", brut)


@pytest.mark.parametrize(
    "morceaux",
    [
        (" INCL", 'UDEPICTURE "http://169.254.169.254/x"'),
        ("includetext x",),
        (" LI", "NK Excel.Sheet x"),
    ],
)
def test_champs_dangereux_refuses_meme_coupes(morceaux: tuple[str, ...]) -> None:
    assert "champs" in _erreurs(_docx_avec_paragraphe(_champ_en_morceaux(*morceaux)))


def test_champ_simple_dangereux_refuse_et_lien_hypertexte_long_accepte() -> None:
    simple = f'<w:p xmlns:w="{W}"><w:fldSimple w:instr="INCLUDETEXT x"/></w:p>'.encode()
    assert "champs" in _erreurs(_docx_avec_paragraphe(simple))
    _accepte(_docx_avec_paragraphe(_champ_en_morceaux(' HYPERLINK "https://x.example/link" ')))


def test_filtre_safe_et_autoescape_refuses() -> None:
    assert "interdit" in _erreurs(docx_avec("{{ mission.titre|safe }}"))
    assert "interdite" in _erreurs(
        docx_avec("{% autoescape false %}{{ mission.titre }}{% endautoescape %}")
    )


def test_sortie_scannee_avant_remise() -> None:
    piege = _docx_avec_paragraphe(_champ_en_morceaux("INCLUDETEXT x"))
    assert verifier_sortie(piege) is not None
    with pytest.raises(RenduError, match="refusé"):
        rendre_docx(piege, CONTRAT_TEST.exemple, CONTRAT_TEST)


# --- N3: external links only for w:hyperlink, http(s)/mailto ----------------------------


def test_image_liee_par_un_lien_externe_refusee() -> None:
    base = _avec_lien_externe(docx_avec("ZZMARQUE"), "http://169.254.169.254/x.png")
    blip = (
        f'<w:p xmlns:w="{W}"><w:r><a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '  # noqa: E501
        f'xmlns:r="{R}" r:link="rId77"/></w:r></w:p>'
    ).encode()
    contenu = _avec_xml_dans_document(base, b"<w:p><w:r><w:t>ZZMARQUE</w:t></w:r></w:p>", blip)
    assert "ressources externes" in _erreurs(contenu)


def test_vml_imagedata_externe_refuse() -> None:
    vml = (
        f'<w:p xmlns:w="{W}"><w:r><v:imagedata xmlns:v="urn:schemas-microsoft-com:vml" '
        'src="http://evil.example/x.png"/></w:r></w:p>'
    ).encode()
    assert "ressources externes" in _erreurs(_docx_avec_paragraphe(vml))


def test_lien_hypertexte_http_accepte_mais_pas_file() -> None:
    lien = (
        f'<w:p xmlns:w="{W}" xmlns:r="{R}"><w:hyperlink r:id="rId77"><w:r><w:t>site</w:t></w:r>'
        "</w:hyperlink></w:p>"
    ).encode()
    marque = b"<w:p><w:r><w:t>ZZMARQUE</w:t></w:r></w:p>"
    http = _avec_xml_dans_document(
        _avec_lien_externe(docx_avec("ZZMARQUE"), "https://onea.bf"), marque, lien
    )
    _accepte(http)
    fichier = _avec_xml_dans_document(
        _avec_lien_externe(docx_avec("ZZMARQUE"), "file:///etc/passwd"), marque, lien
    )
    assert "ressources externes" in _erreurs(fichier)


# --- N4: a Word 365 style file passes; attachedTemplate is stripped ---------------------

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc000000301010018dd8db00000000049454e44ae426082"
)
SVG = (
    b'<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
    b'"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg xmlns="http://www.w3.org/2000/svg" '
    b'width="1" height="1"><a href="#x"/></svg>'
)


def _word365() -> bytes:
    doc = Document()
    doc.add_paragraph("Objet : {{ mission.titre }}")
    doc.sections[0].header.paragraphs[0].add_run().add_picture(io.BytesIO(PNG))
    doc.sections[0].footer.paragraphs[0].text = "{{ document.numero }}"
    tampon = io.BytesIO()
    doc.save(tampon)
    base = tampon.getvalue()
    settings = _lire(base, "word/settings.xml")
    settings = settings.replace(
        b"</w:settings>", f'<w:attachedTemplate xmlns:r="{R}" r:id="rId1"/></w:settings>'.encode()
    )
    rels_settings = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships '
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{R}/attachedTemplate" '
        'Target="file:///C:/Users/x/ONEA.dotx" TargetMode="External"/></Relationships>'
    ).encode()
    racine = _lire(base, "_rels/.rels")
    label = (
        b'<Relationship Id="rId99" Type="http://schemas.microsoft.com/office/2020/02/'
        b'relationships/classificationlabels" Target="docMetadata/LabelInfo.xml"/>'
    )
    xml = b'<?xml version="1.0"?><r xmlns="urn:x"/>'
    return avec_entrees(
        base,
        {
            "word/settings.xml": settings,
            "word/_rels/settings.xml.rels": rels_settings,
            "_rels/.rels": racine.replace(b"</Relationships>", label + b"</Relationships>"),
            "docMetadata/LabelInfo.xml": xml,
            "word/charts/style1.xml": xml,
            "word/charts/colors1.xml": xml,
            "customXml/itemProps9.xml": xml,
            "word/media/logo.svg": SVG,
        },
        {
            "docMetadata/LabelInfo.xml": "application/vnd.ms-office.classificationlabels+xml",
            "word/charts/style1.xml": "application/vnd.ms-office.chartstyle+xml",
            "word/charts/colors1.xml": "application/vnd.ms-office.chartcolorstyle+xml",
            "customXml/itemProps9.xml": "application/vnd.openxmlformats-officedocument.customXmlProperties+xml",  # noqa: E501
            "word/media/logo.svg": "image/svg+xml",
        },
    )


def test_fichier_style_word_365_accepte_et_rendu_sans_modele_attache() -> None:
    contenu = _word365()
    _accepte(contenu)
    sortie = rendre_docx(contenu, CONTRAT_TEST.exemple, CONTRAT_TEST)
    assert b"attachedTemplate" not in _lire(sortie, "word/settings.xml")
    with zipfile.ZipFile(io.BytesIO(sortie)) as z:
        assert "word/_rels/settings.xml.rels" not in z.namelist() or b"ONEA.dotx" not in z.read(
            "word/_rels/settings.xml.rels"
        )


def test_svg_avec_entite_ou_xml_word_avec_doctype_refuses() -> None:
    svg_entite = SVG.replace(
        b'"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">', b'"x" [<!ENTITY a "b">]>'
    )
    base = docx_avec("x")
    assert "valide" in _erreurs(
        avec_entrees(base, {"word/media/l.svg": svg_entite}, {"word/media/l.svg": "image/svg+xml"})
    )
    doctype = b'<?xml version="1.0"?><!DOCTYPE r><r/>'
    assert "valide" in _erreurs(
        avec_entrees(base, {"word/x.xml": doctype}, {"word/x.xml": "application/xml"})
    )


# --- Minors -------------------------------------------------------------------------------


def test_expression_trop_imbriquee_donne_une_erreur_francaise() -> None:
    assert "trop imbriquée" in _erreurs(docx_avec("{{ " + "(" * 3000 + "1" + ")" * 3000 + " }}"))


def test_proprietes_identifier_et_language_analysees() -> None:
    doc = Document()
    doc.core_properties.identifier = "{{ mision.x }}"
    tampon = io.BytesIO()
    doc.save(tampon)
    assert "mision" in _erreurs(tampon.getvalue())


def test_attr_et_indices_dynamiques_refuses_indice_litteral_accepte() -> None:
    assert "interdit" in _erreurs(docx_avec("{{ mission|attr('titr') }}"))
    assert "interdit" in _erreurs(docx_avec("{{ mission[notes] }}"))
    _accepte(docx_avec("{{ mission['titre'] }}"))


def test_stderr_du_sous_processus_jamais_recopiee() -> None:
    bruit = b"DeprecationWarning: english text\n" + b"x" * 100_000
    assert _code_depuis_stderr(bruit)[0] == "generique"
    marque = b"warning\n\nONEA-ERREUR:interdit:detail\n"
    assert _code_depuis_stderr(marque) == ("interdit", "detail")
    assert _code_depuis_stderr(b"ONEA-ERREUR:inconnu:x")[0] == "generique"
