import pytest

from apps.constats.droits import actions_constat, constats_visibles, contexte_constats
from apps.constats.services.constats import soumettre_constat
from apps.missions.models import Mission, StatutEtape
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes

pytestmark = pytest.mark.django_db


def test_constats_visibles_par_role(
    mission_en_xiv: Mission, chef: User, audite_affecte: User, auditeur_mission: User
) -> None:
    brouillon = ConstatFactory(mission=mission_en_xiv)
    soumis = ConstatFactory(mission=mission_en_xiv)
    soumettre_constat(soumis, by=chef)
    rai = make_user(Role.RAI)
    assert set(constats_visibles(rai, mission_en_xiv)) == {brouillon, soumis}
    assert set(constats_visibles(auditeur_mission, mission_en_xiv)) == {brouillon, soumis}
    assert set(constats_visibles(audite_affecte, mission_en_xiv)) == {soumis}
    assert not constats_visibles(make_user(Role.AUDITE), mission_en_xiv).exists()
    assert not constats_visibles(make_user(Role.DG), mission_en_xiv).exists()


def test_actions_par_role(mission_en_xiv: Mission, chef: User, audite_affecte: User) -> None:
    c = ConstatFactory(mission=mission_en_xiv)
    audite_affecte.direction_code = c.entite.code
    audite_affecte.save(update_fields=["direction_code"])
    rai = make_user(Role.RAI)
    sup = make_user(Role.AUDITEUR)
    affecter(mission_en_xiv, sup, "SUPERVISEUR")
    ctx = lambda u: contexte_constats(mission_en_xiv, u)  # noqa: E731
    assert set(actions_constat(c, chef, contexte=ctx(chef))) == {
        "MODIFIER",
        "SUPPRIMER",
        "SOUMETTRE",
    }
    assert actions_constat(c, audite_affecte, contexte=ctx(audite_affecte)) == []
    soumettre_constat(c, by=chef)
    c.refresh_from_db()
    assert actions_constat(c, chef, contexte=ctx(chef)) == []
    assert set(actions_constat(c, rai, contexte=ctx(rai))) == {"VALIDER", "RENVOYER"}
    assert set(actions_constat(c, sup, contexte=ctx(sup))) == {"VALIDER", "RENVOYER"}
    assert actions_constat(c, audite_affecte, contexte=ctx(audite_affecte)) == ["REPONDRE"]
    forcer_etapes(mission_en_xiv, {15: StatutEtape.TERMINEE})
    assert actions_constat(c, audite_affecte, contexte=ctx(audite_affecte)) == []
    forcer_etapes(mission_en_xiv, {14: StatutEtape.TERMINEE})
    assert actions_constat(c, rai, contexte=ctx(rai)) == []
