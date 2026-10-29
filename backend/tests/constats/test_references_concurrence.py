from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from apps.constats.models import Constat
from apps.constats.services.constats import creer_constat
from apps.missions.models import StatutEtape
from apps.users.models import User
from tests.factories import DirectionFactory, ProcessusFactory
from tests.missions.conftest import forcer_etapes


def _creer(mission: Any, chef: User, champs: dict[str, Any]) -> str:
    try:
        return creer_constat(mission, titre="T", by=chef, **champs).reference
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_references_constats_concurrentes(mission_lancee: Any, chef: User) -> None:
    forcer_etapes(mission_lancee, {14: StatutEtape.EN_COURS})
    entite, processus = DirectionFactory(), ProcessusFactory()
    mission_lancee.entites.add(entite)
    mission_lancee.processus.add(processus)
    champs = {"entite": entite, "processus": processus}
    with ThreadPoolExecutor(6) as ex:
        refs = list(ex.map(lambda _: _creer(mission_lancee, chef, champs), range(6)))
    assert sorted(refs) == [f"C-{n:02d}" for n in range(1, 7)]
    assert Constat.objects.filter(mission=mission_lancee).count() == 6
