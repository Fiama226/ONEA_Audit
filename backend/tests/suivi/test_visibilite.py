from apps.missions.models import Mission, StatutMission
from apps.suivi.droits import missions_suivi_visibles, suivis_visibles
from apps.users.models import User


def test_visibilite_par_role(
    mission_en_suivi: Mission,
    rai: User,
    auditeur_mission: User,
    responsable: User,
    dg: User,
    admin: User,
    autre_auditeur: User,
    autre_audite: User,
) -> None:
    assert suivis_visibles(rai).count() == 3
    assert suivis_visibles(auditeur_mission).count() == 3
    assert suivis_visibles(responsable).count() == 3  # lit tout le plan de sa mission
    assert suivis_visibles(dg).count() == 3
    assert suivis_visibles(admin).count() == 0
    assert suivis_visibles(autre_auditeur).count() == 0
    assert suivis_visibles(autre_audite).count() == 0


def test_mission_non_diffusee_invisible_au_dg(
    mission_en_suivi: Mission, rai: User, dg: User, auditeur_mission: User
) -> None:
    Mission.objects.filter(pk=mission_en_suivi.pk).update(statut=StatutMission.EN_COMMUNICATION)
    for user in (rai, dg, auditeur_mission):
        assert not missions_suivi_visibles(user).exists()
        assert suivis_visibles(user).count() == 0


def test_statuts_de_suivi_visibles(mission_en_suivi: Mission, dg: User) -> None:
    for statut in (StatutMission.EN_SUIVI, StatutMission.CLOTUREE):
        Mission.objects.filter(pk=mission_en_suivi.pk).update(statut=statut)
        assert suivis_visibles(dg).count() == 3
