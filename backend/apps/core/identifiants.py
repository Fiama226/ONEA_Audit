"""Lecture stricte des identifiants UUID d'un corps de requête (SEC-01).

Les vues de création lisent l'identifiant du parent **avant** le sérialiseur pour répondre
404 ou 403 avant 400. Le `UUIDField` de DRF accepte un entier JSON (`UUID(int=n)`), alors que
`UUID(str(n))` échoue : une garde tolérante laissait donc passer un entier sans aucun contrôle.
Cette fonction unique refuse tout ce qui n'est pas une chaîne (400), pour que la garde et le
sérialiseur ne puissent plus analyser l'identifiant différemment.
"""

from typing import Any
from uuid import UUID

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

MSG_IDENTIFIANT = "Identifiant invalide."


def uuid_strict(brut: Any, champ: str = "identifiant") -> UUID | None:
    """`None` si absent ou illisible (le sérialiseur répondra 400) ; 400 si non-chaîne."""
    if brut is None:
        return None
    if not isinstance(brut, str):
        raise ValidationError({champ: [MSG_IDENTIFIANT]})
    try:
        return UUID(brut)
    except ValueError:
        return None


def uuid_du_corps(request: Request, champ: str) -> UUID | None:
    """Identifiant du champ du corps, lu strictement (voir `uuid_strict`)."""
    donnees = request.data
    brut = donnees.get(champ) if hasattr(donnees, "get") else None
    return uuid_strict(brut, champ)
