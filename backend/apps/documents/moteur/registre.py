"""Registry of document types and the protocol of the data providers that feed them."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from apps.core.exceptions import RegleMetierError

from .contrats import Contrat

if TYPE_CHECKING:
    from apps.core.models import BaseModel
    from apps.missions.models import Mission
    from apps.signatures.models import Confirmation
    from apps.users.models import User


class Fournisseur(Protocol):
    """Source-object access, rights and context of one kind of business document."""

    def objet(self, objet_id: UUID) -> "BaseModel":
        """Return the source object or raise Http404."""
        ...

    def mission_de(self, objet: "BaseModel") -> "Mission": ...

    def objets_de_mission(self, mission: "Mission") -> "list[BaseModel]": ...

    def peut_consulter(self, user: "User", objet: "BaseModel") -> bool: ...

    def peut_generer(self, user: "User", objet: "BaseModel") -> bool: ...

    def raison_non_generable(self, objet: "BaseModel") -> str | None: ...

    def contexte(self, objet: "BaseModel") -> dict[str, Any]:
        """Context without the common blocks `onea` and `document`."""
        ...

    def confirmation(self, objet: "BaseModel") -> "Confirmation | None": ...


@dataclass(frozen=True)
class TypeDocument:
    code: str
    libelle: str
    etape: int | None
    contrat: Contrat
    abreviation: str
    modele_numero: str
    portee_numero: str
    fournisseur: Fournisseur


_TYPES: dict[str, TypeDocument] = {}


def enregistrer_type(t: TypeDocument) -> None:
    if t.code in _TYPES:
        raise ValueError(f"Type de document déjà enregistré : {t.code}.")
    _TYPES[t.code] = t


def type_document(code: str) -> TypeDocument:
    try:
        return _TYPES[code]
    except KeyError:
        raise RegleMetierError(f"Type de document inconnu : {code}.") from None


def types_documents() -> list[TypeDocument]:
    """Registered types ordered by step (unattached last) then label."""
    return sorted(
        _TYPES.values(),
        key=lambda t: (t.etape is None, t.etape or 0, t.libelle),
    )
