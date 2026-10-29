import pytest
from django.utils import timezone

from apps.programmation.models import ProgrammeAnnuel, StatutProgramme
from tests.factories import make_user

from .factories import ligne, programme, reset_sequences


@pytest.fixture(autouse=True)
def _reset_programmation_sequences() -> None:
    reset_sequences()


@pytest.fixture
def programme_valide(db: None) -> ProgrammeAnnuel:
    """Programme validé avec deux lignes.

    La validation est posée par un `update` SQL direct sur `_base_manager` (hors
    QuerySets gardés) : uniquement pour les tests, le service de validation viendra plus tard.
    """
    prog = programme()
    ligne(programme=prog, numero=1)
    ligne(programme=prog, numero=2)
    ProgrammeAnnuel._base_manager.filter(pk=prog.pk).update(
        statut=StatutProgramme.VALIDE, valide_le=timezone.now(), valide_par=make_user()
    )
    prog.refresh_from_db()
    return prog
