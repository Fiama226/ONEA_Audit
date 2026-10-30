import datetime

import pytest

from apps.constats.models import Recommandation
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape
from apps.missions.services.etapes import terminer_etape
from apps.recommandations.services.acceptations import accepter_risque
from apps.recommandations.services.actions import creer_action
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _livrables(mission: Mission, chef: User) -> list[str]:
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(mission.etapes.get(numero=16), by=chef)
    return list(exc.value.errors["livrables"])


def test_terminer_xvi_exige_xv_close(mission_en_communication: Mission, chef: User) -> None:
    assert any("Terminez l'étape XV" in m for m in _livrables(mission_en_communication, chef))


def test_terminer_xvi_exige_action_ou_acceptation(
    mission_en_communication: Mission, chef: User
) -> None:
    forcer_etapes(mission_en_communication, {15: StatutEtape.TERMINEE})
    manquants = _livrables(mission_en_communication, chef)
    assert len([m for m in manquants if "ni action ni acceptation" in m]) == 3
    assert any(m.startswith("La recommandation C-01-1 ") for m in manquants)


def test_terminer_xvi_action_incomplete_puis_complete(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    forcer_etapes(mission_en_communication, {15: StatutEtape.TERMINEE})
    creer_action(recommandations[0], libelle="M", by=chef)
    creer_action(
        recommandations[1], libelle="N", by=chef, responsable=audite_entite_a, indicateur="i"
    )
    accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    manquants = _livrables(mission_en_communication, chef)
    assert manquants == [
        "L'action A-01 n'a pas de responsable, d'échéance ou d'indicateur.",
        "L'action A-02 n'a pas de responsable, d'échéance ou d'indicateur.",
    ]


def test_terminer_xvi_passe_quand_le_plan_est_complet(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    forcer_etapes(mission_en_communication, {15: StatutEtape.TERMINEE})
    for reco in recommandations[:2]:
        creer_action(
            reco,
            libelle="M",
            by=chef,
            responsable=audite_entite_a,
            indicateur="i",
            echeance=datetime.date.today() + datetime.timedelta(days=10),
        )
    accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    etape = terminer_etape(mission_en_communication.etapes.get(numero=16), by=chef)
    assert etape.statut == StatutEtape.TERMINEE
