import pytest

from apps.accomplissement.models import FicheDeTest, StatutTest, TestPrevu
from apps.accomplissement.services.fiches import valider_fiche
from apps.missions.models import EtapeMission, Mission
from apps.missions.services.livrables import livrables_manquants
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import ouvrir_xiii

pytestmark = pytest.mark.django_db


def _manquants(mission: Mission, numero: int) -> list[str]:
    return livrables_manquants(EtapeMission.objects.get(mission=mission, numero=numero))


def _abandonner_les_autres(mission: Mission, garde: FicheDeTest) -> None:
    TestPrevu.objects.filter(mission=mission).exclude(pk=garde.test_id).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Sans objet"
    )


def test_xii_tests_sans_fiche(mission_en_accomplissement: Mission) -> None:
    assert _manquants(mission_en_accomplissement, 12) == [
        "Le test T-01 n'a pas de fiche. Le test T-02 n'a pas de fiche."
    ]


def test_xii_distingue_sans_fiche_et_non_soumise(
    mission_en_accomplissement: Mission, fiche_auditeur: FicheDeTest
) -> None:
    assert _manquants(mission_en_accomplissement, 12) == [
        "La fiche du test T-01 n'est pas soumise. Le test T-02 n'a pas de fiche."
    ]


def test_xii_fiche_renvoyee_est_non_soumise(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest
) -> None:
    FicheDeTest.objects.filter(pk=fiche_soumise.pk).update(statut="RENVOYE")
    assert _manquants(mission_en_accomplissement, 12) == [
        "La fiche du test T-01 n'est pas soumise. Le test T-02 n'a pas de fiche."
    ]


def test_xii_complete_quand_toutes_les_fiches_sont_soumises(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest
) -> None:
    _abandonner_les_autres(mission_en_accomplissement, fiche_soumise)
    assert _manquants(mission_en_accomplissement, 12) == []


def test_test_abandonne_hors_controle(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest
) -> None:
    assert _manquants(mission_en_accomplissement, 12) == ["Le test T-02 n'a pas de fiche."]
    _abandonner_les_autres(mission_en_accomplissement, fiche_soumise)
    assert _manquants(mission_en_accomplissement, 12) == []
    assert _manquants(mission_en_accomplissement, 13) == [
        "La fiche du test T-01 n'est pas validée."
    ]


def test_terminer_xiii_fiches_non_validees(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest, rai: User
) -> None:
    _abandonner_les_autres(mission_en_accomplissement, fiche_soumise)
    assert _manquants(mission_en_accomplissement, 13) == [
        "La fiche du test T-01 n'est pas validée."
    ]
    ouvrir_xiii(mission_en_accomplissement)
    valider_fiche(fiche_soumise, by=rai)
    assert _manquants(mission_en_accomplissement, 13) == []
