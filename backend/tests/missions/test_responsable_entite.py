from django.utils import timezone

import pytest

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


def test_audite_non_designe_responsable(mission_lancee: Mission) -> None:
    direction = DirectionFactory(code="DEX")
    audite = make_user(Role.AUDITE, direction_code="DEX")
    affecter(mission_lancee, audite, RoleMission.AUDITE, responsable_entite=False)
    assert not acces.est_responsable_entite(audite, mission_lancee, direction.pk)


def test_collaborateur_meme_direction_refuse(mission_lancee: Mission) -> None:
    direction = DirectionFactory(code="DEX")
    responsable = make_user(Role.AUDITE, direction_code="DEX")
    collaborateur = make_user(Role.AUDITE, direction_code="DEX")
    affecter(mission_lancee, responsable, RoleMission.AUDITE)
    affecter(mission_lancee, collaborateur, RoleMission.AUDITE, responsable_entite=False)
    assert acces.est_responsable_entite(responsable, mission_lancee, direction.pk)
    assert not acces.est_responsable_entite(collaborateur, mission_lancee, direction.pk)


def test_responsable_autre_mission_sans_effet(mission_lancee: Mission) -> None:
    from tests.factories import MissionFactory

    direction = DirectionFactory(code="DEX")
    audite = make_user(Role.AUDITE, direction_code="DEX")
    affecter(MissionFactory(), audite, RoleMission.AUDITE)
    affecter(mission_lancee, audite, RoleMission.AUDITE, responsable_entite=False)
    assert not acces.est_responsable_entite(audite, mission_lancee, direction.pk)


def test_contrainte_responsable_reserve_aux_audites(mission_lancee: Mission) -> None:
    from django.db import IntegrityError, transaction

    from tests.factories import AffectationFactory

    with pytest.raises(IntegrityError), transaction.atomic():
        AffectationFactory(
            mission=mission_lancee,
            utilisateur=make_user(Role.AUDITEUR),
            role_mission=RoleMission.AUDITEUR,
            responsable_entite=True,
        )


def test_reprise_des_affectations_existantes(mission_lancee: Mission) -> None:
    import importlib

    from django.apps import apps

    from tests.factories import AffectationFactory, MissionFactory

    reprise = importlib.import_module(
        "apps.missions.migrations.0003_responsable_entite"
    ).designer_responsables_existants

    def aff(mission: Mission, direction: str, **kw: object) -> AffectationMission:
        return AffectationFactory(
            mission=mission,
            utilisateur=make_user(Role.AUDITE, direction_code=direction),
            role_mission=RoleMission.AUDITE,
            **kw,
        )

    seule = aff(mission_lancee, "DEX")
    premiere = aff(mission_lancee, "DAF")
    seconde = aff(mission_lancee, "DAF")
    retiree = aff(mission_lancee, "DRH")
    AffectationMission.all_objects.filter(pk=retiree.pk).update(deleted_at=timezone.now())
    sans_direction = aff(mission_lancee, "")
    autre_mission = aff(MissionFactory(), "DAF")
    intervenant = AffectationFactory(mission=mission_lancee, role_mission=RoleMission.AUDITEUR)

    reprise(apps, None)

    def valeur(a: AffectationMission) -> bool:
        return AffectationMission.all_objects.get(pk=a.pk).responsable_entite

    assert valeur(seule)
    assert valeur(premiere) and not valeur(seconde)
    assert not valeur(retiree) and not valeur(sans_direction)
    assert valeur(autre_mission)
    assert not valeur(intervenant)
