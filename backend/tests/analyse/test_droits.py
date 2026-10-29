import dataclasses
from typing import Any

import pytest

from apps.analyse.droits import DroitsAnalyse, droits_analyse
from apps.missions.models import Mission
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes

pytestmark = pytest.mark.django_db

TOUS = [f.name for f in dataclasses.fields(DroitsAnalyse)]


def vrais(d: DroitsAnalyse) -> set[str]:
    return {n for n in TOUS if getattr(d, n)}


def test_rai(mission_en_analyse: Mission, rai: User) -> None:
    assert vrais(droits_analyse(rai, mission_en_analyse)) == {
        "voir_travaux",
        "contribuer_iii",
        "contribuer_v",
        "voir_referentiel",
    }


def test_chef_confirme_suit_les_fenetres(mission_en_analyse: Mission, chef: User) -> None:
    m = mission_en_analyse
    assert vrais(droits_analyse(chef, m)) == {
        "voir_travaux",
        "contribuer_iii",
        "contribuer_v",
        "voir_referentiel",
    }
    forcer_etapes(m, {3: "TERMINEE", 5: "TERMINEE", 6: "EN_COURS"})
    assert vrais(droits_analyse(chef, m)) == {"voir_travaux", "contribuer_v", "voir_referentiel"}
    forcer_etapes(m, {6: "VALIDEE", 7: "EN_COURS"})
    assert vrais(droits_analyse(chef, m)) == {
        "voir_travaux",
        "contribuer_vii",
        "voir_referentiel",
    }
    forcer_etapes(m, {7: "A_FAIRE"})
    assert vrais(droits_analyse(chef, m)) == {"voir_travaux", "voir_referentiel"}


def test_auditeur_non_confirme_ne_contribue_pas(mission_en_analyse: Mission) -> None:
    user = make_user(Role.AUDITEUR)
    affecter(mission_en_analyse, user, "AUDITEUR", confirmee=False)
    assert vrais(droits_analyse(user, mission_en_analyse)) == {"voir_travaux", "voir_referentiel"}


def test_superviseur_confirme_contribue(mission_en_analyse: Mission) -> None:
    user = make_user(Role.AUDITEUR)
    affecter(mission_en_analyse, user, "SUPERVISEUR")
    assert "contribuer_v" in vrais(droits_analyse(user, mission_en_analyse))


def test_audite_avant_et_apres_demarrage_de_vi(
    mission_en_analyse: Mission, audite_affecte: User
) -> None:
    m = mission_en_analyse
    assert vrais(droits_analyse(audite_affecte, m)) == set()
    forcer_etapes(m, {6: "EN_COURS"})
    assert vrais(droits_analyse(audite_affecte, m)) == {"voir_referentiel", "donner_avis"}
    forcer_etapes(m, {6: "TERMINEE"})
    assert vrais(droits_analyse(audite_affecte, m)) == {"voir_referentiel", "donner_avis"}
    forcer_etapes(m, {6: "VALIDEE"})
    assert vrais(droits_analyse(audite_affecte, m)) == {"voir_referentiel"}


def test_audite_non_affecte_admin_dg_et_auditeur_etranger(mission_en_analyse: Mission) -> None:
    for role in (Role.AUDITE, Role.ADMIN, Role.DG, Role.AUDITEUR):
        assert vrais(droits_analyse(make_user(role), mission_en_analyse)) == set()


def test_mission_figee_retire_les_ecritures(mission_en_analyse: Mission, chef: User) -> None:
    Mission.objects.filter(pk=mission_en_analyse.pk).update(
        statut="SUSPENDUE", statut_avant_suspension="EN_PLANIFICATION"
    )
    mission_en_analyse.refresh_from_db()
    assert vrais(droits_analyse(chef, mission_en_analyse)) == {"voir_travaux", "voir_referentiel"}


@pytest.mark.parametrize("role", ["rai", "chef", "audite_affecte"])
def test_au_plus_trois_requetes(
    mission_en_analyse: Mission,
    request: pytest.FixtureRequest,
    django_assert_max_num_queries: Any,
    role: str,
) -> None:
    user = request.getfixturevalue(role)
    with django_assert_max_num_queries(3):
        droits_analyse(user, mission_en_analyse)
