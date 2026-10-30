import pytest

from apps.constats.models import Recommandation
from apps.missions.models import Mission, StatutMission
from apps.recommandations.services.acceptations import accepter_risque
from apps.recommandations.services.actions import creer_action
from apps.recommandations.services.engagements import engager
from apps.recommandations.services.suivi import actions_a_suivre
from apps.recommandations.services.synthese import synthese_plan
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_synthese_requetes_bornees(
    django_assert_max_num_queries,  # type: ignore[no-untyped-def]
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    creer_action(
        recommandations[0], libelle="M", by=chef, responsable=audite_entite_a, indicateur="i"
    )
    creer_action(recommandations[1], libelle="N", by=chef)
    accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    engager(mission_en_communication, by=audite_entite_a)
    with django_assert_max_num_queries(5):
        synthese = synthese_plan(mission_en_communication)
    statuts = [(r.reference, r.statut_derive, r.nb_actions) for r in synthese.recommandations]
    assert [s[1] for s in statuts] == ["A_LANCER", "A_LANCER", "RISQUE_ACCEPTE"]
    assert synthese.recommandations_sans_suite == []
    assert synthese.actions_incompletes == ["A-01", "A-02"]
    assert [r.engagement for r in synthese.responsables] == ["CONFIRME"]
    assert synthese.engagements_manquants == []
    assert synthese.recommandations[2].acceptation is not None


def test_synthese_sans_suite_et_engagement_manquant(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    chef: User,
) -> None:
    creer_action(recommandations[0], libelle="M", by=chef, responsable=audite_entite_a)
    synthese = synthese_plan(mission_en_communication)
    assert len(synthese.recommandations_sans_suite) == 2
    assert synthese.engagements_manquants == [audite_entite_a.nom_complet]


def test_actions_a_suivre(
    mission_en_communication: Mission, recommandations: list[Recommandation], chef: User
) -> None:
    from apps.missions.models import Mission as M

    creer_action(recommandations[0], libelle="M", by=chef)
    assert not actions_a_suivre().exists()
    M.objects.filter(pk=mission_en_communication.pk).update(statut=StatutMission.RAPPORT_DIFFUSE)
    assert actions_a_suivre().count() == 1
    assert actions_a_suivre(mission_en_communication).count() == 1
