"""Règle de gouvernance « contrôle d'objectivité » (Normes IIA 2.2) à l'affectation et à l'ordre."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.gouvernance import regles_gouvernance as rg
from apps.missions.models import AffectationMission, Mission, RoleMission, TypeMission
from apps.missions.services.equipe import affecter, remplacer_chef
from apps.missions.services.objectivite import conflits
from apps.notifications.models import Notification
from apps.referentiel.models import Direction
from apps.users.models import Role, User
from tests.factories import AffectationFactory, DirectionFactory, MissionFactory, make_user
from tests.regles import regler

pytestmark = pytest.mark.django_db


@pytest.fixture
def entite() -> Direction:
    return DirectionFactory(code="DFC", libelle="Direction financière")


@pytest.fixture
def mission(entite: Direction) -> Mission:
    mission = MissionFactory(type=TypeMission.ASSURANCE)
    mission.entites.add(entite)
    return mission


def _ancienne_mission(entite: Direction, *, type_: str, il_y_a_jours: int) -> Mission:
    ancienne = MissionFactory(type=type_, reference=f"DAI/2025/M{il_y_a_jours % 90:02d}")
    ancienne.entites.add(entite)
    return ancienne


def _affectation_passee(
    mission: Mission, utilisateur: User, role: str, il_y_a_jours: int
) -> AffectationMission:
    affectation = AffectationFactory(mission=mission, utilisateur=utilisateur, role_mission=role)
    AffectationMission.objects.filter(pk=affectation.pk).update(
        created_at=timezone.now() - timedelta(days=il_y_a_jours)
    )
    return affectation


def test_auditor_from_the_audited_entity_is_blocked(rai: User, mission: Mission) -> None:
    auditeur = make_user(Role.AUDITEUR, direction_code="DFC")
    with pytest.raises(RegleMetierError) as exc:
        affecter(mission, utilisateur=auditeur, role_mission=RoleMission.AUDITEUR, by=rai)
    assert "Direction financière" in exc.value.message
    assert "utilisateur" in exc.value.errors
    assert not AffectationMission.objects.filter(mission=mission, utilisateur=auditeur).exists()


def test_recent_auditee_of_the_same_entity_is_blocked(
    rai: User, mission: Mission, entite: Direction
) -> None:
    auditeur = make_user(Role.AUDITEUR)
    ancienne = _ancienne_mission(entite, type_=TypeMission.ASSURANCE, il_y_a_jours=100)
    _affectation_passee(ancienne, auditeur, RoleMission.AUDITE, il_y_a_jours=100)
    assert conflits(mission, auditeur)
    with pytest.raises(RegleMetierError):
        affecter(mission, utilisateur=auditeur, role_mission=RoleMission.CHEF_MISSION, by=rai)


def test_cooling_off_period_is_honoured(rai: User, mission: Mission, entite: Direction) -> None:
    auditeur = make_user(Role.AUDITEUR)
    ancienne = _ancienne_mission(entite, type_=TypeMission.ASSURANCE, il_y_a_jours=400)
    _affectation_passee(ancienne, auditeur, RoleMission.AUDITE, il_y_a_jours=400)
    assert conflits(mission, auditeur) == []
    regler(rg.OBJECTIVITY, cooling_off_months=24)
    assert conflits(mission, auditeur)


def test_recent_advisory_mission_blocks_an_assurance_mission(
    rai: User, mission: Mission, entite: Direction
) -> None:
    auditeur = make_user(Role.AUDITEUR)
    conseil = _ancienne_mission(entite, type_=TypeMission.CONSEIL, il_y_a_jours=30)
    _affectation_passee(conseil, auditeur, RoleMission.AUDITEUR, il_y_a_jours=30)
    messages = conflits(mission, auditeur)
    assert len(messages) == 1 and "conseil" in messages[0]


def test_auditee_assignment_is_never_checked(rai: User, mission: Mission) -> None:
    audite = make_user(Role.AUDITE, direction_code="DFC")
    affecter(mission, utilisateur=audite, role_mission=RoleMission.AUDITE, by=rai)


def test_warning_mode_assigns_and_records_the_alert(rai: User, mission: Mission) -> None:
    regler(rg.OBJECTIVITY, mode="WARN")
    autre_rai = make_user(Role.RAI)
    auditeur = make_user(Role.AUDITEUR, direction_code="DFC")
    affectation = affecter(mission, utilisateur=auditeur, role_mission=RoleMission.AUDITEUR, by=rai)
    affectation.refresh_from_db()
    assert Notification.objects.filter(destinataire=autre_rai, type="ALERTE_OBJECTIVITE").exists()
    assert "Direction financière" in affectation.alerte_objectivite
    # Le RAI auteur de l'affectation n'est pas notifié ; un autre RAI l'est.
    assert not Notification.objects.filter(destinataire=rai, type="ALERTE_OBJECTIVITE").exists()


def test_disabled_check_assigns_without_alert(rai: User, mission: Mission) -> None:
    regler(rg.OBJECTIVITY, enabled=False)
    auditeur = make_user(Role.AUDITEUR, direction_code="DFC")
    affectation = affecter(mission, utilisateur=auditeur, role_mission=RoleMission.AUDITEUR, by=rai)
    assert affectation.alerte_objectivite == ""


def test_new_chief_is_checked_too(rai: User, mission: Mission) -> None:
    chef = make_user(Role.AUDITEUR)
    affecter(mission, utilisateur=chef, role_mission=RoleMission.CHEF_MISSION, by=rai)
    remplacant = make_user(Role.AUDITEUR, direction_code="DFC")
    with pytest.raises(RegleMetierError):
        remplacer_chef(mission, utilisateur=remplacant, by=rai)


def test_order_emission_rechecks_the_team(rai: User, entite: Direction) -> None:
    """Entités posées après l'affectation : le contrôle est refait à l'émission de l'ordre."""
    from apps.missions.services.objectivite import controler_equipe

    mission = MissionFactory(type=TypeMission.ASSURANCE)
    auditeur = make_user(Role.AUDITEUR, direction_code="DFC")
    affecter(mission, utilisateur=auditeur, role_mission=RoleMission.AUDITEUR, by=rai)
    mission.entites.add(entite)
    with pytest.raises(RegleMetierError) as exc:
        controler_equipe(mission, by=rai)
    assert "Direction financière" in exc.value.message
    regler(rg.OBJECTIVITY, mode="WARN")
    controler_equipe(mission, by=rai)
    alerte = AffectationMission.objects.get(mission=mission, utilisateur=auditeur)
    assert "Direction financière" in alerte.alerte_objectivite
