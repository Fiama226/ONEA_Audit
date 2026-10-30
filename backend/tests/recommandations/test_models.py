import pytest
from django.db import IntegrityError, transaction

from apps.constats.models import Recommandation
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from apps.recommandations.models import (
    AcceptationRisque,
    Action,
    EngagementPlanActions,
    StatutAction,
)
from tests.factories import make_user
from tests.recommandations.factories import (
    AcceptationFactory,
    ActionFactory,
    EngagementFactory,
)

pytestmark = pytest.mark.django_db


def test_reference_action_unique_meme_supprimee(
    mission_en_communication: Mission, recommandations: list[Recommandation]
) -> None:
    action = ActionFactory(recommandation=recommandations[0])
    assert action.reference == "A-01"
    action.soft_delete(make_user())
    with pytest.raises(IntegrityError), transaction.atomic():
        ActionFactory(recommandation=recommandations[0], numero=1, reference="A-01")
    with pytest.raises(IntegrityError), transaction.atomic():
        ActionFactory(recommandation=recommandations[0], numero=2, reference="A-01")
    assert ActionFactory(recommandation=recommandations[0]).reference == "A-02"


def test_acceptation_unique_active(recommandations: list[Recommandation]) -> None:
    premiere = AcceptationFactory(recommandation=recommandations[0])
    with pytest.raises(IntegrityError), transaction.atomic():
        AcceptationFactory(recommandation=recommandations[0])
    premiere.soft_delete(make_user())
    assert AcceptationFactory(recommandation=recommandations[0]).pk != premiere.pk
    assert AcceptationRisque.all_objects.filter(recommandation=recommandations[0]).count() == 2


def test_acceptation_justification_non_vide(recommandations: list[Recommandation]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        AcceptationFactory(recommandation=recommandations[0], justification="")


def test_acceptation_immuable(recommandations: list[Recommandation]) -> None:
    acceptation = AcceptationFactory(recommandation=recommandations[0])
    acceptation.justification = "autre"
    with pytest.raises(RegleMetierError):
        acceptation.save()
    with pytest.raises(RegleMetierError):
        AcceptationRisque.objects.filter(pk=acceptation.pk).update(justification="x")
    acceptation.refresh_from_db()
    acceptation.soft_delete(make_user())
    assert AcceptationRisque.objects.filter(pk=acceptation.pk).count() == 0
    acceptation.deleted_at = None
    with pytest.raises(RegleMetierError):
        acceptation.save()


def test_engagement_ajout_seul(mission_en_communication: Mission) -> None:
    engagement = EngagementFactory(mission=mission_en_communication)
    engagement.empreinte_actions = "1" * 64
    with pytest.raises(RegleMetierError):
        engagement.save()
    with pytest.raises(RegleMetierError):
        engagement.soft_delete(make_user())
    with pytest.raises(RegleMetierError):
        EngagementPlanActions.objects.filter(pk=engagement.pk).update(empreinte_actions="2" * 64)
    with pytest.raises(RegleMetierError):
        EngagementPlanActions.objects.bulk_update([engagement], ["empreinte_actions"])
    assert EngagementPlanActions.objects.count() == 1


def test_action_statut_defaut(recommandations: list[Recommandation]) -> None:
    assert ActionFactory(recommandation=recommandations[0]).statut == StatutAction.A_LANCER
    assert Action.objects.count() == 1
