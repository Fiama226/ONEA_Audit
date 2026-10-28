from apps.core.exceptions import RegleMetierError


class ConfirmationImmuableError(RegleMetierError):
    """Tentative de modification ou de suppression d'une confirmation."""

    def __init__(self) -> None:
        super().__init__(
            "Une confirmation est définitive : elle ne peut être ni modifiée ni supprimée."
        )
