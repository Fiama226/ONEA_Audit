"""Type de document « Plan d'actions » (lot 7, T9)."""

from typing import Any

import pytest
from django.utils import timezone

from apps.constats.models import Recommandation
from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.contrats import EXEMPLE_COMMUN, ecarts_contexte
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import type_document
from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.users.models import Role, User
from tests.factories import make_user
from tests.recommandations.factories import AcceptationFactory, ActionFactory


@pytest.fixture
def plan(mission_en_communication: Mission, recommandations: list[Recommandation]) -> Mission:
    ActionFactory(recommandation=recommandations[0], mission=mission_en_communication)
    ActionFactory(recommandation=recommandations[0], mission=mission_en_communication)
    AcceptationFactory(recommandation=recommandations[2], mission=mission_en_communication)
    return mission_en_communication


def _contexte(mission: Mission) -> dict[str, Any]:
    return dict(EXEMPLE_COMMUN) | type_document("PLAN_ACTIONS").fournisseur.contexte(mission)


def _sans_none(valeur: Any) -> bool:
    if valeur is None:
        return False
    if isinstance(valeur, dict):
        return all(_sans_none(v) for v in valeur.values())
    if isinstance(valeur, list):
        return all(_sans_none(v) for v in valeur)
    return True


def test_type_enregistre() -> None:
    t = type_document("PLAN_ACTIONS")
    assert (t.etape, t.abreviation, t.portee_numero) == (16, "PA", "MISSION")


def test_contexte_sans_none_et_conforme_au_contrat(plan: Mission) -> None:
    contexte = _contexte(plan)
    assert _sans_none(contexte)
    assert ecarts_contexte(type_document("PLAN_ACTIONS").contrat, contexte) == []
    assert len(contexte["recommandations"]) == 3
    assert len(contexte["actions"]) == 2
    assert {r["statut"] for r in contexte["recommandations"]} >= {"À lancer", "Risque accepté"}
    assert any(r["acceptation"] for r in contexte["recommandations"])


def test_provisoire_tant_que_xvi_n_est_pas_close(plan: Mission) -> None:
    assert _contexte(plan)["provisoire"] == "Oui"
    EtapeMission.objects.filter(mission=plan, numero=16).update(statut=StatutEtape.TERMINEE)
    assert _contexte(plan)["provisoire"] == ""


def test_gabarit_provisoire_valide() -> None:
    t = type_document("PLAN_ACTIONS")
    balises = analyser_gabarit(
        construire_gabarit_provisoire(t), t.contrat, nom_fichier="p.docx", taille_max_mo=10
    )
    assert {"mission", "actions"} <= balises


def test_contexte_requetes_bornees(plan: Mission, django_assert_max_num_queries: Any) -> None:
    with django_assert_max_num_queries(20):
        type_document("PLAN_ACTIONS").fournisseur.contexte(plan)


def test_droits_fournisseur(plan: Mission, chef: User, audite_entite_a: User, rai: User) -> None:
    Mission.objects.filter(pk=plan.pk).update(ordre_mission_emis_le=timezone.now())
    fournisseur = type_document("PLAN_ACTIONS").fournisseur
    assert fournisseur.peut_consulter(rai, plan)
    assert fournisseur.peut_consulter(chef, plan)
    assert not fournisseur.peut_consulter(audite_entite_a, plan)
    assert not fournisseur.peut_consulter(make_user(Role.DG), plan)
    assert not fournisseur.peut_consulter(make_user(Role.ADMIN), plan)
    assert fournisseur.peut_generer(rai, plan)
    assert not fournisseur.peut_generer(audite_entite_a, plan)
    assert fournisseur.raison_non_generable(plan) is None
