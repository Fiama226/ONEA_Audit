"""Attacks on untrusted templates: static analysis, hardened archive parsing, bounded rendering."""

import io
import time
import zipfile

import pytest
from docx import Document
from docx.oxml import parse_xml

from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.contrats import Champ, Contrat, TypeChamp
from apps.documents.moteur.exceptions import GabaritInvalideError, RenduError
from apps.documents.moteur.rendu import rendre_docx

from .fabrique import CONTRAT_TEST, avec_entrees, docx_avec, texte_docx

NON_DOCX = "n'est pas un document Word .docx valide"


def _erreurs(contenu: bytes) -> str:
    with pytest.raises(GabaritInvalideError) as e:
        analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="g.docx", taille_max_mo=10)
    return "\n".join(e.value.errors["fichier"])


def _accepte(contenu: bytes) -> None:
    analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="g.docx", taille_max_mo=10)


# --- Finding 3: nested tags checked statically against the contract tree ------------------


def test_filtre_default_ne_masque_pas_une_faute() -> None:
    assert "mission.titr" in _erreurs(docx_avec("{{ mission.titr|default('') }}"))


def test_faute_dans_une_branche_jamais_prise() -> None:
    gabarit = docx_avec("{% if mission.titre == 'zz' %}{{ mission.nope }}{% endif %}")
    assert "mission.nope" in _erreurs(gabarit)


def test_faute_derriere_is_defined() -> None:
    assert "mission.nope" in _erreurs(docx_avec("{% if mission.nope is defined %}x{% endif %}"))


def test_faute_dans_entete_pied_et_proprietes() -> None:
    assert "mission.titr" in _erreurs(docx_avec("x", entete="{{ mission.titr }}"))
    assert "mission.titr" in _erreurs(docx_avec("x", pied="{{ mission.titr }}"))
    assert "mision" in _erreurs(docx_avec("x", titre="{{ mision.titre }}"))


def test_entete_pied_proprietes_valides_acceptes() -> None:
    _accepte(
        docx_avec(
            "x",
            entete="{{ mission.titre }}",
            pied="{{ document.numero }}",
            titre="{{ mission.titre }}",
        )
    )


def test_instructions_et_filtres_dangereux_refuses() -> None:
    assert "interdit" in _erreurs(docx_avec("{% include 'x' %}"))
    assert "interdit" in _erreurs(docx_avec("{% macro f() %}x{% endmacro %}"))
    assert "interdit" in _erreurs(docx_avec("{{ 'x'|center(1000000000) }}"))
    assert "range" in _erreurs(docx_avec("{{ range(10) }}"))


def test_methode_de_texte_acceptee() -> None:
    _accepte(docx_avec("{{ mission.titre.upper() }} {{ mission.titre|upper }}"))


# --- Finding 2: hardened archive parsing ---------------------------------------------------


def test_doctype_utf16_refuse() -> None:
    xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE d [<!ENTITY a "b">]><r/>'
    contenu = avec_entrees(
        docx_avec("x"),
        {"customXml/u16.xml": xml.encode("utf-16")},
        {"customXml/u16.xml": "application/xml"},
    )
    assert NON_DOCX in _erreurs(contenu)


def test_doctype_apres_un_long_commentaire_refuse() -> None:
    xml = (
        b'<?xml version="1.0"?><!--'
        + b"x" * (64 * 1024 - 40)
        + b'--><!DOCTYPE d [<!ENTITY a "b">]><r/>'
    )
    contenu = avec_entrees(
        docx_avec("x"), {"customXml/long.xml": xml}, {"customXml/long.xml": "application/xml"}
    )
    assert NON_DOCX in _erreurs(contenu)


def test_doctype_dans_une_partie_sans_extension_xml_refuse() -> None:
    xml = b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "b">]><r/>'
    contenu = avec_entrees(
        docx_avec("x"), {"customXml/data.dat": xml}, {"customXml/data.dat": "application/xml"}
    )
    assert NON_DOCX in _erreurs(contenu)


def test_relation_externe_refusee_mais_lien_hypertexte_accepte() -> None:
    with zipfile.ZipFile(io.BytesIO(docx_avec("x"))) as z:
        rels = z.read("word/_rels/document.xml.rels")
    base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    externe = (
        f'<Relationship Id="rId99" Type="{base}image" '
        'Target="http://interne.example/x.png" TargetMode="External"/></Relationships>'
    ).encode()
    contenu = avec_entrees(
        docx_avec("x"),
        {"word/_rels/document.xml.rels": rels.replace(b"</Relationships>", externe)},
        types_par_defaut=None,
    )
    assert "ressources externes" in _erreurs(contenu)
    lien = (
        f'<Relationship Id="rId98" Type="{base}hyperlink" '
        'Target="https://onea.bf" TargetMode="External"/></Relationships>'
    ).encode()
    _accepte(
        avec_entrees(
            docx_avec("x"),
            {"word/_rels/document.xml.rels": rels.replace(b"</Relationships>", lien)},
            types_par_defaut=None,
        )
    )


def test_champ_includepicture_refuse() -> None:
    doc = Document()
    run = doc.add_paragraph().add_run()
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    run._r.append(
        parse_xml(f'<w:instrText {ns}>INCLUDEPICTURE "http://x.example/a.png"</w:instrText>')
    )
    tampon = io.BytesIO()
    doc.save(tampon)
    assert "champs" in _erreurs(tampon.getvalue())


def test_partie_de_type_inconnu_refusee() -> None:
    contenu = avec_entrees(
        docx_avec("x"), {"word/x.bin": b"abc"}, {"word/x.bin": "application/x-msdownload"}
    )
    assert "non pris en charge" in _erreurs(contenu)
    sans_type = avec_entrees(docx_avec("x"), {"word/y.zzz": b"abc"}, types_par_defaut=None)
    assert "non pris en charge" in _erreurs(sans_type)


# --- Finding 1: bounded rendering ----------------------------------------------------------


def _rendre(*paragraphes: str, delai_s: float = 20, **ctx: object) -> bytes:
    return rendre_docx(
        docx_avec(*paragraphes), CONTRAT_TEST.exemple | ctx, CONTRAT_TEST, delai_s=delai_s
    )


def test_multiplication_geante_refusee_vite() -> None:
    debut = time.monotonic()
    with pytest.raises(RenduError) as e:
        _rendre("{{ ('x' * 10**9)|length }}")
    assert time.monotonic() - debut < 20
    assert "trop volumineux" in str(e.value)


def test_puissance_geante_refusee() -> None:
    with pytest.raises(RenduError, match="trop volumineux"):
        _rendre("{{ 9 ** 9 ** 9 }}")


def test_boucles_imbriquees_interrompues_par_le_delai() -> None:
    equipe = [{"nom": str(i), "role": "r"} for i in range(400)]
    boucles = "{% for a in equipe %}{% for b in equipe %}{% for c in equipe %}"
    boucles += "{% for d in equipe %}{% endfor %}{% endfor %}{% endfor %}{% endfor %}"
    debut = time.monotonic()
    with pytest.raises(RenduError, match="délai"):
        _rendre(boucles, delai_s=3, equipe=equipe)
    assert time.monotonic() - debut < 20


def test_le_gabarit_ne_modifie_pas_le_contexte() -> None:
    equipe = [{"nom": "a", "role": "r"}]
    with pytest.raises(RenduError):
        _rendre("{{ equipe.append(1) }}", equipe=equipe)
    assert equipe == [{"nom": "a", "role": "r"}]


def test_messages_de_rendu_en_francais_sans_texte_technique() -> None:
    for gabarit in ("{{ mission.titre.__class__ }}", "{{ mission.nope }}", "{{ 1 / 0 }}"):
        with pytest.raises(RenduError) as e:
            _rendre(gabarit)
        message = str(e.value)
        assert message.startswith("Le rendu du document a échoué")
        assert "unsafe" not in message and "undefined" not in message.lower()
        assert "Le rendu du document a échoué : Le rendu" not in message


def test_entete_et_pied_rendus_dans_le_bac_a_sable() -> None:
    gabarit = docx_avec("x", entete="E {{ mission.titre }}", pied="P {{ document.numero }}")
    texte = texte_docx(rendre_docx(gabarit, CONTRAT_TEST.exemple, CONTRAT_TEST))
    assert "E Audit des achats" in texte and "P DAI/2026/M01/XX-01" in texte
    piege = docx_avec("x", entete="{{ mission.titre.__class__ }}")
    with pytest.raises(RenduError):
        rendre_docx(piege, CONTRAT_TEST.exemple, CONTRAT_TEST)


def test_caracteres_de_controle_retires_partout() -> None:
    ctx = CONTRAT_TEST.exemple | {"mission": {"reference": "R", "titre": "A\x0bB\x00C"}}
    gabarit = docx_avec(
        "{{ mission.titre }}", entete="{{ mission.titre }}", pied="{{ mission.titre }}"
    )
    texte = texte_docx(rendre_docx(gabarit, ctx, CONTRAT_TEST))
    assert texte.count("ABC") == 3


def test_esperluette_dans_les_proprietes_pas_double_echappee() -> None:
    ctx = CONTRAT_TEST.exemple | {"mission": {"reference": "R", "titre": "A & B"}}
    gabarit = docx_avec("x", titre="{{ mission.titre }}")
    sortie = rendre_docx(gabarit, ctx, CONTRAT_TEST)
    assert Document(io.BytesIO(sortie)).core_properties.title == "A & B"


# --- Minors --------------------------------------------------------------------------------


def test_contrat_exemple_non_conforme_refuse() -> None:
    with pytest.raises(ValueError, match="TEST2"):
        Contrat("TEST2", "x", 1, (Champ("a", TypeChamp.TEXTE, "A"),), {"a": "x"})


def test_contrat_et_exemple_isoles_et_hashables() -> None:
    assert hash(CONTRAT_TEST) == hash(CONTRAT_TEST)
    autre = Contrat("T3", "x", 1, CONTRAT_TEST.champs, CONTRAT_TEST.exemple | {})
    assert autre.exemple["onea"] is not CONTRAT_TEST.exemple["onea"]


def test_gabarit_provisoire_deterministe(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.documents.moteur.provisoires import construire_gabarit_provisoire

    from .test_provisoires import _type

    reel = time.time
    premier = construire_gabarit_provisoire(_type())
    monkeypatch.setattr(time, "time", lambda: reel() + 5 * 86400)
    assert construire_gabarit_provisoire(_type()) == premier
