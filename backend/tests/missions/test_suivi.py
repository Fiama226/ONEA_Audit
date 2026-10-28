from datetime import date
from decimal import Decimal

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.etapes import demarrer_etape, planifier_etape
from apps.missions.services.suivi import fiche_de_suivi
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_ecart_positif_signifie_retard(mission_lancee: Mission, chef: User) -> None:
    e4 = mission_lancee.etapes.get(numero=4)
    EtapeMission.objects.filter(pk=e4.pk).update(
        statut="TERMINEE", date_fin_prevue=date(2026, 3, 10), date_fin_reelle=date(2026, 3, 13)
    )
    e3 = mission_lancee.etapes.get(numero=3)
    EtapeMission.objects.filter(pk=e3.pk).update(
        statut="EN_COURS", date_fin_prevue=date(2026, 3, 20)
    )
    fiche = fiche_de_suivi(mission_lancee, aujourd_hui=date(2026, 3, 18))
    ecarts = {ligne.numero: ligne.ecart_jours for ligne in fiche.lignes if ligne.numero in (3, 4)}
    assert ecarts == {4: 3, 3: -2}


def test_ecart_nul_sans_date_prevue_ou_etape_a_faire(mission_lancee: Mission) -> None:
    EtapeMission.objects.filter(mission=mission_lancee, numero=5).update(
        date_fin_prevue=date(2026, 3, 20)
    )
    EtapeMission.objects.filter(mission=mission_lancee, numero=6).update(statut="EN_COURS")
    fiche = fiche_de_suivi(mission_lancee, aujourd_hui=date(2026, 3, 25))
    par_numero = {ligne.numero: ligne for ligne in fiche.lignes}
    assert par_numero[5].ecart_jours is None  # A_FAIRE
    assert par_numero[6].ecart_jours is None  # pas de date prévue


def test_fiche_de_suivi_totaux_et_requetes(
    mission_lancee: Mission,
    chef: User,
    rai: User,
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(budget_jours=Decimal("30"))
    mission_lancee.refresh_from_db()
    planifier_etape(
        mission_lancee.etapes.get(numero=3), by=chef, charge_prevue_jours=Decimal("4.5")
    )
    planifier_etape(
        mission_lancee.etapes.get(numero=4),
        by=rai,
        charge_prevue_jours=Decimal("2"),
        charge_reelle_jours=Decimal("2.5"),
    )
    forcer_etapes(mission_lancee, {3: StatutEtape.A_FAIRE})
    demarrer_etape(mission_lancee.etapes.get(numero=3), by=rai)
    with django_assert_max_num_queries(3):
        fiche = fiche_de_suivi(mission_lancee)
    assert len(fiche.lignes) == 18
    assert fiche.budget_jours == Decimal("30")
    assert fiche.total_prevu == Decimal("6.5")
    assert fiche.total_reel == Decimal("2.5")
    assert [e.type for e in fiche.evenements] == ["DEMARREE"]
    ligne = fiche.lignes[0]
    assert (ligne.numero, ligne.romain, ligne.phase, ligne.jalon) == (
        1,
        "I",
        "PLANIFICATION",
        False,
    )
