from decimal import Decimal
from typing import Any

import pytest

from apps.accomplissement.models import StatutTest, TestPrevu
from apps.accomplissement.services.synthese import synthese_programme
from apps.missions.models import Mission, StatutEtape
from apps.users.models import User
from tests.accomplissement.factories import TestPrevuFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_synthese_par_objectif_et_par_auditeur(
    mission_programme_complet: Mission, chef: User, auditeur_mission: User
) -> None:
    m = mission_programme_complet
    programme = m.programmes.order_by("objectif__numero").first()
    forcer_etapes(m, {8: StatutEtape.EN_COURS})
    TestPrevuFactory(mission=m, programme=programme, auditeur=chef, charge_prevue_jours=2)
    TestPrevuFactory(mission=m, programme=programme, auditeur=None, charge_prevue_jours=1)
    abandonne = TestPrevuFactory(mission=m, programme=programme, charge_prevue_jours=9)
    TestPrevu.objects.filter(pk=abandonne.pk).update(statut=StatutTest.ABANDONNE, motif_abandon="x")
    s = synthese_programme(m)
    assert [(o.code, o.nb_tests, o.charge) for o in s.objectifs] == [
        ("OA-01", 3, Decimal("6")),
        ("OA-02", 1, Decimal("3")),
    ]
    par_user = {a.utilisateur.pk: (a.nb_tests, a.charge) for a in s.auditeurs}
    assert par_user[chef.pk] == (2, Decimal("5"))
    assert par_user[auditeur_mission.pk] == (1, Decimal("3"))
    assert s.total_charge == Decimal("9")
    assert s.tests_sans_auditeur == ["T-04"]
    assert s.depassement_budget == (s.total_charge > s.budget_jours)


def test_synthese_requetes_bornees(
    mission_programme_complet: Mission, django_assert_max_num_queries: Any
) -> None:
    with django_assert_max_num_queries(4):
        synthese_programme(mission_programme_complet)
