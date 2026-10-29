import pytest

from apps.accomplissement.droits import (
    ABANDONNER,
    AJOUTER_COMPLEMENTAIRE,
    MODIFIER,
    MODIFIER_CONTENU,
    MODIFIER_RESSOURCES,
    SUPPRIMER,
    actions_programme,
    actions_test,
    contexte_programme,
)
from apps.accomplissement.models import ProgrammeDeTravail
from apps.missions.models import Mission, RoleMission, StatutEtape, StatutMission
from apps.users.models import Role, User
from tests.accomplissement.factories import FicheFactory, TestPrevuFactory
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes

pytestmark = pytest.mark.django_db


def test_actions_par_role(
    mission_viii: Mission,
    programme_viii: ProgrammeDeTravail,
    chef: User,
    auditeur_mission: User,
    audite_affecte: User,
    rai: User,
) -> None:
    forcer_etapes(mission_viii, {9: StatutEtape.EN_COURS, 12: StatutEtape.EN_COURS})
    test = TestPrevuFactory(mission=mission_viii, programme=programme_viii)
    superviseur = make_user(Role.AUDITEUR)
    affecter(mission_viii, superviseur, RoleMission.SUPERVISEUR)
    non_confirme = make_user(Role.AUDITEUR)
    affecter(mission_viii, non_confirme, RoleMission.AUDITEUR, confirmee=False)

    def prog(u: User) -> list[str]:
        return actions_programme(u, mission_viii)

    assert prog(rai) == [MODIFIER_CONTENU, MODIFIER_RESSOURCES, AJOUTER_COMPLEMENTAIRE]
    assert prog(chef) == [MODIFIER_CONTENU, MODIFIER_RESSOURCES, AJOUTER_COMPLEMENTAIRE]
    assert prog(superviseur) == [MODIFIER_CONTENU, MODIFIER_RESSOURCES]
    assert prog(auditeur_mission) == [MODIFIER_CONTENU]
    assert prog(non_confirme) == []
    assert prog(audite_affecte) == []
    assert prog(make_user(Role.ADMIN)) == []

    ctx = contexte_programme(mission_viii, chef)
    assert actions_test(test, chef, contexte=ctx) == [MODIFIER, SUPPRIMER, ABANDONNER]
    ctx = contexte_programme(mission_viii, auditeur_mission)
    assert actions_test(test, auditeur_mission, contexte=ctx) == [MODIFIER, SUPPRIMER]
    ctx = contexte_programme(mission_viii, audite_affecte)
    assert actions_test(test, audite_affecte, contexte=ctx) == []


def test_actions_suivent_les_fenetres_et_le_gel(
    mission_viii: Mission, programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    test = TestPrevuFactory(mission=mission_viii, programme=programme_viii)
    assert actions_programme(chef, mission_viii) == [MODIFIER_CONTENU]
    forcer_etapes(mission_viii, {8: StatutEtape.TERMINEE})
    assert actions_programme(chef, mission_viii) == []
    ctx = contexte_programme(mission_viii, chef)
    assert actions_test(test, chef, contexte=ctx) == []
    forcer_etapes(mission_viii, {8: StatutEtape.EN_COURS})
    Mission.objects.filter(pk=mission_viii.pk).update(statut=StatutMission.SUSPENDUE)
    mission_viii.refresh_from_db()
    assert actions_programme(chef, mission_viii) == []


def test_supprimer_masque_si_fiche_et_complementaire(
    mission_viii: Mission, programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    forcer_etapes(mission_viii, {12: StatutEtape.EN_COURS})
    test = TestPrevuFactory(mission=mission_viii, programme=programme_viii)
    FicheFactory(mission=mission_viii, test=test)
    ctx = contexte_programme(mission_viii, chef)
    assert SUPPRIMER not in actions_test(test, chef, contexte=ctx)
    compl = TestPrevuFactory(mission=mission_viii, programme=programme_viii, complementaire=True)
    assert actions_test(compl, chef, contexte=ctx) == [MODIFIER, SUPPRIMER, ABANDONNER]
