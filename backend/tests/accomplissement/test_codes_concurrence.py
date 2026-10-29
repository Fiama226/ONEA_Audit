from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from apps.accomplissement.models import ProgrammeDeTravail, TestPrevu
from apps.accomplissement.services.tests_prevus import creer_test
from apps.users.models import User


def _dans_un_thread(fonction: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fonction(*args, **kwargs)
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_codes_tests_concurrents_uniques(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    with ThreadPoolExecutor(8) as ex:
        list(
            ex.map(
                lambda i: _dans_un_thread(
                    creer_test,
                    programme_viii,
                    libelle=f"Test {i}",
                    nature="EXAMEN_DOCUMENTAIRE",
                    by=chef,
                ),
                range(8),
            )
        )
    codes = sorted(TestPrevu.all_objects.values_list("code", flat=True))
    assert codes == [f"T-{n:02d}" for n in range(1, 9)]


@pytest.mark.django_db(transaction=True)
def test_numero_tient_compte_des_tests_supprimes(
    programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    t = creer_test(programme_viii, libelle="a", nature="AUTRE", by=chef)
    TestPrevu.objects.get(pk=t.pk).soft_delete(chef)
    with ThreadPoolExecutor(4) as ex:
        list(
            ex.map(
                lambda i: _dans_un_thread(
                    creer_test, programme_viii, libelle=f"b{i}", nature="AUTRE", by=chef
                ),
                range(4),
            )
        )
    codes = sorted(TestPrevu.all_objects.values_list("code", flat=True))
    assert codes == [f"T-{n:02d}" for n in range(1, 6)]
