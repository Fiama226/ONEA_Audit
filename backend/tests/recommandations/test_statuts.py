import pytest

from apps.recommandations.models import StatutAction as S
from apps.recommandations.services.statuts import (
    INCONNU,
    statut_depuis,
    statut_recommandation,
)
from tests.recommandations.factories import AcceptationFactory, ActionFactory


@pytest.mark.parametrize(
    ("statuts", "acceptee", "attendu"),
    [
        ([], True, "RISQUE_ACCEPTE"),
        ([S.EN_COURS], True, "RISQUE_ACCEPTE"),
        ([], False, "SANS_ACTION"),
        ([S.A_LANCER, S.A_LANCER], False, "A_LANCER"),
        ([S.A_LANCER, S.EN_COURS], False, "EN_COURS"),
        ([S.A_LANCER, S.REALISEE], False, "EN_COURS"),
        ([S.REALISEE, S.ABANDONNEE], False, "REALISEE"),
        ([S.REALISEE, S.REALISEE], False, "REALISEE"),
        ([S.ABANDONNEE, S.ABANDONNEE], False, "A_LANCER"),
    ],
)
def test_statut_recommandation_derive(statuts: list[str], acceptee: bool, attendu: str) -> None:
    assert statut_depuis(statuts, acceptee=acceptee) == attendu


@pytest.mark.django_db
def test_statut_depuis_la_base_et_prechargé(django_assert_num_queries) -> None:  # type: ignore[no-untyped-def]
    action = ActionFactory()
    reco = action.recommandation
    assert statut_recommandation(reco) == "A_LANCER"
    with django_assert_num_queries(0):
        assert statut_recommandation(reco, actions=[action], acceptation=None) == "A_LANCER"
        assert statut_recommandation(reco, actions=[], acceptation=None) == "SANS_ACTION"
    autre = AcceptationFactory()
    assert statut_recommandation(autre.recommandation) == "RISQUE_ACCEPTE"
    assert INCONNU is not None
