import pytest

from apps.analyse.models import CouvertureOrdre, EvaluationConception, MotifNonTest
from apps.analyse.services import objectifs, orientation
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, RisqueMission, StatutEtape
from apps.missions.services.etapes import terminer_etape
from apps.missions.services.livrables import livrables_manquants
from apps.users.models import User
from tests.factories import LigneMARCFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def etape_vii(mission: Mission) -> EtapeMission:
    return mission.etapes.get(numero=7)


def test_terminer_vii_livrables(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    LigneMARCFactory(
        mission=mission_en_analyse,
        risque=risque_eleve,
        cle=True,
        evaluation=EvaluationConception.ADEQUATE,
        controle_existant="Double validation",
    )
    forcer_etapes(mission_en_analyse, {5: StatutEtape.TERMINEE, 7: StatutEtape.EN_COURS})
    assert livrables_manquants(etape_vii(mission_en_analyse)) == [
        "Le référentiel d'audit n'est pas validé (jalon VI).",
        "Aucun objectif d'audit n'est retenu.",
        "Contrôles clés sans décision de test : 1.",
        "Le rapprochement avec l'ordre de mission n'est pas renseigné.",
    ]
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape_vii(mission_en_analyse), by=chef)
    assert exc.value.message == "Livrables manquants."
    assert len(exc.value.errors["livrables"]) == 4

    forcer_etapes(mission_en_analyse, {6: StatutEtape.VALIDEE})
    objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    orientation.enregistrer_rapport(
        mission_en_analyse, by=chef, couverture_ordre=CouvertureOrdre.EXACTE
    )
    assert livrables_manquants(etape_vii(mission_en_analyse)) == []
    etape = terminer_etape(etape_vii(mission_en_analyse), by=chef)
    assert etape.statut == StatutEtape.TERMINEE


def test_controles_vii_non_retenu_compte_comme_decision(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    for _ in range(2):
        LigneMARCFactory(mission=mission_en_analyse, risque=risque_eleve, cle=True)
    forcer_etapes(
        mission_en_analyse,
        {5: StatutEtape.TERMINEE, 6: StatutEtape.VALIDEE, 7: StatutEtape.EN_COURS},
    )
    for objectif in objectifs.initialiser_objectifs(mission_en_analyse, by=chef):
        objectifs.modifier_objectif(
            objectif,
            by=chef,
            retenu=False,
            motif_non_test=MotifNonTest.CONCEPTION_ADAPTEE,
            justification="Ok.",
        )
    orientation.enregistrer_rapport(
        mission_en_analyse, by=chef, couverture_ordre=CouvertureOrdre.EXACTE
    )
    # Décisions prises (non testés), mais aucun objectif retenu.
    assert livrables_manquants(etape_vii(mission_en_analyse)) == [
        "Aucun objectif d'audit n'est retenu."
    ]
