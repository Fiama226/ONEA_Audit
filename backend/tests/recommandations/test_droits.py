import datetime

import pytest

from apps.constats.models import Recommandation
from apps.missions.models import Mission, StatutEtape
from apps.recommandations import droits
from apps.recommandations.services.acceptations import accepter_risque
from apps.recommandations.services.actions import creer_action
from apps.recommandations.services.engagements import engager
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_actions_visibles_par_role(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    a = creer_action(recommandations[0], libelle="M", by=chef)
    b = creer_action(recommandations[2], libelle="N", by=chef)
    voit = lambda u: set(  # noqa: E731
        droits.actions_visibles(u, mission_en_communication).values_list("pk", flat=True)
    )
    assert voit(chef) == {a.pk, b.pk}
    assert voit(make_user(Role.RAI)) == {a.pk, b.pk}
    assert voit(audite_entite_a) == {a.pk}
    assert voit(audite_entite_b) == {b.pk}
    assert voit(make_user(Role.AUDITE)) == set()
    assert voit(make_user(Role.DG)) == set()
    assert voit(make_user(Role.ADMIN)) == set()
    assert voit(make_user(Role.AUDITEUR)) == set()


def test_actions_droits_equipe_et_audite(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    mission = mission_en_communication
    reco_a, reco_b = recommandations[0], recommandations[2]
    action = creer_action(reco_a, libelle="M", by=audite_entite_a)
    ctx = lambda u: droits.contexte_plan(mission, u)  # noqa: E731
    assert droits.actions_action(action, chef, contexte=ctx(chef)) == ["MODIFIER", "SUPPRIMER"]
    assert droits.actions_action(action, audite_entite_a, contexte=ctx(audite_entite_a)) == [
        "MODIFIER",
        "SUPPRIMER",
    ]
    assert droits.actions_action(action, audite_entite_b, contexte=ctx(audite_entite_b)) == []
    assert droits.actions_recommandation(reco_a, chef, contexte=ctx(chef)) == ["AJOUTER_ACTION"]
    assert droits.actions_recommandation(
        reco_b, audite_entite_b, contexte=ctx(audite_entite_b)
    ) == ["AJOUTER_ACTION", "ACCEPTER_RISQUE"]
    assert droits.actions_recommandation(
        reco_a, audite_entite_a, contexte=ctx(audite_entite_a)
    ) == ["AJOUTER_ACTION"]
    accepter_risque(reco_b, justification="x", by=audite_entite_b)
    assert droits.actions_recommandation(reco_b, chef, contexte=ctx(chef)) == []
    assert droits.actions_recommandation(
        reco_b, audite_entite_b, contexte=ctx(audite_entite_b)
    ) == ["RETIRER_ACCEPTATION"]
    rai = make_user(Role.RAI)
    assert droits.actions_recommandation(reco_b, rai, contexte=ctx(rai)) == ["RETIRER_ACCEPTATION"]


def test_droits_vides_hors_fenetre(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    chef: User,
) -> None:
    action = creer_action(recommandations[0], libelle="M", by=chef)
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    ctx = droits.contexte_plan(mission_en_communication, chef)
    assert droits.actions_action(action, chef, contexte=ctx) == []
    assert droits.actions_recommandation(recommandations[0], chef, contexte=ctx) == []


def test_peut_engager(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    assert not droits.peut_engager(audite_entite_a, mission_en_communication)
    creer_action(
        recommandations[0],
        libelle="M",
        by=chef,
        responsable=audite_entite_a,
        echeance=datetime.date.today() + datetime.timedelta(days=5),
    )
    assert droits.peut_engager(audite_entite_a, mission_en_communication)
    assert not droits.peut_engager(audite_entite_b, mission_en_communication)
    assert not droits.peut_engager(chef, mission_en_communication)
    engager(mission_en_communication, by=audite_entite_a)
