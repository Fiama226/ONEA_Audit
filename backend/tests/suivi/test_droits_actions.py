from apps.missions.models import Mission, RoleMission
from apps.suivi.droits import actions_possibles, contexte_suivi
from apps.suivi.models import SuiviAction
from apps.suivi.services import workflow
from apps.users.models import User
from tests.missions.conftest import affecter
from tests.suivi.factories import PreuveFactory


def _codes(suivi: SuiviAction, user: User) -> list[str]:
    ctx = contexte_suivi(user, [suivi.mission_id])
    return actions_possibles(suivi, user, contexte=ctx)


def test_actions_a_lancer(
    mission_en_suivi: Mission,
    rai: User,
    responsable: User,
    audite_affecte: User,
    auditeur_mission: User,
    dg: User,
    admin: User,
    autre_audite: User,
) -> None:
    s = SuiviAction.objects.filter(mission=mission_en_suivi).first()
    executant = [
        "DEMARRER",
        "DECLARER_REALISEE",
        "PROPOSER_ABANDON",
        "COMMENTER",
        "DEPOSER_PREUVE",
        "DEMANDER_REPORT",
    ]
    assert _codes(s, responsable) == executant
    assert _codes(s, rai) == [*executant[:3], "COMMENTER", "CHANGER_RESPONSABLE", *executant[4:]]
    assert _codes(s, audite_affecte) == ["COMMENTER"]
    assert _codes(s, auditeur_mission) == ["COMMENTER"]
    for user in (dg, admin, autre_audite):
        assert _codes(s, user) == []


def test_actions_a_verifier(
    mission_en_suivi: Mission, rai: User, responsable: User, auditeur_mission: User
) -> None:
    s = SuiviAction.objects.filter(mission=mission_en_suivi).first()
    PreuveFactory(suivi=s)
    workflow.declarer_realisee(s, commentaire="Fait.", by=responsable)
    s.refresh_from_db()
    assert _codes(s, auditeur_mission) == ["VERIFIER", "REJETER", "COMMENTER"]
    assert "VERIFIER" in _codes(s, rai)
    assert _codes(s, responsable) == ["COMMENTER"]


def test_declarant_rai_sans_verification(mission_en_suivi: Mission, rai: User) -> None:
    s = SuiviAction.objects.filter(mission=mission_en_suivi).first()
    PreuveFactory(suivi=s)
    workflow.declarer_realisee(s, commentaire="Pour compte.", by=rai)
    s.refresh_from_db()
    codes = _codes(s, rai)
    assert "VERIFIER" not in codes
    assert "REJETER" not in codes


def test_contexte_calcule_en_peu_de_requetes(
    mission_en_suivi: Mission, auditeur_mission: User, django_assert_max_num_queries: object
) -> None:
    suivis = list(SuiviAction.objects.filter(mission=mission_en_suivi))
    with django_assert_max_num_queries(3):  # type: ignore[operator]
        ctx = contexte_suivi(auditeur_mission, {s.mission_id for s in suivis})
        for s in suivis:
            actions_possibles(s, auditeur_mission, contexte=ctx)


def test_audite_non_affecte_au_chef(mission_en_suivi: Mission, autre_auditeur: User) -> None:
    affecter(mission_en_suivi, autre_auditeur, RoleMission.SUPERVISEUR)
    s = SuiviAction.objects.filter(mission=mission_en_suivi).first()
    assert _codes(s, autre_auditeur) == ["COMMENTER"]
