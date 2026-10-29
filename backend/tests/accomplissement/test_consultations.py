import pytest

from apps.accomplissement.models import FicheDeTest
from apps.core.consultations import Consultation, journaliser_consultation
from apps.core.exceptions import RegleMetierError
from apps.users.models import Role
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def test_consultation_journalisee_en_ajout_seul(fiche_brouillon: FicheDeTest) -> None:
    user = make_user(Role.RAI)
    journaliser_consultation(
        fiche_brouillon, par=user, action="TELECHARGEMENT", adresse_ip="10.0.0.1"
    )
    c = Consultation.objects.get()
    assert (c.object_id, c.par, c.action) == (fiche_brouillon.pk, user, "TELECHARGEMENT")
    c.action = "CONSULTATION"
    with pytest.raises(RegleMetierError):
        c.save()
    with pytest.raises(RegleMetierError):
        Consultation.objects.update(action="CONSULTATION")
