import pytest

from apps.core.exceptions import RegleMetierError
from apps.missions.models import (
    AffectationMission,
    DeclarationIndependance,
    Mission,
    RoleMission,
    StatutDeclaration,
    StatutMission,
)
from apps.missions.services.equipe import (
    MSG_AUDITE,
    MSG_CHEF_EXISTE,
    MSG_CHEF_RETRAIT,
    MSG_DEJA_AFFECTE,
    MSG_INTERVENANT,
    MSG_SUPERVISEUR_CHEF,
    MSG_SUPERVISEUR_EXISTE,
    affecter,
    audites_par_defaut,
    desaffecter,
    remplacer_chef,
)
from apps.users.models import Role, User
from tests.factories import DirectionFactory, MissionFactory, make_user


def _refus(**kw: object) -> str:
    with pytest.raises(RegleMetierError) as e:
        affecter(**kw)  # type: ignore[arg-type]
    return next(iter(e.value.errors.values()))[0]


@pytest.fixture
def mission(db: None) -> Mission:
    return MissionFactory(
        statut=StatutMission.PLANIFIEE, reference="DAI/2026/M01", annee=2026, numero=1
    )


def test_affecter_cree_la_declaration_des_intervenants_seulement(rai: User, mission: Mission):
    a = affecter(mission, utilisateur=make_user(Role.AUDITEUR), role_mission="AUDITEUR", by=rai)
    assert a.declaration.statut == StatutDeclaration.EN_ATTENTE
    b = affecter(mission, utilisateur=make_user(Role.AUDITE), role_mission="AUDITE", by=rai)
    assert not DeclarationIndependance.objects.filter(affectation=b).exists()


def test_affecter_regles(rai: User, mission: Mission):
    auditeur, audite = make_user(Role.AUDITEUR), make_user(Role.AUDITE)
    assert (
        _refus(mission=mission, utilisateur=audite, role_mission="AUDITEUR", by=rai)
        == MSG_INTERVENANT
    )
    assert (
        _refus(mission=mission, utilisateur=rai, role_mission="CHEF_MISSION", by=rai)
        == MSG_INTERVENANT
    )
    assert (
        _refus(mission=mission, utilisateur=auditeur, role_mission="AUDITE", by=rai) == MSG_AUDITE
    )

    chef = affecter(mission, utilisateur=auditeur, role_mission="CHEF_MISSION", by=rai).utilisateur
    assert (
        _refus(mission=mission, utilisateur=make_user(), role_mission="CHEF_MISSION", by=rai)
        == MSG_CHEF_EXISTE
    )
    assert (
        _refus(mission=mission, utilisateur=chef, role_mission="AUDITEUR", by=rai)
        == MSG_DEJA_AFFECTE
    )
    assert (
        _refus(mission=mission, utilisateur=chef, role_mission="SUPERVISEUR", by=rai)
        == MSG_SUPERVISEUR_CHEF
    )

    sup = make_user()
    affecter(mission, utilisateur=sup, role_mission="SUPERVISEUR", by=rai)
    assert (
        _refus(mission=mission, utilisateur=make_user(), role_mission="SUPERVISEUR", by=rai)
        == MSG_SUPERVISEUR_EXISTE
    )
    assert (
        _refus(mission=mission, utilisateur=sup, role_mission="CHEF_MISSION", by=rai)
        == MSG_SUPERVISEUR_CHEF
    )


def test_desaffecter_et_reaffecter(rai: User, mission: Mission):
    u = make_user()
    a = affecter(mission, utilisateur=u, role_mission="AUDITEUR", by=rai)
    desaffecter(a, by=rai)
    assert not AffectationMission.objects.filter(pk=a.pk).exists()
    assert not DeclarationIndependance.objects.filter(affectation=a).exists()
    b = affecter(mission, utilisateur=u, role_mission="AUDITEUR", by=rai)
    assert b.declaration.statut == StatutDeclaration.EN_ATTENTE and b.pk != a.pk


def test_chef_retire_avant_lancement_pas_apres(rai: User, mission: Mission):
    a = affecter(mission, utilisateur=make_user(), role_mission="CHEF_MISSION", by=rai)
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.EN_PLANIFICATION)
    with pytest.raises(RegleMetierError) as e:
        desaffecter(a, by=rai)
    assert e.value.message == MSG_CHEF_RETRAIT
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.PLANIFIEE)
    desaffecter(a, by=rai)


def test_remplacer_chef(rai: User, mission: Mission):
    ancien = make_user()
    a = affecter(mission, utilisateur=ancien, role_mission="CHEF_MISSION", by=rai)
    decl = a.declaration
    nouveau = make_user()
    n = remplacer_chef(mission, utilisateur=nouveau, by=rai)
    assert n.role_mission == RoleMission.CHEF_MISSION and n.utilisateur == nouveau
    assert n.declaration.statut == StatutDeclaration.EN_ATTENTE
    a.refresh_from_db()
    assert a.role_mission == RoleMission.AUDITEUR
    assert DeclarationIndependance.objects.filter(pk=decl.pk).exists()
    # Un auditeur déjà dans l'équipe devient chef en gardant sa déclaration.
    autre = make_user()
    b = affecter(mission, utilisateur=autre, role_mission="AUDITEUR", by=rai)
    r = remplacer_chef(mission, utilisateur=autre, by=rai)
    assert r.pk == b.pk and r.role_mission == RoleMission.CHEF_MISSION
    assert mission.affectations.filter(role_mission="CHEF_MISSION").count() == 1
    with pytest.raises(RegleMetierError):
        remplacer_chef(mission, utilisateur=autre, by=rai)


def test_remplacer_chef_sans_chef_refuse(rai: User, mission: Mission):
    with pytest.raises(RegleMetierError):
        remplacer_chef(mission, utilisateur=make_user(), by=rai)


def test_audites_par_defaut_par_direction_code(rai: User, mission: Mission):
    d1, d2 = DirectionFactory(code="DEX"), DirectionFactory(code="DAF")
    mission.entites.add(d1)
    ok = make_user(Role.AUDITE, direction_code="DEX")
    make_user(Role.AUDITE, direction_code="DAF")  # entité non auditée
    make_user(Role.AUDITE, direction_code="DEX", is_active=False)
    make_user(Role.AUDITEUR, direction_code="DEX")
    assert list(audites_par_defaut(mission)) == [ok]
    mission.entites.add(d2)
    assert audites_par_defaut(mission).count() == 2
