import datetime
from collections.abc import Callable
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.constats.models import Constat, StatutConstat
from apps.missions.models import Mission, RoleMission, StatutMission
from apps.referentiel.models import CartographieVersion
from apps.suivi.models import StatutSuivi, SuiviAction
from apps.tableaux_de_bord.services import (
    tableau_audite,
    tableau_auditeur,
    tableau_dg,
    tableau_rai,
)
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import DirectionFactory, make_user
from tests.missions.conftest import affecter
from tests.suivi.factories import DemandeReportFactory
from tests.tableaux_de_bord.conftest import AUJOURD_HUI, faire_mission

CLES_RAI = {
    "annee",
    "missions_par_statut",
    "missions_en_retard",
    "etapes_en_retard",
    "jalons_a_valider",
    "actions_par_direction",
    "file_decisions",
    "cartographie",
    "taux",
}


def test_tableau_rai_requetes_bornees(
    django_assert_max_num_queries: Any, jeu_complet: Mission
) -> None:
    with django_assert_max_num_queries(12):
        tableau = tableau_rai(2026, AUJOURD_HUI)
    assert set(tableau) == CLES_RAI
    assert tableau["taux"]["total"] == 3
    assert tableau["cartographie"]["version_id"] is not None


def test_tableau_rai_ne_croit_pas_avec_le_volume(
    django_assert_max_num_queries: Any,
    jeu_complet: Mission,
    creer_suivi: Callable[..., SuiviAction],
) -> None:
    for _ in range(3):
        creer_suivi(
            jeu_complet, DirectionFactory(), StatutSuivi.EN_COURS, datetime.date(2026, 1, 1)
        )
    with django_assert_max_num_queries(12):
        tableau = tableau_rai(2026, AUJOURD_HUI)
    assert len(tableau["actions_par_direction"]) == 6


def test_tableau_auditeur_limite_a_ses_missions(
    django_assert_max_num_queries: Any,
    mission_diffusee: Mission,
    creer_suivi: Callable[..., SuiviAction],
) -> None:
    mission_en_suivi = mission_diffusee
    auditeur_mission = make_user(Role.AUDITEUR)
    affecter(mission_en_suivi, auditeur_mission, RoleMission.AUDITEUR)
    autre_auditeur = make_user(Role.AUDITEUR)
    realisee = creer_suivi(mission_en_suivi, DirectionFactory(), StatutSuivi.REALISEE)
    autre = faire_mission()
    creer_suivi(autre, DirectionFactory(), StatutSuivi.REALISEE)
    with django_assert_max_num_queries(8):
        tableau = tableau_auditeur(auditeur_mission, AUJOURD_HUI)
    assert set(tableau) == {
        "mes_missions",
        "mes_etapes_en_cours",
        "mes_tests_a_documenter",
        "actions_a_verifier",
    }
    assert [m["mission_id"] for m in tableau["mes_missions"]] == [mission_en_suivi.pk]
    assert [a["suivi_id"] for a in tableau["actions_a_verifier"]] == [realisee.pk]
    vide = tableau_auditeur(autre_auditeur, AUJOURD_HUI)
    assert vide["mes_missions"] == [] and vide["actions_a_verifier"] == []


def test_tableau_auditeur_refuse_les_autres_roles(db: None) -> None:
    for role in (Role.RAI, Role.AUDITE, Role.DG, Role.ADMIN):
        with pytest.raises(PermissionDenied):
            tableau_auditeur(make_user(role), AUJOURD_HUI)


def test_tableau_audite_constats_a_repondre_cycle_courant(
    django_assert_max_num_queries: Any,
    mission_diffusee: Mission,
    creer_suivi: Callable[..., SuiviAction],
) -> None:
    mission_en_suivi = mission_diffusee
    responsable = make_user(Role.AUDITE)
    affecter(mission_en_suivi, responsable, RoleMission.AUDITE)
    entite = DirectionFactory()
    User.objects.filter(pk=responsable.pk).update(direction_code=entite.code)
    responsable.refresh_from_db()
    constat: Constat = ConstatFactory(mission=mission_en_suivi, entite=entite)
    Constat.objects.filter(pk=constat.pk).update(
        statut=StatutConstat.SOUMIS, cycle=1, soumis_le=timezone.now()
    )
    tard = creer_suivi(
        mission_en_suivi, entite, StatutSuivi.EN_COURS, datetime.date(2026, 10, 19), responsable
    )
    bientot = creer_suivi(
        mission_en_suivi, entite, StatutSuivi.A_LANCER, datetime.date(2026, 12, 1), responsable
    )
    creer_suivi(
        mission_en_suivi, entite, StatutSuivi.CLOTUREE, datetime.date(2026, 11, 1), responsable
    )
    creer_suivi(mission_en_suivi, entite, StatutSuivi.EN_COURS, datetime.date(2026, 10, 1))  # autre
    demande = DemandeReportFactory(suivi=bientot, demandee_par=responsable)
    with django_assert_max_num_queries(8):
        tableau = tableau_audite(responsable, AUJOURD_HUI)
    assert set(tableau) == {"constats_a_repondre", "mes_actions", "mes_demandes_report"}
    assert [c["constat_id"] for c in tableau["constats_a_repondre"]] == [constat.pk]
    assert [(a["suivi_id"], a["en_retard"], a["jours_retard"]) for a in tableau["mes_actions"]] == [
        (tard.pk, True, 10),
        (bientot.pk, False, None),
    ]
    assert [d["demande_id"] for d in tableau["mes_demandes_report"]] == [demande.pk]
    # La ligne nomme l'action, pas seulement la mission (deux demandes d'une mission se distinguent).
    assert tableau["mes_demandes_report"][0]["libelle"] == bientot.action.libelle


def test_tableau_audite_refuse_les_autres_roles(db: None) -> None:
    with pytest.raises(PermissionDenied):
        tableau_audite(make_user(Role.AUDITEUR), AUJOURD_HUI)


def test_tableau_dg_seulement_rapports_diffuses(
    django_assert_max_num_queries: Any,
    mission_diffusee: Mission,
    creer_suivi: Callable[..., SuiviAction],
    valider_carto: Callable[[CartographieVersion], CartographieVersion],
) -> None:
    entite = DirectionFactory()
    creer_suivi(mission_diffusee, entite, StatutSuivi.CLOTUREE)
    creer_suivi(mission_diffusee, entite, StatutSuivi.EN_COURS)
    en_cours = faire_mission(StatutMission.EN_COMMUNICATION)
    faire_mission(StatutMission.BROUILLON)
    faire_mission(StatutMission.EN_SUIVI, annee=2025)
    with django_assert_max_num_queries(10):
        tableau = tableau_dg(2026, AUJOURD_HUI)
    assert set(tableau) == {
        "annee",
        "rapports_diffuses",
        "taux",
        "taux_par_direction",
        "risques_eleves",
    }
    (rapport,) = tableau["rapports_diffuses"]
    assert rapport["mission_id"] == mission_diffusee.pk
    assert (rapport["nombre_actions"], rapport["actions_cloturees"]) == (2, 1)
    assert en_cours.pk not in {r["mission_id"] for r in tableau["rapports_diffuses"]}
    assert str(tableau["taux"]["taux"]) == "0.50"
    assert [d["code"] for d in tableau["taux_par_direction"]] == [entite.code]


@pytest.mark.parametrize("tableau", [tableau_dg, tableau_rai])
def test_une_seule_regle_d_annee_celle_de_la_mission(
    db: None, creer_suivi: Callable[..., SuiviAction], tableau: Callable[..., dict[str, Any]]
) -> None:
    """Rapports, taux et risques suivent l'année de la mission, pas celle de la diffusion."""
    mission = faire_mission(annee=2027)
    suivi = creer_suivi(mission, DirectionFactory(), StatutSuivi.CLOTUREE)
    assert suivi.diffuse_le.year == 2026  # diffusé l'année précédant celle de la mission
    en_2027 = tableau(2027, AUJOURD_HUI)
    en_2026 = tableau(2026, AUJOURD_HUI)
    assert en_2027["taux"]["total"] == 1
    assert en_2026["taux"]["total"] == 0
    if tableau is tableau_dg:
        assert [m["reference"] for m in en_2027["rapports_diffuses"]] == [mission.reference]
        assert en_2026["rapports_diffuses"] == []
