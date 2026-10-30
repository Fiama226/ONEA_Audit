# ruff: noqa: F811, F401, F403
"""Registre des recommandations : statut dérivé (SQL = fonction pure), filtres, requêtes bornées."""

import datetime
from typing import Any

import pytest

from apps.constats.models import Recommandation
from apps.missions.models import StatutEtape
from apps.suivi.models import StatutSuivi, SuiviAction
from apps.suivi.services.registre import Compteurs, statut_recommandation
from tests.accomplissement.fixtures_api import client_de
from tests.constats.factories import RecommandationFactory
from tests.missions.conftest import forcer_etapes
from tests.recommandations.factories import ActionFactory
from tests.suivi.factories import SuiviActionFactory
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import RECOMMANDATIONS, EquipeSuivi

pytestmark = pytest.mark.django_db

S = StatutSuivi


@pytest.mark.parametrize(
    ("compteurs", "attendu"),
    [
        (Compteurs(0, 0, 0, 0), "SANS_ACTION"),
        (Compteurs(0, 0, 0, 0, risque_accepte=True), "RISQUE_ACCEPTE"),
        (Compteurs(2, 2, 0, 0), "REALISEE"),
        (Compteurs(2, 1, 1, 0), "REALISEE"),
        (Compteurs(2, 0, 2, 0), "ABANDONNEE"),
        (Compteurs(2, 0, 0, 2), "A_LANCER"),
        (Compteurs(2, 1, 0, 1), "EN_COURS"),
        (Compteurs(3, 0, 0, 1), "EN_COURS"),
        (Compteurs(1, 0, 1, 0), "ABANDONNEE"),
    ],
)
def test_statut_recommandation_fonction_pure(compteurs: Compteurs, attendu: str) -> None:
    assert statut_recommandation(compteurs) == attendu


def _lignes(e: EquipeSuivi, qui: str = "rai", **params: Any) -> list[dict[str, Any]]:
    reponse = client_de(e.users[qui]).get(RECOMMANDATIONS, {"page_size": 100, **params})
    assert reponse.status_code == 200, reponse.content
    resultats: list[dict[str, Any]] = reponse.json()["results"]
    return resultats


def _forcer(suivi: SuiviAction, statut: str) -> None:
    SuiviAction.objects.filter(pk=suivi.pk).update(
        statut=statut, justification_abandon="Obsolète." if statut == S.ABANDONNEE else ""
    )


@pytest.mark.parametrize(
    "statuts",
    [
        (S.A_LANCER, S.A_LANCER),
        (S.CLOTUREE, S.CLOTUREE),
        (S.ABANDONNEE, S.ABANDONNEE),
        (S.CLOTUREE, S.ABANDONNEE),
        (S.CLOTUREE, S.A_LANCER),
        (S.EN_COURS, S.A_LANCER),
        (S.VERIFIEE, S.A_LANCER),
        (S.REALISEE, S.EN_COURS),
    ],
)
def test_registre_statut_derive_sql_egal_fonction_pure(
    equipe_suivi: EquipeSuivi, statuts: tuple[str, str]
) -> None:
    e = equipe_suivi
    reco_a = e.suivis[0].recommandation
    deux = list(SuiviAction.objects.filter(recommandation=reco_a))
    assert len(deux) == 2
    for suivi, statut in zip(deux, statuts, strict=True):
        _forcer(suivi, statut)
    ligne = next(r for r in _lignes(e) if r["id"] == str(reco_a.pk))
    attendu = statut_recommandation(
        Compteurs(
            total=2,
            cloturees=statuts.count(S.CLOTUREE),
            abandonnees=statuts.count(S.ABANDONNEE),
            a_lancer=statuts.count(S.A_LANCER),
        )
    )
    assert ligne["statut_suivi"] == attendu
    assert ligne["actions_total"] == 2
    assert ligne["actions_closes"] == sum(1 for s in statuts if s in (S.CLOTUREE, S.ABANDONNEE))


def test_registre_risque_accepte_et_sans_action(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    constat = e.suivi.recommandation.constat
    forcer_etapes(e.mission, {14: StatutEtape.EN_COURS})  # garde du lot 6 sur les recommandations
    sans_action = RecommandationFactory(constat=constat, ordre=3)
    forcer_etapes(e.mission, {14: StatutEtape.VALIDEE})
    lignes = {r["id"]: r for r in _lignes(e)}
    assert len(lignes) == 4
    acceptee = [r for r in lignes.values() if r["risque_accepte"]]
    assert len(acceptee) == 1
    assert acceptee[0]["statut_suivi"] == "RISQUE_ACCEPTE"
    assert acceptee[0]["actions_total"] == 0
    assert lignes[str(sans_action.pk)]["statut_suivi"] == "SANS_ACTION"
    assert lignes[str(sans_action.pk)]["prochaine_echeance"] is None


def test_registre_forme_filtres_et_tri(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    reco_a = e.suivis[0].recommandation
    ligne = next(r for r in _lignes(e) if r["id"] == str(reco_a.pk))
    assert set(ligne) == {
        "id",
        "mission",
        "constat",
        "entite",
        "libelle",
        "priorite",
        "statut_suivi",
        "risque_accepte",
        "actions_total",
        "actions_closes",
        "actions_en_retard",
        "prochaine_echeance",
    }
    assert ligne["mission"]["id"] == str(e.mission.pk)
    assert ligne["actions_en_retard"] == 0
    assert ligne["prochaine_echeance"] == str(
        min(s.echeance for s in SuiviAction.objects.filter(recommandation=reco_a))
    )
    assert {r["id"] for r in _lignes(e, mission=e.mission.pk)} == {r["id"] for r in _lignes(e)}
    assert [r["id"] for r in _lignes(e, statut_suivi="RISQUE_ACCEPTE")] != []
    assert all(r["statut_suivi"] == "A_LANCER" for r in _lignes(e, statut_suivi="A_LANCER"))
    assert _lignes(e, statut_suivi="REALISEE") == []
    assert _lignes(e, en_retard="true") == []
    assert len(_lignes(e, en_retard="false")) == 3
    assert _lignes(e, annee=e.mission.annee)
    assert _lignes(e, annee=2001) == []
    assert all(r["priorite"] == ligne["priorite"] for r in _lignes(e, priorite=ligne["priorite"]))
    assert _lignes(e, entite=ligne["entite"]["id"])
    for tri in ("prochaine_echeance", "-prochaine_echeance", "priorite", "-priorite"):
        assert len(_lignes(e, ordering=tri)) == 3


def test_registre_en_retard(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    # échéance courante repoussée sous la date du jour impossible (échéance >= initiale) :
    # on utilise une action créée avec une échéance passée.
    forcer_etapes(e.mission, {16: StatutEtape.EN_COURS})
    passe = SuiviActionFactory(
        action=ActionFactory(
            recommandation=s.recommandation,
            responsable=e.users["responsable"],
            proposee_par=e.users["chef"],
            echeance=datetime.date.today() - datetime.timedelta(days=5),
        )
    )
    forcer_etapes(e.mission, {16: StatutEtape.VALIDEE})
    lignes = _lignes(e, en_retard="true")
    assert [r["id"] for r in lignes] == [str(s.recommandation_id)]
    assert lignes[0]["actions_en_retard"] == 1
    assert lignes[0]["prochaine_echeance"] == str(passe.echeance)


def test_registre_requetes_bornees(
    equipe_suivi: EquipeSuivi, django_assert_max_num_queries: Any
) -> None:
    e = equipe_suivi
    for qui in ("rai", "auditeur", "dg"):
        client = client_de(e.users[qui])
        with django_assert_max_num_queries(5):
            assert client.get(RECOMMANDATIONS, {"page_size": 50}).status_code == 200


def test_registre_visibilite_et_detail(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    reco: Recommandation = e.suivi.recommandation
    for qui in ("rai", "dg", "auditeur", "responsable", "audite"):
        r = client_de(e.users[qui]).get(f"{RECOMMANDATIONS}{reco.pk}/")
        assert r.status_code == 200, qui
        assert r.json()["id"] == str(reco.pk)
    for qui in ("non_affecte", "audite_non_affecte"):
        client = client_de(e.users[qui])
        assert client.get(f"{RECOMMANDATIONS}{reco.pk}/").status_code == 404
        assert client.get(RECOMMANDATIONS).json()["results"] == []
    assert client_de(e.users["admin"]).get(RECOMMANDATIONS).status_code == 403
