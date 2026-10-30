import datetime

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection

from apps.constats.models import Constat, Recommandation, StatutConstat
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.recommandations.models import Action
from apps.recommandations.services._fenetres import MSG_FENETRE
from apps.recommandations.services.actions import (
    MSG_ECHEANCE,
    MSG_NON_VALIDE,
    MSG_RESPONSABLE,
    creer_action,
    modifier_action,
    supprimer_action,
)
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes

dans_30_jours = datetime.date.today() + datetime.timedelta(days=30)


def _erreur(exc: pytest.ExceptionInfo[RegleMetierError], champ: str) -> list[str]:
    return list(exc.value.errors[champ])


@pytest.mark.django_db
def test_chef_cree_une_action(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    chef: User,
    audite_entite_a: User,
) -> None:
    action = creer_action(
        recommandations[0],
        libelle=" Mesure ",
        by=chef,
        responsable=audite_entite_a,
        echeance=dans_30_jours,
        indicateur="i",
    )
    assert (action.reference, action.numero, action.libelle) == ("A-01", 1, "Mesure")
    assert action.proposee_par == chef
    assert action.statut == "A_LANCER"


@pytest.mark.django_db
def test_audite_propose_une_action_sur_son_entite(
    recommandations: list[Recommandation], audite_entite_a: User
) -> None:
    action = creer_action(recommandations[0], libelle="Mesure", by=audite_entite_a)
    assert action.proposee_par == audite_entite_a


@pytest.mark.django_db
def test_audite_autre_entite_refuse(
    recommandations: list[Recommandation], audite_entite_b: User
) -> None:
    with pytest.raises(PermissionDenied):
        creer_action(recommandations[0], libelle="Mesure", by=audite_entite_b)


@pytest.mark.django_db
def test_responsable_hors_mission_refuse(recommandations: list[Recommandation], chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_action(recommandations[0], libelle="M", by=chef, responsable=make_user(Role.AUDITE))
    assert _erreur(exc, "responsable") == [MSG_RESPONSABLE]


@pytest.mark.django_db
def test_echeance_passee_refusee(recommandations: list[Recommandation], chef: User) -> None:
    hier = datetime.date.today() - datetime.timedelta(days=2)
    with pytest.raises(RegleMetierError) as exc:
        creer_action(recommandations[0], libelle="M", by=chef, echeance=hier)
    assert _erreur(exc, "echeance") == [MSG_ECHEANCE]


@pytest.mark.django_db
def test_saisie_hors_xv_xvi_refusee(
    mission_en_communication: Mission, recommandations: list[Recommandation], chef: User
) -> None:
    forcer_etapes(mission_en_communication, {15: StatutEtape.TERMINEE, 16: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError, match=MSG_FENETRE):
        creer_action(recommandations[0], libelle="M", by=chef)
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError, match=MSG_FENETRE):
        creer_action(recommandations[0], libelle="M", by=chef)


@pytest.mark.django_db
def test_ebauche_des_xv_puis_xvi_en_cours(
    mission_en_communication: Mission, recommandations: list[Recommandation], chef: User
) -> None:
    forcer_etapes(mission_en_communication, {15: StatutEtape.EN_COURS, 16: StatutEtape.A_FAIRE})
    creer_action(recommandations[0], libelle="M", by=chef)
    forcer_etapes(mission_en_communication, {15: StatutEtape.TERMINEE, 16: StatutEtape.EN_COURS})
    creer_action(recommandations[0], libelle="N", by=chef)


@pytest.mark.django_db
def test_constat_non_valide_refuse(
    mission_en_communication: Mission, recommandations: list[Recommandation], chef: User
) -> None:
    with connection.cursor() as cur:  # SQL brut : le constat VALIDE est gelé par ses gardes
        cur.execute(
            f"UPDATE {Constat._meta.db_table} SET statut = %s WHERE id = %s",  # noqa: S608
            [StatutConstat.SOUMIS, recommandations[0].constat_id],
        )
    with pytest.raises(RegleMetierError, match=MSG_NON_VALIDE):
        creer_action(recommandations[0], libelle="M", by=chef)


@pytest.mark.django_db
def test_modifier_et_supprimer(
    recommandations: list[Recommandation],
    chef: User,
    audite_entite_a: User,
    audite_entite_b: User,
) -> None:
    action = creer_action(recommandations[0], libelle="M", by=audite_entite_a)
    modifier_action(action, by=audite_entite_a, libelle="N", moyens="x")
    action.refresh_from_db()
    assert (action.libelle, action.moyens) == ("N", "x")
    with pytest.raises(PermissionDenied):
        modifier_action(action, by=audite_entite_b, libelle="Z")
    with pytest.raises(ValueError, match="statut"):
        modifier_action(action, by=chef, statut="REALISEE")
    supprimer_action(action, by=chef)
    assert not Action.objects.filter(pk=action.pk).exists()
    assert Action.all_objects.filter(pk=action.pk, deleted_at__isnull=False).exists()
    # La référence n'est jamais réattribuée.
    assert creer_action(recommandations[0], libelle="P", by=chef).reference == "A-02"


@pytest.mark.django_db
def test_gel_suspendue_toutes_ecritures_plan(
    mission_en_communication: Mission, recommandations: list[Recommandation], chef: User
) -> None:
    action = creer_action(recommandations[0], libelle="M", by=chef)
    Mission.objects.filter(pk=mission_en_communication.pk).update(statut=StatutMission.SUSPENDUE)
    with pytest.raises(MissionFigeeError):
        creer_action(recommandations[0], libelle="N", by=chef)
    with pytest.raises(MissionFigeeError):
        modifier_action(action, by=chef, libelle="N")
    with pytest.raises(MissionFigeeError):
        supprimer_action(action, by=chef)
