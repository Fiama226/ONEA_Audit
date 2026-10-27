class RegleMetierError(Exception):
    """Business rule violation, converted to HTTP 422 by the API exception handler."""

    def __init__(self, message: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors: dict[str, list[str]] = errors or {}


class SuppressionPhysiqueInterditeError(RuntimeError):
    """Raised on any attempt to physically delete a business object."""

    def __init__(
        self, message: str = "Suppression physique interdite : utiliser soft_delete()."
    ) -> None:
        super().__init__(message)
