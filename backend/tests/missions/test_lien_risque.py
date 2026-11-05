"""Règle de gouvernance « lien programme ↔ risque » à la création d'une mission (Normes IIA 9.4)."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.gouvernance import regles_gouvernance as rg
from apps.missions.models import EvenementDeclencheur, Mission
from apps.missions.services.missions import creer_mission, modifier_mission
from apps.referentiel.models import CartographieVersion, Risque, StatutCartographie
from apps.users.models import User
from tests.factories import CartographieVersionFactory, RisqueFactory
from tests.regles import regler

pytestmark = pytest.mark.django_db

PROGRAMME = EvenementDeclencheur.PROGRAMME_ANNUEL


@pytest.fixture
def risque(rai: User) -> Risque:
    """Risque d'une cartographie validée, la plus récente (référence des nouvelles missions)."""
    version = CartographieVersionFactory(annee=2099)
    risque = RisqueFactory(version=version)
    CartographieVersion._base_manager.filter(pk=version.pk).update(  # noqa: SLF001
        statut=StatutCartographie.VALIDEE, validee_le=timezone.now(), validee_par=rai
    )
    return risque


@pytest.fixture
def risque_ancien(rai: User, risque: Risque) -> Risque:
    version = CartographieVersionFactory(annee=2098)
    ancien = RisqueFactory(version=version)
    CartographieVersion._base_manager.filter(pk=version.pk).update(  # noqa: SLF001
        statut=StatutCartographie.VALIDEE, validee_le=timezone.now(), validee_par=rai
    )
    return ancien


def test_programme_mission_without_risk_is_refused(rai: User, risque: Risque) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_mission(titre="Audit", type="ASSURANCE", by=rai, evenement_declencheur=PROGRAMME)
    assert "risques_couverts" in exc.value.errors
    assert not Mission.objects.exists()


def test_programme_mission_names_the_risks_it_covers(rai: User, risque: Risque) -> None:
    mission = creer_mission(
        titre="Audit",
        type="ASSURANCE",
        by=rai,
        evenement_declencheur=PROGRAMME,
        risques_couverts=[risque],
    )
    assert list(mission.risques_couverts.all()) == [risque]


def test_risk_of_another_map_is_refused(rai: User, risque_ancien: Risque) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_mission(
            titre="Audit",
            type="ASSURANCE",
            by=rai,
            evenement_declencheur=PROGRAMME,
            risques_couverts=[risque_ancien],
        )
    assert "risques_couverts" in exc.value.errors


def test_other_missions_need_no_risk(rai: User, risque: Risque) -> None:
    mission = creer_mission(
        titre="Audit",
        type="ASSURANCE",
        by=rai,
        evenement_declencheur=EvenementDeclencheur.DEMANDE_MANAGEMENT,
    )
    assert mission.risques_couverts.count() == 0


def test_optional_rule_lets_a_programme_mission_without_risk(rai: User, risque: Risque) -> None:
    regler(rg.PROGRAM_RISK_LINK, required=False)
    mission = creer_mission(
        titre="Audit", type="ASSURANCE", by=rai, evenement_declencheur=PROGRAMME
    )
    assert mission.risques_couverts.count() == 0


def test_rule_is_not_retroactive_on_existing_missions(rai: User, risque: Risque) -> None:
    regler(rg.PROGRAM_RISK_LINK, required=False)
    mission = creer_mission(
        titre="Audit", type="ASSURANCE", by=rai, evenement_declencheur=PROGRAMME
    )
    regler(rg.PROGRAM_RISK_LINK, required=True)
    modifier_mission(mission, by=rai, titre="Audit modifié")
    assert Mission.objects.get(pk=mission.pk).titre == "Audit modifié"


def test_covered_risks_through_the_api(api_client: APIClient, rai: User, risque: Risque) -> None:
    api_client.force_authenticate(rai)
    corps = {"titre": "Audit", "type": "ASSURANCE", "evenement_declencheur": PROGRAMME}
    reponse = api_client.post("/api/v1/missions/", corps, format="json")
    assert reponse.status_code == 422
    assert "risques_couverts" in reponse.json()["errors"]
    reponse = api_client.post(
        "/api/v1/missions/", {**corps, "risques_couverts": [str(risque.pk)]}, format="json"
    )
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["risques_couverts_detail"] == [
        {"id": str(risque.pk), "code": risque.code, "libelle": risque.libelle, "niveau": "MOYEN"}
    ]
