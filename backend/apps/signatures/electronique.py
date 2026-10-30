"""Point d'extension de la signature électronique (lot 7 bis).

Aucune implémentation réelle ici : un signataire est enregistré par le lot 7 bis (PAdES) ou,
en test, par une classe factice. Tant qu'aucun n'est enregistré, le mode électronique est
indisponible.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.documents.models import DocumentVersion


@dataclass(frozen=True)
class ResultatVerification:
    valide: bool
    signataire: str  # sujet du certificat
    signe_le: datetime | None
    motif: str  # message français si invalide


class SignataireElectronique(Protocol):
    def est_signee(self, version: "DocumentVersion") -> bool: ...

    def verifier(self, version: "DocumentVersion") -> ResultatVerification: ...

    # signer(...) est défini par le lot 7 bis, qui porte aussi ses vues.


_signataire: SignataireElectronique | None = None


def enregistrer_signataire_electronique(s: SignataireElectronique | None) -> None:
    """Enregistre (ou, avec None, retire) le signataire électronique de la plateforme."""
    global _signataire  # noqa: PLW0603
    _signataire = s


def signataire_electronique() -> SignataireElectronique | None:
    return _signataire
