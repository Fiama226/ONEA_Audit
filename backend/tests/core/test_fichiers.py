"""Contrôle commun des téléversements : type réel, macros, bombes zip, tailles."""

import io
import time
import zipfile

import pytest

from apps.core.fichiers import (
    MAX_ENTREES,
    FichierRefuseError,
    TypeDetecte,
    controler_televersement,
    detecter_type,
    est_pdf,
)

PDF = b"%PDF-1.7\n" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
TOUT = frozenset({"pdf", "png", "docx", "xlsx", "odt", "txt", "csv", "msg"})
MO = 1024 * 1024


def fichier(nom: str, contenu: bytes) -> io.BytesIO:
    flux = io.BytesIO(contenu)
    flux.name = nom
    return flux


def zip_de(entrees: dict[str, bytes], *, mimetype_odf: bytes | None = None) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        if mimetype_odf is not None:
            z.writestr("mimetype", mimetype_odf, compress_type=zipfile.ZIP_STORED)
        for nom, donnees in entrees.items():
            z.writestr(nom, donnees)
    return tampon.getvalue()


def docx_minimal(extra: dict[str, bytes] | None = None) -> bytes:
    base = {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w:document/>" * 40}
    return zip_de({**base, **(extra or {})})


def refus(nom: str, contenu: bytes, extensions: frozenset[str] = TOUT, taille_max: int = 50 * MO):
    with pytest.raises(FichierRefuseError) as exc:
        controler_televersement(fichier(nom, contenu), extensions=extensions, taille_max=taille_max)
    assert exc.value.status_http == 400
    assert exc.value.errors == {"fichier": [exc.value.message]}
    return exc.value.message


def test_detecter_type_par_signature() -> None:
    assert detecter_type(PDF[:16]) == "pdf"
    assert detecter_type(PNG[:16]) == "png"
    assert detecter_type(b"\xff\xd8\xff\xe0" + b"0" * 12) == "jpeg"
    assert detecter_type(b"II*\x00" + b"0" * 12) == "tiff"
    assert detecter_type(b"PK\x03\x04" + b"0" * 12) == "zip"
    assert detecter_type(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 8) == "ole"
    assert detecter_type(b"hello") is None
    assert detecter_type(b"") is None
    assert est_pdf(PDF) and not est_pdf(PNG)


def test_pdf_valide_renvoie_le_type_de_l_extension() -> None:
    f = fichier("facture.PDF", PDF)
    detecte = controler_televersement(f, extensions=TOUT, taille_max=MO)
    assert detecte == TypeDetecte("pdf", "application/pdf", "pdf", len(PDF))
    assert f.tell() == 0  # replacé au début pour la suite du traitement


def test_pdf_renomme_png_refuse() -> None:
    assert "ne correspond pas" in refus("photo.png", PDF)


def test_extension_non_autorisee_refusee_meme_avec_bonne_signature() -> None:
    assert "n'est pas accepté" in refus("a.pdf", PDF, extensions=frozenset({"png"}))
    assert "n'est pas accepté" in refus("a.exe", PDF)
    assert "n'est pas accepté" in refus("sans_extension", PDF)
    assert "n'est pas accepté" in refus("a.pdf.exe", PDF)


def test_nom_du_client_avec_chemin_ne_compte_que_pour_l_extension() -> None:
    detecte = controler_televersement(
        fichier("..\\..\\etc/passwd.pdf", PDF), extensions=TOUT, taille_max=MO
    )
    assert detecte.extension == "pdf"
    assert "n'est pas accepté" in refus("a.pdf/..", PDF)


def test_fichier_vide_refuse() -> None:
    assert refus("a.pdf", b"") == "Le fichier est vide."


def test_taille_maximale() -> None:
    limite = 50 * MO
    controler_televersement(
        fichier("a.pdf", b"%PDF-" + b"0" * (limite - 5)), extensions=TOUT, taille_max=limite
    )
    message = refus("a.pdf", b"%PDF-" + b"0" * (limite - 4), taille_max=limite)
    assert message == "Le fichier dépasse la taille maximale de 50 Mo."


def test_macros_par_extension() -> None:
    assert "macros" in refus("g.docm", docx_minimal())
    assert "macros" in refus("g.xlsm", docx_minimal())


def test_docx_contenant_vbaproject_refuse() -> None:
    avec_macro = docx_minimal({"word/vbaProject.bin": b"vba"})
    assert "macros" in refus("g.docx", avec_macro)
    imbrique = docx_minimal({"word/VBAProject.BIN": b"vba"})
    assert "macros" in refus("g.docx", imbrique)


def test_docx_valide_accepte() -> None:
    detecte = controler_televersement(
        fichier("g.docx", docx_minimal()), extensions=TOUT, taille_max=MO
    )
    assert detecte.famille == "zip"


def test_docx_qui_n_est_pas_un_docx() -> None:
    assert "ne correspond pas" in refus("g.docx", b"PK\x03\x04junk")  # zip invalide
    assert "ne correspond pas" in refus("g.docx", zip_de({"a.txt": b"x"}))  # sans word/document.xml
    assert "ne correspond pas" in refus("g.xlsx", docx_minimal())  # docx renommé xlsx
    assert "ne correspond pas" in refus("g.docx", PDF)


def test_odf_exige_le_mimetype() -> None:
    bon = zip_de({"content.xml": b"<x/>"}, mimetype_odf=b"application/vnd.oasis.opendocument.text")
    controler_televersement(fichier("a.odt", bon), extensions=TOUT, taille_max=MO)
    sans = zip_de({"content.xml": b"<x/>"})
    assert "ne correspond pas" in refus("a.odt", sans)
    ods = zip_de(
        {"content.xml": b"<x/>"}, mimetype_odf=b"application/vnd.oasis.opendocument.spreadsheet"
    )
    assert "ne correspond pas" in refus("a.odt", ods)


def _bombe(declare: int) -> bytes:
    """Petit zip dont l'annuaire central annonce `declare` octets décompressés."""
    contenu = docx_minimal()
    octets = bytearray(contenu)
    # Annuaire central : signature PK\x01\x02, taille décompressée à l'offset 24.
    # Le fichier contient deux entrées : on falsifie la taille de la première.
    debut = bytes(octets).index(b"PK\x01\x02")
    octets[debut + 24 : debut + 28] = declare.to_bytes(4, "little")
    return bytes(octets)


def test_bombe_zip_refusee_sans_decompression() -> None:
    bombe = _bombe(500 * MO)
    assert len(bombe) < MO
    debut = time.perf_counter()
    message = refus("bombe.docx", bombe)
    assert time.perf_counter() - debut < 1
    assert "décompressée" in message


def test_ratio_de_compression_excessif_refuse() -> None:
    # 17 Mo annoncés pour moins de 1 Ko : sous les 200 Mo mais au-delà de 20 fois le fichier.
    assert "décompressée" in refus("r.docx", _bombe(17 * MO))


def test_document_word_legitime_tres_compressible_accepte() -> None:
    from tests.documents.fabrique import docx_avec

    contenu = docx_avec("Mission : {{ mission.titre }}")  # ratio ~ 22 : sous le seuil des 16 Mo
    detecte = controler_televersement(fichier("g.docx", contenu), extensions=TOUT, taille_max=MO)
    assert detecte.extension == "docx"


def test_trop_d_entrees_refuse() -> None:
    entrees = {f"word/p{i}.xml": b"x" for i in range(MAX_ENTREES + 1)}
    entrees.update({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<d/>"})
    assert "décompressée" in refus("e.docx", zip_de(entrees))


def test_noms_d_entree_dangereux_refuses() -> None:
    assert "archive" in refus("a.docx", docx_minimal({"../evil.xml": b"x"}))


def test_texte_sans_octets_de_controle() -> None:
    controler_televersement(
        fichier("l.csv", b"a;b\n" * 100000), extensions=TOUT, taille_max=50 * MO
    )
    # octet nul bien après l'en-tête : le balayage porte sur le contenu entier
    assert "ne correspond pas" in refus("l.txt", b"a" * 200_000 + b"\x00" + b"b")
    assert "ne correspond pas" in refus("l.csv", b"\x1b[31mrouge")


def test_signature_ole_pour_msg() -> None:
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 50
    assert controler_televersement(fichier("m.msg", ole), extensions=TOUT, taille_max=MO).mime == (
        "application/vnd.ms-outlook"
    )
    assert "ne correspond pas" in refus("m.msg", PDF)
