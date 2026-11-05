"""Réglage des règles de gouvernance dans les tests, par le service (piste d'audit comprise)."""

from typing import Any

from apps.gouvernance import regles_gouvernance as rg
from apps.users.models import Role
from tests.factories import make_user


def regler(cle: str, **valeurs: Any) -> None:
    """Change la règle `cle` comme le ferait l'ADMIN (motif fourni)."""
    admin = make_user(Role.ADMIN)
    rg.modifier(cle, valeurs, motif="Réglage de test", by=admin)
