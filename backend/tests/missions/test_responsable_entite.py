from django.utils import timezone

from apps.missions import acces
from apps.missions.models import AffectationMission, Mission, RoleMission
from apps.users.models import Role, User
from tests.factories import DirectionFactory, make_user

from .conftest import affecter


def test_est_responsable_entite(mission_lancee: Mission) -> None:
    direction = DirectionFactory(code="DEX")
    autre = DirectionFactory(code="DAF")
    audite = make_user(Role.AUDITE, direction_code="DEX")
    affecter(mission_lancee, audite, RoleMission.AUDITE)
    assert acces.est_responsable_entite(audite, mission_lancee, direction.pk)
    assert not acces.est_responsable_entite(audite, mission_lancee, autre.pk)


def test_non_affecte(mission_lancee: Mission) -> None:
    direction = DirectionFactory(code="DEX")
    audite = make_user(Role.AUDITE, direction_code="DEX")
    assert not acces.est_responsable_entite(audite, mission_lancee, direction.pk)


def test_affectation_retiree(mission_lancee: Mission) -> None:
    direction = DirectionFactory(code="DEX")
    audite = make_user(Role.AUDITE, direction_code="DEX")
    affectation = affecter(mission_lancee, audite, RoleMission.AUDITE)
    AffectationMission.all_objects.filter(pk=affectation.pk).update(deleted_at=timezone.now())
    assert not acces.est_responsable_entite(audite, mission_lancee, direction.pk)


def test_role_auditeur_faux(mission_lancee: Mission, chef: User) -> None:
    direction = DirectionFactory(code="DAI")
    assert chef.direction_code == "DAI"
    assert not acces.est_responsable_entite(chef, mission_lancee, direction.pk)
