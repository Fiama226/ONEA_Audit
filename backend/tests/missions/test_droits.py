import dataclasses

import pytest

from apps.missions.models import Mission, RoleMission, StatutEtape, StatutMission
from apps.missions.services.droits import DroitsMission, droits_mission
from apps.users.models import Role, User
from tests.factories import make_user

from .conftest import affecter

TOUS = [f.name for f in dataclasses.fields(DroitsMission)]


def vrais(d: DroitsMission) -> set[str]:
    return {n for n in TOUS if getattr(d, n)}


def en(mission: Mission, statut: str) -> Mission:
    Mission.objects.filter(pk=mission.pk).update(statut=statut)
    mission.refresh_from_db()
    return mission


@pytest.mark.parametrize(
    ("statut", "attendu"),
    [
        (
            StatutMission.BROUILLON,
            {"modifier", "planifier", "supprimer", "affecter", "voir_travaux"},
        ),
        (
            StatutMission.PLANIFIEE,
            {
                "modifier",
                "lancer",
                "suspendre",
                "annuler",
                "affecter",
                "contribuer",
                "voir_travaux",
            },
        ),
        (
            StatutMission.EN_COMMUNICATION,
            {"modifier", "suspendre", "annuler", "affecter", "contribuer", "voir_travaux"},
        ),
        (StatutMission.SUSPENDUE, {"reprendre", "annuler"}),
        (StatutMission.ANNULEE, set()),
        (StatutMission.CLOTUREE, set()),
    ],
)
def test_droits_rai_par_etat(mission_lancee: Mission, rai: User, statut: str, attendu: set[str]):
    assert vrais(droits_mission(rai, en(mission_lancee, statut))) == attendu


def test_droits_rai_emettre_ordre_selon_etape_I(mission_lancee: Mission, rai: User):
    assert "emettre_ordre" in vrais(droits_mission(rai, mission_lancee))
    mission_lancee.etapes.filter(numero=1).update(statut=StatutEtape.TERMINEE)
    assert "emettre_ordre" not in vrais(droits_mission(rai, mission_lancee))


def test_droits_auditeur_non_confirme_puis_confirme(mission_lancee: Mission):
    u = make_user(Role.AUDITEUR)
    affecter(mission_lancee, u, RoleMission.AUDITEUR, confirmee=False)
    d = droits_mission(u, mission_lancee)
    assert not d.contribuer and d.confirmer_ma_declaration and d.voir_travaux
    assert vrais(d) == {"voir_travaux", "confirmer_ma_declaration"}
    v = make_user(Role.AUDITEUR)
    affecter(mission_lancee, v, RoleMission.AUDITEUR, confirmee=True)
    assert vrais(droits_mission(v, mission_lancee)) == {"contribuer", "voir_travaux"}


def test_droits_auditeur_mission_figee(mission_lancee: Mission, chef: User):
    assert droits_mission(chef, mission_lancee).contribuer
    assert vrais(droits_mission(chef, en(mission_lancee, StatutMission.SUSPENDUE))) == set()


@pytest.mark.parametrize("role", [Role.ADMIN, Role.DG, Role.AUDITE])
def test_droits_autres_roles_aucun(mission_lancee: Mission, role: str):
    assert vrais(droits_mission(make_user(role), mission_lancee)) == set()


def test_droits_audite_affecte_aucun(mission_lancee: Mission, audite_affecte: User):
    assert vrais(droits_mission(audite_affecte, mission_lancee)) == set()


def test_droits_auditeur_non_affecte_aucun(mission_lancee: Mission):
    assert vrais(droits_mission(make_user(Role.AUDITEUR), mission_lancee)) == set()
