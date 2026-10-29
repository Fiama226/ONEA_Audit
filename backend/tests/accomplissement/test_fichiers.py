import pytest
from django.test import override_settings

from apps.accomplissement.fichiers import (
    EXTENSIONS_AUTORISEES,
    controler_fichier,
    nom_affichable,
)
from apps.core.exceptions import RegleMetierError

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50
PDF = b"%PDF-1.7\n" + b"0" * 50


def test_extensions_autorisees_sans_dangereuses() -> None:
    for dangereuse in ("exe", "html", "svg", "js", "php", "bat", "zip", "dll"):
        assert dangereuse not in EXTENSIONS_AUTORISEES


def test_pdf_valide_renvoie_le_type_mime_de_l_extension() -> None:
    assert controler_fichier("facture.pdf", PDF[:16], len(PDF)) == "application/pdf"
    assert controler_fichier("PHOTO.JPG", b"\xff\xd8\xff\xe0" + b"0" * 12, 100) == "image/jpeg"


def test_type_usurpe_refuse() -> None:
    with pytest.raises(RegleMetierError) as exc:
        controler_fichier("photo.pdf", PNG[:16], 100)
    assert str(exc.value) == "Le contenu du fichier ne correspond pas à son extension."


@pytest.mark.parametrize("nom", ["virus.exe", "page.html", "sans_extension", "archive.pdf.exe"])
def test_extension_refusee(nom: str) -> None:
    with pytest.raises(RegleMetierError) as exc:
        controler_fichier(nom, PDF[:16], 100)
    assert str(exc.value) == "Ce type de fichier n'est pas accepté."


def test_fichier_vide() -> None:
    with pytest.raises(RegleMetierError) as exc:
        controler_fichier("a.pdf", b"", 0)
    assert str(exc.value) == "Le fichier est vide."


def test_taille_maximale() -> None:
    limite = 50 * 1024 * 1024
    assert controler_fichier("a.pdf", PDF[:16], limite) == "application/pdf"
    with pytest.raises(RegleMetierError) as exc:
        controler_fichier("a.pdf", PDF[:16], limite + 1)
    assert str(exc.value) == "Le fichier dépasse la taille maximale de 50 Mo."


@override_settings(PIECE_TAILLE_MAX_OCTETS=10)
def test_taille_maximale_lue_dans_les_reglages() -> None:
    with pytest.raises(RegleMetierError):
        controler_fichier("a.pdf", PDF[:16], 11)


def test_texte_avec_octets_nuls_refuse() -> None:
    assert controler_fichier("liste.csv", b"a;b\n1;2\n", 8) == "text/csv"
    with pytest.raises(RegleMetierError):
        controler_fichier("liste.txt", b"abc\x00def", 7)


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\x\\rapport.pdf", "rapport.pdf"),
        ("fa\x00ct\x1fure\n.pdf", "facture.pdf"),
        ("", "fichier"),
        ("..", "fichier"),
        ("   ", "fichier"),
    ],
)
def test_nom_affichable(brut: str, attendu: str) -> None:
    assert nom_affichable(brut) == attendu


def test_nom_affichable_plafonne_a_255_en_gardant_l_extension() -> None:
    nom = nom_affichable("a" * 400 + ".pdf")
    assert len(nom) == 255
    assert nom.endswith(".pdf")
