from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction

from apps.documents.models import Document
from apps.documents.numerotation import attribuer_numero
from apps.missions.models import Mission


@pytest.mark.django_db(transaction=True)
def test_numeros_concurrents_uniques(type_test: object, mission_planifiee: Mission) -> None:
    ct = ContentType.objects.get_for_model(Mission)

    def un(i: int) -> str:
        try:
            with transaction.atomic():
                numero, annee, sequence = attribuer_numero("TEST_DOC", mission=mission_planifiee)
                Document.objects.create(
                    type_document="TEST_DOC",
                    mission=mission_planifiee,
                    content_type=ct,
                    object_id=mission_planifiee.pk if i == 0 else uuid4(),
                    numero=numero,
                    annee=annee,
                    sequence=sequence,
                )
                return numero
        finally:
            connection.close()

    with ThreadPoolExecutor(8) as ex:
        numeros = sorted(ex.map(un, range(8)))
    assert numeros == [f"{mission_planifiee.reference}/TD-{n:02d}" for n in range(1, 9)]
