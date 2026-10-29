import hashlib
import os
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pytest

from apps.accomplissement.stockage import (
    FichierIntrouvableError,
    FichierTropVolumineuxError,
    StockageDisque,
    StockageError,
    StockageFichiers,
    empreinte_fichier,
)
from tests.accomplissement.fakes import StockageDisqueTemporaire

IMPLEMENTATIONS: list[Callable[[Path], StockageFichiers]] = [
    StockageDisqueTemporaire,
    StockageDisque,
]


@pytest.fixture(params=IMPLEMENTATIONS, ids=["fake", "disque"])
def stockage(request: pytest.FixtureRequest, tmp_path: Path) -> StockageFichiers:
    return request.param(tmp_path / "racine")


def _fichiers(racine: Path) -> list[Path]:
    return [p for p in racine.rglob("*") if p.is_file()]


def test_contrat_ecriture_et_sha256(stockage: StockageFichiers, tmp_path: Path) -> None:
    contenu = b"contenu de la preuve" * 1000
    stocke = stockage.deposer(BytesIO(contenu), prefixe="preuves/m1", taille_max=10**6)
    assert stocke.sha256 == hashlib.sha256(contenu).hexdigest()
    assert stocke.taille == len(contenu)
    assert stocke.cle.startswith("preuves/m1/")
    assert stockage.existe(stocke.cle)
    with stockage.ouvrir(stocke.cle) as f:
        assert f.read() == contenu
    assert empreinte_fichier(stockage, stocke.cle) == stocke.sha256
    assert len(_fichiers(tmp_path / "racine")) == 1  # aucun fichier temporaire résiduel


def test_contrat_jamais_ecrase(stockage: StockageFichiers) -> None:
    a = stockage.deposer(BytesIO(b"a"), prefixe="preuves/m1", taille_max=10)
    b = stockage.deposer(BytesIO(b"a"), prefixe="preuves/m1", taille_max=10)
    assert a.cle != b.cle
    assert a.sha256 == b.sha256


def test_contrat_taille_depassee_sans_residu(stockage: StockageFichiers, tmp_path: Path) -> None:
    with pytest.raises(FichierTropVolumineuxError, match="50 Mo"):
        stockage.deposer(BytesIO(b"x" * 11), prefixe="preuves/m1", taille_max=10)
    assert _fichiers(tmp_path / "racine") == []


@pytest.mark.parametrize("prefixe", ["../evasion", "preuves/../..", "/etc", "a//b", "C:/x", ""])
def test_contrat_prefixe_malveillant(stockage: StockageFichiers, prefixe: str) -> None:
    with pytest.raises(StockageError):
        stockage.deposer(BytesIO(b"x"), prefixe=prefixe, taille_max=10)


@pytest.mark.parametrize("cle", ["../x", "/etc/passwd", "preuves/m1/inconnue", "preuves/m1/.."])
def test_contrat_cle_inconnue_ou_hors_racine(stockage: StockageFichiers, cle: str) -> None:
    assert not stockage.existe(cle)
    with pytest.raises(FichierIntrouvableError):
        stockage.ouvrir(cle)


@pytest.mark.skipif(os.name == "nt", reason="modes POSIX")
def test_contrat_droits_prives(stockage: StockageFichiers, tmp_path: Path) -> None:
    stocke = stockage.deposer(BytesIO(b"x"), prefixe="preuves/m1", taille_max=10)
    fichier = tmp_path / "racine" / stocke.cle
    assert fichier.stat().st_mode & 0o777 == 0o640
    assert fichier.parent.stat().st_mode & 0o777 == 0o750
