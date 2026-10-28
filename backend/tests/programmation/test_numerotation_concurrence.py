from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import pytest
from django.db import connection

from apps.programmation.services import creer_ligne
from apps.users.models import User
from tests.factories import ProcessusFactory

from .factories import programme


def _dans_un_thread(fn: Callable[..., Any], **kwargs: Any) -> Any:
    """Exécute `fn` dans un thread et ferme la connexion du thread en sortie."""
    try:
        return fn(**kwargs)
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_numeros_concurrents_uniques(rai: User) -> None:
    p = programme(annee=2026)
    proc = ProcessusFactory()

    def creer(i: int) -> Any:
        return _dans_un_thread(
            creer_ligne,
            programme=p,
            titre=f"L{i}",
            type="ASSURANCE",
            processus=proc,
            debut_prevu=date(2026, 3, 1),
            fin_prevue=date(2026, 3, 31),
            by=rai,
        )

    with ThreadPoolExecutor(6) as ex:
        list(ex.map(creer, range(6)))
    assert sorted(p.lignes.values_list("numero", flat=True)) == [1, 2, 3, 4, 5, 6]
