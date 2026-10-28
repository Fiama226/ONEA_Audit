from typing import Any

import pytest

from apps.missions import acces
from apps.missions.models import Mission, RoleMission, StatutMission
from apps.users.models import Role, User
from tests.factories import MissionFactory, make_user
from tests.missions.conftest import affecter

pytestmark = pytest.mark.django_db


def test_roles_dans_la_mission(
    mission_lancee: Mission, chef: User, auditeur_mission: User, audite_affecte: User
) -> None:
    assert acces.role_dans_mission(chef, mission_lancee) == RoleMission.CHEF_MISSION
    assert acces.role_dans_mission(auditeur_mission, mission_lancee) == RoleMission.AUDITEUR
    assert acces.role_dans_mission(audite_affecte, mission_lancee) == RoleMission.AUDITE
    assert acces.role_dans_mission(make_user(), mission_lancee) is None
    assert acces.est_chef(chef, mission_lancee)
    assert not acces.est_chef(auditeur_mission, mission_lancee)
    assert acces.est_intervenant(chef, mission_lancee)
    assert acces.est_intervenant(auditeur_mission, mission_lancee)
    assert not acces.est_intervenant(audite_affecte, mission_lancee)
    assert not acces.est_superviseur(chef, mission_lancee)


def test_superviseur(mission_lancee: Mission) -> None:
    sup = make_user(Role.AUDITEUR)
    affecter(mission_lancee, sup, RoleMission.SUPERVISEUR)
    assert acces.est_superviseur(sup, mission_lancee)
    assert acces.est_intervenant(sup, mission_lancee)


def test_peut_contribuer_exige_declaration_levee(mission_lancee: Mission, rai: User) -> None:
    confirme = make_user(Role.AUDITEUR)
    en_attente = make_user(Role.AUDITEUR)
    affecter(mission_lancee, confirme, RoleMission.AUDITEUR)
    affecter(mission_lancee, en_attente, RoleMission.AUDITEUR, confirmee=False)
    assert acces.declaration_levee(confirme, mission_lancee)
    assert not acces.declaration_levee(en_attente, mission_lancee)
    assert acces.peut_contribuer(confirme, mission_lancee)
    assert not acces.peut_contribuer(en_attente, mission_lancee)
    assert acces.peut_contribuer(rai, mission_lancee)
    assert not acces.peut_contribuer(make_user(Role.AUDITEUR), mission_lancee)


def test_audite_ne_contribue_pas(mission_lancee: Mission, audite_affecte: User) -> None:
    assert not acces.peut_contribuer(audite_affecte, mission_lancee)
    assert not acces.declaration_levee(audite_affecte, mission_lancee)


def test_peut_valider_jalon(mission_lancee: Mission, rai: User) -> None:
    sup = make_user(Role.AUDITEUR)
    affecter(mission_lancee, sup, RoleMission.SUPERVISEUR)
    aud = make_user(Role.AUDITEUR)
    affecter(mission_lancee, aud, RoleMission.AUDITEUR)
    for n in (6, 10, 13, 18):
        assert acces.peut_valider_jalon(rai, mission_lancee, n)
        assert not acces.peut_valider_jalon(aud, mission_lancee, n)
    for n in (6, 10, 13):
        assert acces.peut_valider_jalon(sup, mission_lancee, n)
    assert not acces.peut_valider_jalon(sup, mission_lancee, 18)
    assert not acces.peut_valider_jalon(rai, mission_lancee, 5)
    assert not acces.peut_valider_jalon(sup, mission_lancee, 5)


def test_missions_visibles_par_role(
    mission_lancee: Mission,
    chef: User,
    auditeur_mission: User,
    audite_affecte: User,
    rai: User,
    admin: User,
    dg: User,
    django_assert_num_queries: Any,
) -> None:
    brouillon = MissionFactory()
    non_affecte = make_user(Role.AUDITEUR)
    assert set(acces.missions_visibles(rai)) == {mission_lancee, brouillon}
    assert list(acces.missions_visibles(non_affecte)) == []
    assert list(acces.missions_visibles(admin)) == []
    assert list(acces.missions_visibles(dg)) == []
    assert list(acces.missions_visibles(chef)) == [mission_lancee]
    assert list(acces.missions_visibles(auditeur_mission)) == [mission_lancee]
    # l'audité ne voit rien avant l'ordre de mission, puis la mission
    assert list(acces.missions_visibles(audite_affecte)) == []
    Mission.objects.filter(pk=mission_lancee.pk).update(
        ordre_mission_emis_le="2026-01-05T08:00:00Z"
    )
    assert list(acces.missions_visibles(audite_affecte)) == [mission_lancee]
    with django_assert_num_queries(1):
        list(acces.missions_visibles(audite_affecte))


def test_brouillon_invisible_a_l_auditeur_affecte() -> None:
    m = MissionFactory()
    aud = make_user(Role.AUDITEUR)
    affecter(m, aud, RoleMission.CHEF_MISSION)
    assert list(acces.missions_visibles(aud)) == []
    Mission.objects.filter(pk=m.pk).update(statut=StatutMission.PLANIFIEE, reference="DAI/2026/M09")
    assert list(acces.missions_visibles(aud)) == [m]


def test_pas_de_doublons(rai: User) -> None:
    MissionFactory()
    MissionFactory()
    assert acces.missions_visibles(rai).count() == 2


def test_superviseur_non_confirme_ne_valide_pas(mission_lancee: Mission) -> None:
    sup = make_user(Role.AUDITEUR)
    affecter(mission_lancee, sup, RoleMission.SUPERVISEUR, confirmee=False)
    assert not acces.peut_valider_jalon(sup, mission_lancee, 6)
