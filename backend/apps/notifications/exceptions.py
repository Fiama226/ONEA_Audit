from apps.core.exceptions import RegleMetierError


class NotificationImmuableError(RegleMetierError):
    """Tentative de modifier autre chose que l'état de lecture d'une notification."""

    def __init__(self) -> None:
        super().__init__("Une notification ne change que par son état de lecture.")
