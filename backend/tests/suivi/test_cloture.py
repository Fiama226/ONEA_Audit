import pytest

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import Mission, StatutMission
from apps.notifications.models import Notification
from apps.suivi.models import StatutSuivi, SuiviAction
from apps.suivi.services import cloture, workflow
from apps.users.models import User
from tests.suivi.factories import PreuveFactory


def _clore_tout(mission: Mission, rai: User, responsable: User, auditeur: User) -> None:
    for suivi in list(SuiviAction.objects.filter(mission=mission)):
        PreuveFactory(suivi=suivi)
        workflow.declarer_realisee(suivi, commentaire="Fait.", by=responsable)
        workflow.verifier(suivi, by=auditeur)
        workflow.cloturer(suivi, by=rai)


def test_cloture_mission_refusee_si_action_ouverte(mission_en_suivi: Mission, rai: User) -> None:
    with pytest.raises(RegleMetierError, match=r"3 action\(s\) du plan ne sont pas closes\."):
        cloture.cloturer_mission(mission_en_suivi, by=rai)
    assert not cloture.missions_a_cloturer().exists()


def test_cloture_mission_reservee_au_rai(mission_en_suivi: Mission, chef: User) -> None:
    from django.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        cloture.cloturer_mission(mission_en_suivi, by=chef)


def test_mission_a_cloturer_notifiee_une_fois(
    mission_en_suivi: Mission, rai: User, responsable: User, auditeur_mission: User
) -> None:
    _clore_tout(mission_en_suivi, rai, responsable, auditeur_mission)
    notifs = Notification.objects.filter(type="MISSION_A_CLOTURER")
    assert notifs.filter(destinataire=rai).count() == 1
    assert list(cloture.missions_a_cloturer()) == [mission_en_suivi]
    mission_en_suivi.refresh_from_db()
    cloture.proposer_cloture_si_complete(mission_en_suivi)
    assert notifs.filter(destinataire=rai).count() == 1


def test_mission_a_cloturer_apres_abandon_de_la_derniere(
    mission_en_suivi: Mission, rai: User, responsable: User, auditeur_mission: User
) -> None:
    *autres, derniere = SuiviAction.objects.filter(mission=mission_en_suivi)
    for suivi in autres:
        PreuveFactory(suivi=suivi)
        workflow.declarer_realisee(suivi, commentaire="Fait.", by=responsable)
        workflow.verifier(suivi, by=auditeur_mission)
        workflow.cloturer(suivi, by=rai)
    assert not Notification.objects.filter(type="MISSION_A_CLOTURER").exists()
    workflow.proposer_abandon(derniere, justification="Obsolète.", by=responsable)
    workflow.accepter_abandon(derniere, commentaire="Oui.", by=rai)
    assert Notification.objects.filter(type="MISSION_A_CLOTURER", destinataire=rai).count() == 1


def test_cloture_mission_gele_tout(
    mission_en_suivi: Mission, rai: User, responsable: User, auditeur_mission: User
) -> None:
    _clore_tout(mission_en_suivi, rai, responsable, auditeur_mission)
    mission = cloture.cloturer_mission(mission_en_suivi, by=rai)
    assert mission.statut == StatutMission.CLOTUREE
    suivi = SuiviAction.objects.filter(mission=mission).first()
    assert suivi.statut == StatutSuivi.CLOTUREE
    with pytest.raises(MissionFigeeError):
        workflow.rouvrir(suivi, motif="Reprise.", by=rai)
    with pytest.raises(MissionFigeeError):
        workflow.commenter(suivi, texte="Encore.", by=rai)
    with pytest.raises(MissionFigeeError):
        suivi.save(update_fields=["derniere_activite_le"])
    with pytest.raises(RegleMetierError):
        cloture.cloturer_mission(mission, by=rai)


def test_mission_sans_action_cloturable(mission_lancee: Mission, rai: User) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.RAPPORT_DIFFUSE)
    assert list(cloture.missions_a_cloturer()) == [mission_lancee]
    assert cloture.cloturer_mission(mission_lancee, by=rai).statut == StatutMission.CLOTUREE


def test_cloture_refusee_si_action_du_plan_sans_suivi(
    mission_en_suivi: Mission, rai: User, responsable: User, auditeur_mission: User
) -> None:
    from apps.missions.models import StatutEtape
    from tests.missions.conftest import forcer_etapes
    from tests.recommandations.factories import ActionFactory

    _clore_tout(mission_en_suivi, rai, responsable, auditeur_mission)
    forcer_etapes(mission_en_suivi, {16: StatutEtape.EN_COURS})
    ActionFactory(
        recommandation=SuiviAction.objects.first().recommandation, responsable=responsable
    )
    with pytest.raises(RegleMetierError, match=r"1 action\(s\)"):
        cloture.cloturer_mission(mission_en_suivi, by=rai)
