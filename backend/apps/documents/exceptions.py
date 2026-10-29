from apps.core.exceptions import RegleMetierError


class VersionFigeeError(RegleMetierError):
    """A generated document version is final: only the PDF conversion fields may change."""

    def __init__(self) -> None:
        super().__init__("Une version de document générée est définitive.")


class GabaritFigeError(RegleMetierError):
    """The file of a template is final: a new version must be uploaded instead."""

    def __init__(self) -> None:
        super().__init__("Le fichier d'un gabarit est définitif : déposez une nouvelle version.")


class DocumentFigeError(RegleMetierError):
    """The identity and number of a document are final."""

    def __init__(self) -> None:
        super().__init__("L'identité et le numéro d'un document sont définitifs.")


class ConsultationImmuableError(RegleMetierError):
    """A consultation record is append-only."""

    def __init__(self) -> None:
        super().__init__("Une consultation est enregistrée une fois pour toutes.")
