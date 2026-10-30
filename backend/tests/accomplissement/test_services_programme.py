import pytest
from django.core.exceptions import PermissionDenied as DjangoDenied
from rest_framework.exceptions import PermissionDenied

from apps.accomplissement.models import ProgrammeDeTravail
from apps.accomplissement.services import programme as svc
from apps.accomplissement.services import tests_prevus as tests_svc
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.users.models import User
from tests.accomplissement.factories import TestPrevuFactory
from tests.factories import ObjectifAuditFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_creer_programme(mission_viii: Mission, chef: User) -> None:
    objectif = mission_viii.objectifs_audit.get(numero=2)
    p = svc.creer_programme(mission_viii, objectif=objectif, by=chef, techniques="Entretiens")
    assert p.objectif_id == objectif.pk
    assert p.created_by == chef


def test_references_croisees_refusees(mission_viii: Mission, chef: User) -> None:
    autre = ObjectifAuditFactory()  # autre mission
    with pytest.raises(RegleMetierError) as e:
        svc.creer_programme(mission_viii, objectif=autre, by=chef)
    assert e.value.errors["objectif"] == ["Cet objectif n'appartient pas à la mission."]
    assert ProgrammeDeTravail.objects.count() == 0


def test_programme_en_double_refuse(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    with pytest.raises(RegleMetierError):
        svc.creer_programme(programme_viii.mission, objectif=programme_viii.objectif, by=chef)


def test_objectif_non_retenu_refuse(mission_viii: Mission, chef: User) -> None:
    objectif = mission_viii.objectifs_audit.get(numero=2)
    forcer_etapes(mission_viii, {7: StatutEtape.EN_COURS})
    mission_viii.objectifs_audit.filter(pk=objectif.pk).update(
        retenu=False, motif_non_test="AUTRE", justification="x"
    )
    with pytest.raises(RegleMetierError):
        svc.creer_programme(mission_viii, objectif=objectif, by=chef)


def test_fenetre_viii_fermee_ou_pas_commencee(mission_viii: Mission, chef: User) -> None:
    objectif = mission_viii.objectifs_audit.get(numero=2)
    forcer_etapes(mission_viii, {8: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError, match="Commencez l'étape VIII"):
        svc.creer_programme(mission_viii, objectif=objectif, by=chef)
    forcer_etapes(mission_viii, {8: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        svc.creer_programme(mission_viii, objectif=objectif, by=chef)


def test_fenetre_viii_renvoyee_ouverte(mission_viii: Mission, chef: User) -> None:
    forcer_etapes(mission_viii, {8: StatutEtape.RENVOYEE})
    objectif = mission_viii.objectifs_audit.get(numero=2)
    assert svc.creer_programme(mission_viii, objectif=objectif, by=chef)


def test_modifier_programme_ferme(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    forcer_etapes(programme_viii.mission, {8: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        svc.modifier_programme(programme_viii, by=chef, commentaire="x")
    with pytest.raises(EtapeCloseError):
        svc.supprimer_programme(programme_viii, by=chef)


def test_modifier_programme(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    svc.modifier_programme(programme_viii, by=chef, commentaire="Nouveau")
    programme_viii.refresh_from_db()
    assert programme_viii.commentaire == "Nouveau"
    with pytest.raises(ValueError):
        svc.modifier_programme(programme_viii, by=chef, objectif=None)


def test_supprimer_programme_avec_tests_refuse(
    programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    TestPrevuFactory(mission=programme_viii.mission, programme=programme_viii)
    with pytest.raises(RegleMetierError, match="Supprimez d'abord les tests de ce programme."):
        svc.supprimer_programme(programme_viii, by=chef)


def test_supprimer_programme_vide(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    svc.supprimer_programme(programme_viii, by=chef)
    assert ProgrammeDeTravail.objects.count() == 0
    assert ProgrammeDeTravail.all_objects.count() == 1


def test_droit_contribution_exige(mission_viii: Mission, audite_affecte: User) -> None:
    objectif = mission_viii.objectifs_audit.get(numero=2)
    with pytest.raises((PermissionDenied, DjangoDenied)):
        svc.creer_programme(mission_viii, objectif=objectif, by=audite_affecte)


@pytest.mark.parametrize("statut", [StatutMission.SUSPENDUE, StatutMission.ANNULEE])
def test_gel_suspendue_toutes_ecritures_lot6(
    programme_viii: ProgrammeDeTravail, chef: User, statut: str
) -> None:
    mission = programme_viii.mission
    test = TestPrevuFactory(mission=mission, programme=programme_viii)
    objectif = mission.objectifs_audit.get(numero=2)
    Mission.objects.filter(pk=mission.pk).update(statut=statut)
    mission.refresh_from_db()
    appels = [
        lambda: svc.creer_programme(mission, objectif=objectif, by=chef),
        lambda: svc.modifier_programme(programme_viii, by=chef, commentaire="x"),
        lambda: svc.supprimer_programme(programme_viii, by=chef),
        lambda: tests_svc.creer_test(programme_viii, libelle="x", nature="AUTRE", by=chef),
        lambda: tests_svc.modifier_test(test, by=chef, libelle="y"),
        lambda: tests_svc.supprimer_test(test, by=chef),
        lambda: tests_svc.creer_test_complementaire(
            programme_viii, libelle="x", nature="AUTRE", by=chef
        ),
        lambda: tests_svc.abandonner_test(test, motif="x", by=chef),
    ]
    for appel in appels:
        with pytest.raises(MissionFigeeError):
            appel()
