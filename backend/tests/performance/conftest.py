"""Fixtures de performance : volumétrie de démonstration réduite, jouée dans une transaction.

Les données sont créées une fois par module par `peupler_tout` (services publics, comme la
commande `peupler_demo`) puis annulées à la fin du module : aucune fuite vers les autres tests.
"""

from collections.abc import Iterator
from typing import Any

import pytest
import yaml
from django.db import connection, transaction
from rest_framework.test import APIClient

from apps.core import demo
from apps.users.models import User

from .outils import contexte_complet
from .seed import semer_domaine

ECHELLE = 0.2


@pytest.fixture(scope="module")
def volumetrie(django_db_setup: None, django_db_blocker: Any) -> Iterator[dict[str, Any]]:
    with django_db_blocker.unblock(), transaction.atomic():
        ctx = demo.ContexteDemo(
            profil="volumetrie",
            echelle=ECHELLE,
            graine=demo.GRAINE_PAR_DEFAUT,
            volumes=demo.volumes("volumetrie", ECHELLE),
            avec_pdf=False,
            sortie=lambda _m: None,
        )
        demo.peupler_tout(ctx)
        contexte = contexte_complet(semer_domaine(), client_pour("rai"))
        connection.cursor().execute("ANALYZE")
        yield contexte
        transaction.set_rollback(True)


def client_pour(username: str) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=User.objects.get(username=username))
    return client


def routes_get() -> dict[str, frozenset[str]]:
    """Chemins GET du schema OpenAPI (hors routes de test) et leurs parametres de requete."""
    from drf_spectacular.generators import SchemaGenerator

    schema: dict[str, Any] = yaml.safe_load(
        yaml.safe_dump(SchemaGenerator().get_schema(request=None, public=True))
    )
    return {
        chemin: frozenset(
            p["name"] for p in ops["get"].get("parameters", []) if p.get("in") == "query"
        )
        for chemin, ops in sorted(schema["paths"].items())
        if "get" in ops and "/_test/" not in chemin
    }
