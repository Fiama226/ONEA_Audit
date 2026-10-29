import io
import os
import zipfile

import pytest

from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.exceptions import GabaritInvalideError

from .fabrique import CONTRAT_TEST, avec_entrees, docx_avec

NON_DOCX = "n'est pas un document Word .docx valide"
TROP_GROS_DECOMPRESSE = "trop volumineux une fois décompressé"
DOC = "Les fichiers .doc ne sont pas acceptés"


def _analyser(contenu: bytes, nom: str = "g.docx", mo: int = 10) -> frozenset[str]:
    return analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier=nom, taille_max_mo=mo)


def _erreurs(contenu: bytes, nom: str = "g.docx", mo: int = 10) -> str:
    with pytest.raises(GabaritInvalideError) as e:
        _analyser(contenu, nom, mo)
    return "\n".join(e.value.errors["fichier"])


def test_analyse_refuse_balise_inconnue_et_faute_de_frappe() -> None:
    with pytest.raises(GabaritInvalideError) as e:
        analyser_gabarit(
            docx_avec("{{ mision.titre }} {{ mission.titr }}"),
            CONTRAT_TEST,
            nom_fichier="g.docx",
            taille_max_mo=10,
        )
    erreurs = e.value.errors["fichier"]
    assert any("mision" in m for m in erreurs)
    assert any("mission.titr " in m or "mission.titr." in m for m in erreurs)


def test_analyse_renvoie_balises_racines() -> None:
    gabarit = docx_avec("{{ mission.titre }} {{ onea.nom }}", "{{ notes }}")
    assert _analyser(gabarit) == {"mission", "onea", "notes"}


def test_analyse_accepte_boucle_tr() -> None:
    gabarit = docx_avec(
        lignes_tableau=[["{%tr for l in equipe %}"], ["{{ l.nom }}"], ["{%tr endfor %}"]]
    )
    assert _analyser(gabarit) == {"equipe"}


def test_analyse_refuse_faute_dans_boucle() -> None:
    gabarit = docx_avec(
        lignes_tableau=[["{%tr for l in equipe %}"], ["{{ l.nmo }}"], ["{%tr endfor %}"]]
    )
    assert "l.nmo" in _erreurs(gabarit)


def test_analyse_refuse_doc() -> None:
    assert DOC in _erreurs(b"\xd0\xcf\x11\xe0abc", "g.doc")
    assert DOC in _erreurs(docx_avec("x"), "g.DOC")
    # Renamed .doc: detected by content, whatever the extension.
    assert DOC in _erreurs(b"\xd0\xcf\x11\xe0abc", "g.docx")


def test_analyse_refuse_docm_et_macros() -> None:
    assert "macros" in _erreurs(docx_avec("x"), "g.docm")
    avec_macro = avec_entrees(docx_avec("x"), {"word/vbaProject.bin": b"vba"})
    assert "macros" in _erreurs(avec_macro)


def test_analyse_refuse_docm_renomme_en_docx() -> None:
    from .fabrique import avec_entrees as modifier

    contenu = docx_avec("x")
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        types = z.read("[Content_Types].xml")
    types = types.replace(
        b"wordprocessingml.document.main+xml", b"wordprocessingml.document.macroEnabled.main+xml"
    )
    assert b"macroEnabled" in types
    assert "macros" in _erreurs(modifier(contenu, {"[Content_Types].xml": types}))


def test_analyse_refuse_vba_sous_un_autre_nom() -> None:
    contenu = avec_entrees(
        docx_avec("x"),
        {"word/donnees.dat": b"vba"},
        {"word/donnees.dat": "application/vnd.ms-office.vbaProject"},
    )
    assert "macros" in _erreurs(contenu)


def test_analyse_refuse_non_docx() -> None:
    assert NON_DOCX in _erreurs(b"pas un zip")
    assert NON_DOCX in _erreurs(b"PK\x03\x04junk")
    zip_autre = io.BytesIO()
    with zipfile.ZipFile(zip_autre, "w") as z:
        z.writestr("a.txt", "x")
    assert NON_DOCX in _erreurs(zip_autre.getvalue())
    assert NON_DOCX in _erreurs(docx_avec("x"), "g.txt")


def test_analyse_refuse_fichier_trop_gros() -> None:
    gros = avec_entrees(docx_avec("x"), {"word/media/x.png": os.urandom(1_200_000)})
    assert "Le fichier dépasse 1 Mo." in _erreurs(gros, mo=1)


def test_analyse_refuse_bombe_zip() -> None:
    bombe = avec_entrees(docx_avec("x"), {"word/media/bombe.png": bytes(60 * 1024 * 1024)})
    assert len(bombe) < 1024 * 1024
    assert TROP_GROS_DECOMPRESSE in _erreurs(bombe)


def test_analyse_refuse_trop_d_entrees() -> None:
    contenu = avec_entrees(
        docx_avec("x"), {f"word/media/{i}.png": b"" for i in range(2001)}, types_par_defaut=None
    )
    assert TROP_GROS_DECOMPRESSE in _erreurs(contenu)


def test_analyse_refuse_syntaxe() -> None:
    assert "Erreur de syntaxe dans les balises" in _erreurs(docx_avec("{% if %}"))


def test_analyse_refuse_acces_interne() -> None:
    assert "interdit" in _erreurs(docx_avec("{{ ''.__class__.__mro__ }}"))
    assert "interdit" in _erreurs(docx_avec("{{ mission.titre.__class__ }}"))


def test_analyse_cite_le_contrat_pour_une_balise_inconnue() -> None:
    texte = _erreurs(docx_avec("{{ inconnu }}"))
    assert "Balise inconnue du contrat « Contrat de test » : inconnu." in texte
    assert "rendu d'essai" not in texte
