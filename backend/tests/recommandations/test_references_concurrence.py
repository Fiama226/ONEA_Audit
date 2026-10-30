from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection, transaction

from apps.constats.models import Recommandation
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.recommandations.models import Action
from apps.recommandations.services.actions import creer_action
from apps.users.models import User
from tests.constats.factories import ConstatFactory
from tests.missions.conftest import forcer_etapes


def _dans_un_thread(fonction, *args, **kwargs):  # type: ignore[no-untyped-def]
    try:
        return fonction(*args, **kwargs)
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_references_actions_concurrentes(mission_lancee: Mission, chef: User) -> None:
    forcer_etapes(mission_lancee, {14: StatutEtape.EN_COURS})
    with transaction.atomic():
        constat = ConstatFactory(mission=mission_lancee)
        constat.soumettre()
        constat.save()
        constat.valider()
        constat.save()
    forcer_etapes(
        mission_lancee,
        {14: StatutEtape.TERMINEE, 15: StatutEtape.EN_COURS, 16: StatutEtape.EN_COURS},
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    reco = Recommandation.objects.filter(mission=mission_lancee).first()
    assert reco is not None
    with ThreadPoolExecutor(8) as ex:
        list(
            ex.map(
                lambda i: _dans_un_thread(creer_action, reco, libelle=f"Mesure {i}", by=chef),
                range(8),
            )
        )
    references = Action.objects.values_list("reference", flat=True)
    assert sorted(references) == [f"A-{n:02d}" for n in range(1, 9)]
