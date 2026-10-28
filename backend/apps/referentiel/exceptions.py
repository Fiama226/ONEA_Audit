from apps.core.exceptions import RegleMetierError


class CartographieFigeeError(RegleMetierError):
    """Modification d'une cartographie validée (immuable)."""

    def __init__(self, annee: int) -> None:
        super().__init__(f"La cartographie {annee} est validée : elle ne peut plus être modifiée.")
        self.annee = annee
