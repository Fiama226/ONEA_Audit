import pytest

from apps.accomplissement.models import FicheDeTest, StatutTest, TestPrevu
from apps.accomplissement.services.fiches import valider_fiche
from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.livrables import livrables_manquants
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import ouvrir_xiii

pytestmark = pytest.mark.django_db


def _manquants(mission: Mission, numero: int) -> list[str]:
    return livrables_manquants(EtapeMission.objects.get(mission=mission, numero=numero))


def test_terminer_xii_tests_sans_fiche_ou_non_soumise(
    mission_en_accomplissement: Mission, fiche_auditeur: FicheDeTest
) -> None:
    manquants = _manquants(mission_en_accomplissement, 12)
    assert len(manquants) == 1
    assert "2" in manquants[0]  # un test brouillon + un test sans fiche


def test_xii_complete_quand_toutes_les_fiches_sont_soumises(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest
) -> None:
    autre = mission_en_accomplissement.tests_prevus.exclude(pk=fiche_soumise.test_id).get()
    TestPrevu.objects.filter(pk=autre.pk).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Sans objet"
    )
    assert _manquants(mission_en_accomplissement, 12) == []


def test_test_abandonne_hors_controle(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest
) -> None:
    avant = _manquants(mission_en_accomplissement, 12)
    assert avant
    TestPrevu.objects.filter(mission=mission_en_accomplissement).exclude(
        pk=fiche_soumise.test_id
    ).update(statut=StatutTest.ABANDONNE, motif_abandon="Sans objet")
    assert _manquants(mission_en_accomplissement, 12) == []
    assert _manquants(mission_en_accomplissement, 13)  # la fiche soumise n'est pas validée


def test_terminer_xiii_fiches_non_validees(
    mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest, rai: User
) -> None:
    TestPrevu.objects.filter(mission=mission_en_accomplissement).exclude(
        pk=fiche_soumise.test_id
    ).update(statut=StatutTest.ABANDONNE, motif_abandon="Sans objet")
    manquants = _manquants(mission_en_accomplissement, 13)
    assert len(manquants) == 1
    assert "validée" in manquants[0]
    ouvrir_xiii(mission_en_accomplissement)
    valider_fiche(fiche_soumise, by=rai)
    assert _manquants(mission_en_accomplissement, 13) == []
    assert StatutEtape.EN_COURS  # fenêtre XIII toujours ouverte
