"""Faux stockage de test : disque temporaire, conforme au contrat `StockageFichiers`."""

from pathlib import Path

from apps.accomplissement.stockage import StockageDisque


class StockageDisqueTemporaire(StockageDisque):
    """Même comportement que le stockage disque, mais pour une racine `tmp_path`."""

    def __init__(self, racine: str | Path) -> None:
        super().__init__(racine)
