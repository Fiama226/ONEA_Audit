import pytest

from apps.constats.models import Recommandation
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.recommandations.exceptions import MSG_STATUT_SUIVI
from apps.recommandations.models import AcceptationRisque, Action, StatutAction
from tests.constats.factories import RecommandationFactory
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes
from tests.recommandations.factories import (
    AcceptationFactory,
    ActionFactory,
    EngagementFactory,
)

pytestmark = pytest.mark.django_db


def test_action_figee_apres_xvi_sauf_champs_suivi(
    mission_en_communication: Mission, recommandations: list[Recommandation]
) -> None:
    action = ActionFactory(recommandation=recommandations[0])
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    action.libelle = "autre"
    with pytest.raises(EtapeCloseError) as exc:
        action.save()
    assert exc.value.romain == "XVI"
    action.refresh_from_db()
    action.statut = StatutAction.EN_COURS
    with pytest.raises(RegleMetierError, match="suivi des recommandations"):
        action.save()
    with pytest.raises(EtapeCloseError):
        ActionFactory(recommandation=recommandations[0])
    with pytest.raises(EtapeCloseError):
        action.soft_delete(make_user())

    Mission.objects.filter(pk=mission_en_communication.pk).update(
        statut=StatutMission.RAPPORT_DIFFUSE
    )
    action.refresh_from_db()
    action.statut = StatutAction.EN_COURS
    action.save()
    action.refresh_from_db()
    assert action.statut == StatutAction.EN_COURS
    action.libelle = "autre"
    with pytest.raises(EtapeCloseError):
        action.save()


def test_statut_refuse_en_communication_meme_xvi_ouverte(
    recommandations: list[Recommandation],
) -> None:
    action = ActionFactory(recommandation=recommandations[0])
    action.statut = StatutAction.REALISEE
    with pytest.raises(RegleMetierError) as exc:
        action.save()
    assert str(exc.value) == MSG_STATUT_SUIVI


def test_update_queryset_garde(
    mission_en_communication: Mission, recommandations: list[Recommandation]
) -> None:
    action = ActionFactory(recommandation=recommandations[0])
    with pytest.raises(RegleMetierError):
        Action.objects.filter(pk=action.pk).update(statut=StatutAction.REALISEE)
    action.statut = StatutAction.REALISEE
    with pytest.raises(RegleMetierError):
        Action.objects.bulk_update([action], ["statut"])
    Action.objects.filter(pk=action.pk).update(libelle="modifié")
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        Action.objects.filter(pk=action.pk).update(libelle="x")
    with pytest.raises(EtapeCloseError):
        Action.objects.filter(pk=action.pk).update(deleted_at="2026-01-01T00:00:00Z")
    action.libelle = "x"
    with pytest.raises(EtapeCloseError):
        Action.objects.bulk_update([action], ["libelle"])
    with pytest.raises(EtapeCloseError):
        Action.objects.bulk_create([ActionFactory.build(recommandation=recommandations[0])])
    with pytest.raises(RegleMetierError):
        Action.objects.bulk_create(
            [ActionFactory.build(recommandation=recommandations[0])], update_conflicts=True
        )


def test_acceptation_retrait_exige_xvi_ouverte(
    mission_en_communication: Mission, recommandations: list[Recommandation]
) -> None:
    acceptation = AcceptationFactory(recommandation=recommandations[0])
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        acceptation.soft_delete(make_user())
    with pytest.raises(EtapeCloseError):
        AcceptationFactory(recommandation=recommandations[1])


def test_action_recommandation_autre_mission(mission_en_communication: Mission) -> None:
    autre = RecommandationFactory()
    with pytest.raises(RegleMetierError, match="n'appartient pas"):
        ActionFactory(recommandation=autre, mission=mission_en_communication)


@pytest.mark.parametrize("cible", ["recommandations"])
def test_mission_suspendue_refuse_toutes_ecritures_lot7(
    cible: str, mission_en_communication: Mission, recommandations: list[Recommandation]
) -> None:
    action = ActionFactory(recommandation=recommandations[0])
    acceptation = AcceptationFactory(recommandation=recommandations[1])
    engagement = EngagementFactory(mission=mission_en_communication)
    Mission.objects.filter(pk=mission_en_communication.pk).update(statut=StatutMission.SUSPENDUE)

    with pytest.raises(MissionFigeeError):
        ActionFactory(recommandation=recommandations[2])
    action.libelle = "x"
    with pytest.raises(MissionFigeeError):
        action.save()
    with pytest.raises(MissionFigeeError):
        Action.objects.filter(pk=action.pk).update(libelle="x")
    with pytest.raises(MissionFigeeError):
        Action.objects.bulk_update([action], ["libelle"])
    with pytest.raises(MissionFigeeError):
        action.soft_delete(make_user())
    with pytest.raises(MissionFigeeError):
        AcceptationFactory(recommandation=recommandations[2])
    with pytest.raises(MissionFigeeError):
        acceptation.soft_delete(make_user())
    with pytest.raises(MissionFigeeError):
        AcceptationRisque.objects.filter(pk=acceptation.pk).update(deleted_at="2026-01-01Z")
    with pytest.raises(MissionFigeeError):
        EngagementFactory(mission=mission_en_communication)
    assert engagement.pk is not None
