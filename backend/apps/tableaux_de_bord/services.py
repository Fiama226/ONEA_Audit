"""Tableaux de bord par rôle : assemblage des agrégats (clés figées par les tests de contrat)."""

from datetime import date
from typing import Any

from apps.missions.acces import missions_visibles
from apps.missions.models import Mission, StatutMission
from apps.suivi.droits import STATUTS_MISSION_SUIVI, suivis_visibles
from apps.suivi.models import SuiviAction
from apps.users.models import Role, User

from . import agregats
from .perimetres import exiger_role, missions_de_l_annee, suivis_diffuses_de_l_annee


def tableau_rai(annee: int, aujourd_hui: date) -> dict[str, Any]:
    missions = missions_de_l_annee(Mission.objects.all(), annee)
    suivis = suivis_diffuses_de_l_annee(SuiviAction.objects.all(), annee)
    return {
        "annee": annee,
        "missions_par_statut": agregats.missions_par_statut(missions),
        "missions_en_retard": agregats.missions_en_retard(missions, aujourd_hui),
        "etapes_en_retard": agregats.etapes_en_retard(missions, aujourd_hui),
        "jalons_a_valider": agregats.jalons_a_valider(missions),
        "actions_par_direction": agregats.actions_par_direction(suivis, aujourd_hui),
        "file_decisions": agregats.file_decisions_rai(),
        "cartographie": agregats.cartographie(annee),
        "taux": agregats.taux_mise_en_oeuvre(suivis, aujourd_hui),
    }


def tableau_auditeur(user: User, aujourd_hui: date) -> dict[str, Any]:
    exiger_role(user, Role.AUDITEUR)
    missions = missions_visibles(user).exclude(statut=StatutMission.BROUILLON)
    return {
        "mes_missions": agregats.missions_resume(missions),
        "mes_etapes_en_cours": agregats.mes_etapes_en_cours(missions, aujourd_hui),
        "mes_tests_a_documenter": agregats.mes_tests_a_documenter(user),
        "actions_a_verifier": agregats.actions_a_verifier(suivis_visibles(user)),
    }


def tableau_audite(user: User, aujourd_hui: date) -> dict[str, Any]:
    exiger_role(user, Role.AUDITE)
    return {
        "constats_a_repondre": agregats.constats_a_repondre(user),
        "mes_actions": agregats.mes_actions(suivis_visibles(user), user, aujourd_hui),
        "mes_demandes_report": agregats.mes_demandes_report(user),
    }


def tableau_dg(annee: int, aujourd_hui: date) -> dict[str, Any]:
    missions = missions_de_l_annee(Mission.objects.filter(statut__in=STATUTS_MISSION_SUIVI), annee)
    suivis = suivis_diffuses_de_l_annee(SuiviAction.objects.all(), annee)
    return {
        "annee": annee,
        "rapports_diffuses": agregats.rapports_diffuses(missions),
        "taux": agregats.taux_mise_en_oeuvre(suivis, aujourd_hui),
        "taux_par_direction": agregats.taux_par_direction(suivis, aujourd_hui),
        "risques_eleves": agregats.risques_eleves(annee),
    }
