import io
import os
import zipfile

import pytest

from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.exceptions import GabaritInvalideError

from .fabrique import CONTRAT_TEST, docx_avec

NON_DOCX = "n'est pas un document Word .docx valide"
TROP_GROS_DECOMPRESSE = "trop volumineux une fois décompressé"


def _analyser(contenu: bytes, nom: str = "g.docx", mo: int = 10) -> frozenset[str]:
    return analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier=nom, taille_max_mo=mo)


def _erreurs(contenu: bytes, nom: str = "g.docx", mo: int = 10) -> str:
    with pytest.raises(GabaritInvalideError) as e:
        _analyser(contenu, nom, mo)
    return "\n".join(e.value.errors["fichier"])


def _avec_entrees(contenu: bytes, entrees: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(contenu)) as src:
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                dst.writestr(item, src.read(item.filename))
            for nom, data in entrees.items():
                dst.writestr(nom, data)
    return tampon.getvalue()


def test_analyse_refuse_balise_inconnue_et_faute_de_frappe() -> None:
    with pytest.raises(GabaritInvalideError) as e:
        analyser_gabarit(
            docx_avec("{{ mision.titre }} {{ mission.titr }}"),
            CONTRAT_TEST,
            nom_fichier="g.docx",
            taille_max_mo=10,
        )
    assert any("mision" in m for m in e.value.errors["fichier"])
    assert any("rendu d'essai" in m for m in e.value.errors["fichier"])


def test_analyse_renvoie_balises_racines() -> None:
    gabarit = docx_avec("{{ mission.titre }} {{ onea.nom }}", "{{ notes }}")
    assert _analyser(gabarit) == {"mission", "onea", "notes"}


def test_analyse_accepte_boucle_tr() -> None:
    gabarit = docx_avec(
        lignes_tableau=[["{%tr for l in equipe %}"], ["{{ l.nom }}"], ["{%tr endfor %}"]]
    )
    assert _analyser(gabarit) == {"equipe"}


def test_analyse_refuse_doc() -> None:
    assert "Les fichiers .doc ne sont pas acceptés" in _erreurs(b"\xd0\xcf\x11\xe0abc", "g.doc")
    assert "Les fichiers .doc ne sont pas acceptés" in _erreurs(docx_avec("x"), "g.DOC")


def test_analyse_refuse_docm_et_macros() -> None:
    assert "macros" in _erreurs(docx_avec("x"), "g.docm")
    avec_macro = _avec_entrees(docx_avec("x"), {"word/vbaProject.bin": b"vba"})
    assert "macros" in _erreurs(avec_macro)


def test_analyse_refuse_non_docx() -> None:
    assert NON_DOCX in _erreurs(b"pas un zip")
    assert NON_DOCX in _erreurs(b"PK\x03\x04junk")
    zip_autre = io.BytesIO()
    with zipfile.ZipFile(zip_autre, "w") as z:
        z.writestr("a.txt", "x")
    assert NON_DOCX in _erreurs(zip_autre.getvalue())
    assert NON_DOCX in _erreurs(docx_avec("x"), "g.txt")


def test_analyse_refuse_fichier_trop_gros() -> None:
    gros = _avec_entrees(docx_avec("x"), {"word/media/x.bin": os.urandom(1_200_000)})
    assert "Le fichier dépasse 1 Mo." in _erreurs(gros, mo=1)


def test_analyse_refuse_bombe_zip() -> None:
    bombe = _avec_entrees(docx_avec("x"), {"word/media/bombe.bin": bytes(60 * 1024 * 1024)})
    assert len(bombe) < 1024 * 1024
    assert TROP_GROS_DECOMPRESSE in _erreurs(bombe)


def test_analyse_refuse_trop_d_entrees() -> None:
    contenu = _avec_entrees(docx_avec("x"), {f"word/media/{i}.txt": b"" for i in range(2001)})
    assert TROP_GROS_DECOMPRESSE in _erreurs(contenu)


def test_analyse_refuse_entites_xml_externes() -> None:
    xxe = b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>'
    contenu = _avec_entrees(docx_avec("x"), {"customXml/xxe.xml": xxe})
    assert NON_DOCX in _erreurs(contenu)


def test_analyse_refuse_syntaxe_et_acces_interne() -> None:
    assert "Erreur de syntaxe dans les balises" in _erreurs(docx_avec("{% if %}"))
    assert "rendu d'essai" in _erreurs(docx_avec("{{ ''.__class__.__mro__ }}"))
    assert "rendu d'essai" in _erreurs(docx_avec("{{ mission.titre.__class__ }}"))


def test_analyse_cite_le_contrat_pour_une_balise_inconnue() -> None:
    texte = _erreurs(docx_avec("{{ inconnu }}"))
    assert "Balise inconnue du contrat « Contrat de test » : inconnu." in texte
