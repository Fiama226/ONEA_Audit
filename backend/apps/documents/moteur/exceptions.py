from apps.core.exceptions import RegleMetierError


class GabaritInvalideError(RegleMetierError):
    """A Word template failed verification; all problems are listed under errors["fichier"]."""

    def __init__(self, erreurs: list[str]) -> None:
        super().__init__("Le gabarit est invalide.", errors={"fichier": erreurs})


class RenduError(Exception):
    """A template could not be rendered; the message is in French and safe to show."""
