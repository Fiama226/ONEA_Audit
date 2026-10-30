import pytest
from django.utils import timezone

from apps.communication.models import Rapport, StatutRapport
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.notifications.models import Notification
from apps.recommandations.models import Action
from apps.suivi.models import EvenementSuivi, StatutSuivi, SuiviAction, TypeEvenementSuivi
from apps.suivi.recepteurs import sur_rapport_diffuse
from apps.suivi.services import ouverture
from apps.users.models import User
from tests.communication.factories import RapportFactory, creer_diffusion
from tests.constats.factories import ConstatFactory
from tests.missions.conftest import forcer_etapes
from tests.recommandations.factories import ActionFactory


@pytest.fixture
def mission_diffusee(mission_lancee: Mission, responsable: User) -> Mission:
    """Rapport diffusé, trois actions de plan mais aucun suivi ouvert."""
    mission = mission_lancee
    reco_a = ConstatFactory(mission=mission).recommandations.first()
    reco_b = ConstatFactory(mission=mission).recommandations.first()
    for reco in (reco_a, reco_a, reco_b):
        ActionFactory(recommandation=reco, responsable=responsable)
    rapport: Rapport = RapportFactory(mission=mission, fige=True, statut=StatutRapport.DIFFUSE)
    creer_diffusion(rapport)
    forcer_etapes(mission, {n: StatutEtape.VALIDEE for n in range(1, 19)})
    Mission.objects.filter(pk=mission.pk).update(
        statut=StatutMission.RAPPORT_DIFFUSE, ordre_mission_emis_le=timezone.now()
    )
    mission.refresh_from_db()
    return mission


def test_initialiser_suivi_idempotent(mission_diffusee: Mission, responsable: User) -> None:
    premiers = ouverture.initialiser_suivi(mission_diffusee)
    secondes = ouverture.initialiser_suivi(mission_diffusee)
    assert len(premiers) == len(secondes) == 3
    assert {s.pk for s in premiers} == {s.pk for s in secondes}
    assert SuiviAction.objects.filter(mission=mission_diffusee).count() == 3
    for suivi in premiers:
        ouverts = EvenementSuivi.objects.filter(suivi=suivi, type=TypeEvenementSuivi.OUVERT)
        assert ouverts.count() == 1
        assert suivi.statut == StatutSuivi.A_LANCER
        assert suivi.echeance == suivi.echeance_initiale == suivi.action.echeance
        assert suivi.entite == suivi.recommandation.constat.entite
    mission_diffusee.refresh_from_db()
    assert mission_diffusee.statut == StatutMission.EN_SUIVI
    assert Notification.objects.filter(destinataire=responsable, type="SUIVI_OUVERT").count() == 3


def test_action_sans_responsable_ignoree_et_signalee(mission_diffusee: Mission, rai: User) -> None:
    forcer_etapes(mission_diffusee, {16: StatutEtape.EN_COURS})
    sans = ActionFactory(recommandation=Action.objects.first().recommandation, responsable=None)
    suivis = ouverture.initialiser_suivi(mission_diffusee)
    assert len(suivis) == 3
    assert not SuiviAction.all_objects.filter(action=sans).exists()
    assert Notification.objects.filter(destinataire=rai, type="ACTION_IGNOREE").count() == 1
    ouverture.initialiser_suivi(mission_diffusee)
    assert Notification.objects.filter(destinataire=rai, type="ACTION_IGNOREE").count() == 1


def test_mission_sans_action_reste_diffusee(mission_lancee: Mission) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.RAPPORT_DIFFUSE)
    assert ouverture.initialiser_suivi(mission_lancee) == []
    mission_lancee.refresh_from_db()
    assert mission_lancee.statut == StatutMission.RAPPORT_DIFFUSE


def test_mission_non_diffusee_sans_effet(mission_diffusee: Mission) -> None:
    Mission.objects.filter(pk=mission_diffusee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    assert ouverture.initialiser_suivi(mission_diffusee) == []
    assert not SuiviAction.objects.exists()


def test_reconcilier_rattrape_sans_signal(mission_diffusee: Mission) -> None:
    assert ouverture.reconcilier() == 3
    assert ouverture.reconcilier() == 0
    assert SuiviAction.objects.filter(mission=mission_diffusee).count() == 3
    forcer_etapes(mission_diffusee, {16: StatutEtape.EN_COURS})
    ActionFactory(recommandation=Action.objects.first().recommandation)
    assert ouverture.reconcilier() == 1


def test_recepteur_du_signal(mission_diffusee: Mission) -> None:
    rapport = mission_diffusee.rapports.first()
    sur_rapport_diffuse(Rapport, rapport=rapport, diffusion=None, par=None)
    assert SuiviAction.objects.filter(mission=mission_diffusee).count() == 3


def test_recepteur_branche_sur_le_signal(mission_diffusee: Mission) -> None:
    from apps.communication.signals import rapport_diffuse

    rapport = mission_diffusee.rapports.first()
    rapport_diffuse.send(Rapport, rapport=rapport, diffusion=None, par=None)
    assert SuiviAction.objects.filter(mission=mission_diffusee).count() == 3


def test_recepteur_avale_les_erreurs(db: None) -> None:
    class Faux:
        mission_id = "x"

        @property
        def mission(self) -> object:
            raise RuntimeError("boom")

    sur_rapport_diffuse(Rapport, rapport=Faux(), par=None)
