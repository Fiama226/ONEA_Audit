from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import Mock

import pytest
from django.db import connection

from apps.core.exceptions import RegleMetierError
from apps.documents import tasks
from apps.documents.models import Document, DocumentVersion, GabaritDocument
from apps.documents.moteur.registre import TypeDocument
from apps.documents.services.generation import demander_generation
from apps.missions.models import Mission
from apps.users.models import User


@pytest.mark.django_db(transaction=True)
def test_demandes_concurrentes_une_seule_version(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The worker is not run: the version stays EN_ATTENTE, so the others are refused.
    monkeypatch.setattr(tasks.generer_version, "delay", Mock())

    def une(_: int) -> str:
        try:
            demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
            return "ok"
        except RegleMetierError as exc:
            return exc.message
        finally:
            connection.close()

    with ThreadPoolExecutor(4) as ex:
        resultats: list[Any] = list(ex.map(une, range(4)))
    assert resultats.count("ok") == 1
    assert resultats.count("Une génération est déjà en cours.") == 3
    assert DocumentVersion.all_objects.count() == 1 and Document.all_objects.count() == 1
