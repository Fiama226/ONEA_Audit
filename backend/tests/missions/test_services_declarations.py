import pytest

from apps.core.exceptions import RegleMetierError
from apps.missions.models import (
    DeclarationIndependance,
    Mission,
    StatutDeclaration,
    StatutMission,
)
from apps.missions.services.declarations import (
    MSG_AUTRE,
    MSG_DEJA_CONFIRMEE,
    arbitrer_conflit,
    confirmation_de,
    confirmer_declaration,
    texte_declaration,
)
from apps.missions.services.equipe import affecter
from apps.signatures.services import verifier
from apps.users.models import Role, User
from tests.factories import DirectionFactory, MissionFactory, make_user


@pytest.fixture
def mission(db: None) -> Mission:
    m = MissionFactory(
        statut=StatutMission.PLANIFIEE,
        reference="DAI/2026/M07",
        annee=2026,
        numero=7,
        titre="Audit des achats",
    )
    m.entites.add(DirectionFactory(code="DAF", libelle="Direction Administrative et Financière"))
    m.entites.add(DirectionFactory(code="DEX", libelle="Direction de l'Exploitation"))
    return m


@pytest.fixture
def auditeur(rai: User, mission: Mission) -> User:
    u = make_user(Role.AUDITEUR, first_name="Awa", last_name="Sawadogo")
    affecter(mission, utilisateur=u, role_mission="AUDITEUR", by=rai)
    return u


def _declaration(mission: Mission, user: User) -> DeclarationIndependance:
    return DeclarationIndependance.objects.get(
        affectation__mission=mission, affectation__utilisateur=user
    )


def test_texte_declaration_exact(mission: Mission, auditeur: User):
    assert texte_declaration(_declaration(mission, auditeur)) == (
        "Je soussigné(e) Awa Sawadogo, affecté(e) à la mission DAI/2026/M07 « Audit des achats » "
        "en qualité de auditeur, déclare n'avoir, à ma connaissance, aucun conflit d'intérêts ni "
        "aucune relation personnelle, professionnelle ou financière avec les entités auditées "
        "(Direction Administrative et Financière, Direction de l'Exploitation), ni avoir exercé "
        "de responsabilité opérationnelle sur les activités auditées au cours des douze derniers "
        "mois, de nature à porter atteinte à mon objectivité (Normes internationales d'audit "
        "interne, principe 2). Je m'engage à signaler sans délai au Responsable de l'Audit "
        "Interne toute situation nouvelle de cette nature."
    )


def test_confirmer_la_declaration(mission: Mission, auditeur: User):
    d = confirmer_declaration(_declaration(mission, auditeur), by=auditeur, adresse_ip="10.1.1.1")
    assert d.statut == StatutDeclaration.CONFIRMEE and d.levee
    c = confirmation_de(d)
    assert c is not None and verifier(c)
    assert c.donnees == {
        "mission": str(mission.pk),
        "reference": "DAI/2026/M07",
        "role_mission": "AUDITEUR",
        "conflit": False,
        "description_conflit": "",
    }
    assert c.texte == texte_declaration(d)
    with pytest.raises(RegleMetierError) as e:
        confirmer_declaration(d, by=auditeur)
    assert e.value.message == MSG_DEJA_CONFIRMEE


def test_confirmer_la_declaration_d_un_autre_refuse(rai: User, mission: Mission, auditeur: User):
    d = _declaration(mission, auditeur)
    for autre in (rai, make_user(Role.AUDITEUR)):
        with pytest.raises(RegleMetierError) as e:
            confirmer_declaration(d, by=autre)
        assert e.value.message == MSG_AUTRE
    assert confirmation_de(d) is None


def test_confirmer_refusee_sur_brouillon(rai: User, auditeur: User, mission: Mission):
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.BROUILLON, reference="")
    with pytest.raises(RegleMetierError):
        confirmer_declaration(_declaration(mission, auditeur), by=auditeur)


def test_conflit_puis_arbitrage_leve_la_declaration(rai: User, mission: Mission, auditeur: User):
    d = _declaration(mission, auditeur)
    with pytest.raises(RegleMetierError) as e:
        confirmer_declaration(d, by=auditeur, conflit=True, description_conflit="  ")
    assert "description_conflit" in e.value.errors
    d = confirmer_declaration(
        d, by=auditeur, conflit=True, description_conflit="Ancien chef de service"
    )
    assert d.statut == StatutDeclaration.CONFLIT_DECLARE and not d.levee
    c = confirmation_de(d)
    assert c is not None and c.donnees["conflit"] is True and "Ancien chef de service" in c.texte
    with pytest.raises(RegleMetierError):
        arbitrer_conflit(d, justification=" ", by=rai)
    d = arbitrer_conflit(d, justification="Aucune incidence, mission non concernée", by=rai)
    assert d.levee and d.arbitre_par == rai and d.arbitre_le is not None
    with pytest.raises(RegleMetierError):
        arbitrer_conflit(d, justification="Encore", by=rai)


def test_arbitrer_sans_conflit_refuse(rai: User, mission: Mission, auditeur: User):
    with pytest.raises(RegleMetierError):
        arbitrer_conflit(_declaration(mission, auditeur), justification="x", by=rai)
