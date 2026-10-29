import pytest

from apps.accomplissement.models import FicheDeTest
from apps.constats.models import Constat
from apps.constats.services.constats import soumettre_constat, valider_constat
from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from apps.missions.services.etapes import terminer_etape
from apps.missions.services.livrables import livrables_manquants
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def _xiv(mission: Mission) -> EtapeMission:
    return EtapeMission.objects.get(mission=mission, numero=14)


@pytest.fixture
def rai() -> User:
    return make_user(Role.RAI)


def test_terminer_XIV_sans_constat_valide(mission_en_xiv: Mission) -> None:
    assert livrables_manquants(_xiv(mission_en_xiv)) == ["Aucun constat n'est validé."]


def test_constats_non_valides_listes(mission_en_xiv: Mission, chef: User, rai: User) -> None:
    valide = ConstatFactory(mission=mission_en_xiv)
    soumettre_constat(valide, by=chef)
    valider_constat(valide, by=rai)
    brouillon = ConstatFactory(mission=mission_en_xiv)
    assert livrables_manquants(_xiv(mission_en_xiv)) == [
        f"Le constat {brouillon.reference} n'est pas validé."
    ]


def test_terminer_XIV_sans_anomalie_permis(mission_lancee: Mission) -> None:
    assert not FicheDeTest.objects.filter(mission=mission_lancee).exists()
    assert livrables_manquants(_xiv(mission_lancee)) == []


def test_xiv_termine_et_xiii_valide_passent_en_communication(
    mission_en_xiv: Mission, chef: User, rai: User
) -> None:
    Mission.objects.filter(pk=mission_en_xiv.pk).update(statut=StatutMission.EN_ACCOMPLISSEMENT)
    c = ConstatFactory(mission=mission_en_xiv)
    soumettre_constat(c, by=chef)
    valider_constat(c, by=rai)
    assert Constat.objects.filter(mission=mission_en_xiv).count() == 1
    terminer_etape(_xiv(mission_en_xiv), by=chef)
    mission_en_xiv.refresh_from_db()
    assert mission_en_xiv.statut == StatutMission.EN_COMMUNICATION
    assert _xiv(mission_en_xiv).statut == StatutEtape.TERMINEE
