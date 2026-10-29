from collections.abc import Iterator

import pytest

from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services import livrables
from apps.missions.services.livrables import enregistrer_controles, livrables_manquants
from apps.signatures.models import TypeDocumentSignable
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db

_BASE = {1, 2, 4, 11}


def _etape(mission: Mission, numero: int) -> EtapeMission:
    return mission.etapes.get(numero=numero)


def _factice(etape: EtapeMission) -> str | None:
    return "Contrôle factice."


def _autre(etape: EtapeMission) -> str | None:
    return None


@pytest.fixture(autouse=True)
def _registre_isole() -> Iterator[None]:
    """Registre ramené au périmètre du lot 3 pendant le test, restauré ensuite."""
    controles = {k: list(v) for k, v in livrables.CONTROLES.items()}
    gerees = set(livrables.ETAPES_GEREES)
    for numero in set(livrables.CONTROLES) - _BASE:
        del livrables.CONTROLES[numero]
    livrables.ETAPES_GEREES.intersection_update(_BASE)
    yield
    livrables.CONTROLES.clear()
    livrables.CONTROLES.update(controles)
    livrables.ETAPES_GEREES.clear()
    livrables.ETAPES_GEREES.update(gerees)


def test_enregistrer_controles_idempotent() -> None:
    enregistrer_controles(5, [_factice])
    enregistrer_controles(5, [_factice, _factice])
    enregistrer_controles(5, _factice)
    assert livrables.CONTROLES[5] == [_factice]


def test_enregistrer_controles_variadique_et_plusieurs_gestionnaires() -> None:
    enregistrer_controles(5, _factice)
    enregistrer_controles(5, _autre)
    assert livrables.CONTROLES[5] == [_factice, _autre]
    assert 5 in livrables.ETAPES_GEREES


def test_etapes_gerees_initiales() -> None:
    assert livrables.ETAPES_GEREES == _BASE


def test_controle_enregistre_remplace_message_de_lot(mission_lancee: Mission) -> None:
    forcer_etapes(mission_lancee, {5: StatutEtape.EN_COURS})
    etape = _etape(mission_lancee, 5)
    assert "gérés à partir du lot 5" in livrables_manquants(etape)[0]
    enregistrer_controles(5, [_factice])
    assert livrables_manquants(etape) == ["Contrôle factice."]


def test_enregistrer_rien_conserve_le_message_de_lot(mission_lancee: Mission) -> None:
    enregistrer_controles(5, [])
    enregistrer_controles(5)
    assert 5 not in livrables.ETAPES_GEREES
    assert "gérés à partir du lot 5" in livrables_manquants(_etape(mission_lancee, 5))[0]


def test_livrables_lot3_inchanges(mission_lancee: Mission) -> None:
    for numero in (1, 2, 4, 11):
        etape = _etape(mission_lancee, numero)
        assert all("gérés à partir du lot" not in m for m in livrables_manquants(etape))
    assert livrables_manquants(_etape(mission_lancee, 4)) == [
        "Aucun risque n'est sélectionné pour la mission."
    ]


def test_type_validation_referentiel_disponible() -> None:
    assert TypeDocumentSignable.VALIDATION_REFERENTIEL.value == "VALIDATION_REFERENTIEL"
    assert TypeDocumentSignable.VALIDATION_REFERENTIEL.label == "Validation du référentiel d'audit"
