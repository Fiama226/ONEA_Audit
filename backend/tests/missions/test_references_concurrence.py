from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import pytest
from django.db import connection

from apps.missions.models import Mission
from apps.missions.services.missions import planifier_mission
from apps.users.models import User
from tests.factories import DirectionFactory, MissionFactory, ProcessusFactory


def _dans_un_thread(fonction: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fonction(*args, **kwargs)
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_references_concurrentes_uniques(rai: User):
    missions = [
        MissionFactory(date_debut_prevue=date(2026, 3, 1), date_fin_prevue=date(2026, 5, 1))
        for _ in range(8)
    ]
    for m in missions:
        m.processus.add(ProcessusFactory())
        m.entites.add(DirectionFactory())
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda m: _dans_un_thread(planifier_mission, m, by=rai), missions))

    refs = sorted(Mission.objects.values_list("reference", flat=True))
    assert refs == [f"DAI/2026/M{n:02d}" for n in range(1, 9)]
