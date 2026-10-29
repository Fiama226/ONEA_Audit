import os
from typing import Any

import pytest
import requests

from apps.documents.models import GabaritDocument
from apps.documents.moteur.registre import TypeDocument
from apps.documents.services.generation import demander_generation, ouvrir_version
from apps.missions.models import Mission
from apps.users.models import User

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://localhost:3000")


def _disponible() -> bool:
    try:
        return requests.get(f"{GOTENBERG_URL}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


@pytest.mark.gotenberg
@pytest.mark.django_db
@pytest.mark.skipif(not _disponible(), reason="Gotenberg indisponible")
def test_generation_bout_en_bout_gotenberg_reel(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    settings: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    settings.GOTENBERG_URL = GOTENBERG_URL
    with django_capture_on_commit_callbacks(execute=True):
        v = demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    v.refresh_from_db()
    assert (v.statut, v.statut_pdf) == ("PRETE", "PRET")
    contenu, nom = ouvrir_version(v, format="PDF", by=rai, adresse_ip=None)
    assert contenu.startswith(b"%PDF-") and nom.endswith("_v1.pdf")
