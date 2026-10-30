import datetime

import pytest

from apps.missions.models import StatutEtape
from apps.recommandations.models import Action
from apps.users.models import Role
from tests.accomplissement.fixtures_api import client_de
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes
from tests.recommandations.factories import ActionFactory
from tests.recommandations.fixtures_api import (
    ACCEPTATIONS,
    ACTIONS,
    ENGAGEMENTS,
    EquipePlan,
    equipe_plan,
)

# ruff: noqa: F811, F401
pytestmark = pytest.mark.django_db

ROLES = (
    "rai",
    "chef",
    "auditeur",
    "superviseur",
    "audite_a",
    "audite_b",
    "non_affecte",
    "audite_non_affecte",
    "admin",
    "dg",
)

# rôle -> statut attendu, par opération (D8, D13)
LIRE = dict.fromkeys(ROLES, 200) | {
    "non_affecte": 404,
    "audite_non_affecte": 404,
    "admin": 403,
    "dg": 403,
}
CREER = dict.fromkeys(("rai", "chef", "auditeur", "superviseur", "audite_a"), 201) | {
    "audite_b": 404,
    "non_affecte": 404,
    "audite_non_affecte": 404,
    "admin": 403,
    "dg": 403,
}
MODIFIER = dict.fromkeys(("rai", "chef", "auditeur", "superviseur"), 200) | {
    "audite_a": 403,
    "audite_b": 404,
    "non_affecte": 404,
    "audite_non_affecte": 404,
    "admin": 403,
    "dg": 403,
}
ACCEPTER = dict.fromkeys(ROLES, 403) | {
    "audite_a": 404,
    "audite_b": 201,
    "audite_non_affecte": 404,
}
ENGAGER = dict.fromkeys(ROLES, 403) | {"audite_a": 201, "audite_b": 422, "audite_non_affecte": 404}


def _lire(e: EquipePlan, qui: str) -> int:
    return client_de(e.users[qui]).get(f"{ACTIONS}?mission={e.mission.pk}").status_code


def _creer(e: EquipePlan, qui: str) -> int:
    corps = {"recommandation": str(e.recommandations[0].pk), "libelle": "Nouvelle mesure."}
    return client_de(e.users[qui]).post(ACTIONS, corps, format="json").status_code


def _modifier(e: EquipePlan, qui: str) -> int:
    url = f"{ACTIONS}{e.action_a.pk}/"
    return client_de(e.users[qui]).patch(url, {"indicateur": "KPI"}, format="json").status_code


def _accepter(e: EquipePlan, qui: str) -> int:
    corps = {
        "recommandation": str(e.recommandations[2].pk),
        "justification": "Coût disproportionné.",
        "confirme": True,
    }
    return client_de(e.users[qui]).post(ACCEPTATIONS, corps, format="json").status_code


def _engager(e: EquipePlan, qui: str) -> int:
    corps = {"mission": str(e.mission.pk), "confirme": True}
    return client_de(e.users[qui]).post(ENGAGEMENTS, corps, format="json").status_code


OPERATIONS = {
    "lire": (_lire, LIRE),
    "creer": (_creer, CREER),
    "modifier": (_modifier, MODIFIER),
    "accepter": (_accepter, ACCEPTER),
    "engager": (_engager, ENGAGER),
}


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("qui", ROLES)
def test_matrice_droits_plan(equipe_plan: EquipePlan, operation: str, qui: str) -> None:
    appel, attendu = OPERATIONS[operation]
    assert appel(equipe_plan, qui) == attendu[qui], f"{operation} / {qui}"


def test_creation_serialisee(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    r = client_de(e.users["chef"]).post(
        ACTIONS,
        {
            "recommandation": str(e.recommandations[0].pk),
            "libelle": "  Rédiger la note.  ",
            "responsable": e.users["audite_a"].pk,
            "echeance": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["libelle"] == "Rédiger la note."
    assert corps["reference"] == "A-03" and corps["statut"] == "A_LANCER"
    assert corps["mission"] == str(e.mission.pk)
    assert corps["responsable_detail"]["id"] == e.users["audite_a"].pk
    assert corps["proposee_par"] == e.users["chef"].pk
    assert corps["constat_reference"] == e.recommandations[0].constat.reference
    assert corps["actions_possibles"] == ["MODIFIER", "SUPPRIMER"]


def test_creation_erreurs(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    chef = client_de(e.users["chef"])
    base = {"recommandation": str(e.recommandations[0].pk), "libelle": "M"}
    sans_reco = chef.post(ACTIONS, {"libelle": "M"}, format="json")
    assert sans_reco.status_code == 400 and "recommandation" in sans_reco.json()["errors"]
    sans_libelle = chef.post(ACTIONS, {"recommandation": base["recommandation"]}, format="json")
    assert sans_libelle.status_code == 400
    assert (
        chef.post(ACTIONS, {**base, "recommandation": "pas-un-uuid"}, format="json").status_code
        == 400
    )
    hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    r = chef.post(ACTIONS, {**base, "echeance": hier}, format="json")
    assert r.status_code == 422 and set(r.json()) == {"detail", "errors"}
    r = chef.post(ACTIONS, {**base, "responsable": e.users["rai"].pk}, format="json")
    assert r.status_code == 422
    r = chef.post(ACTIONS, {**base, "libelle": "   "}, format="json")
    assert r.status_code == 400


def test_modification_refus_changer_recommandation_et_audite_proprietaire(
    equipe_plan: EquipePlan,
) -> None:
    e = equipe_plan
    url = f"{ACTIONS}{e.action_resp.pk}/"
    chef = client_de(e.users["chef"])
    autre = str(e.recommandations[0].pk)
    assert chef.patch(url, {"recommandation": autre}, format="json").status_code == 400
    # l'audité responsable de l'action (entité A) peut la modifier ; pas statut ni proposee_par
    audite = client_de(e.users["audite_a"])
    r = audite.patch(url, {"indicateur": "Taux de formation", "statut": "REALISEE"}, format="json")
    assert r.status_code == 200, r.json()
    assert r.json()["indicateur"] == "Taux de formation" and r.json()["statut"] == "A_LANCER"


def test_suppression_logique(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    r = client_de(e.users["chef"]).delete(f"{ACTIONS}{e.action_a.pk}/")
    assert r.status_code == 204
    assert not Action.objects.filter(pk=e.action_a.pk).exists()
    assert Action.all_objects.filter(pk=e.action_a.pk, deleted_at__isnull=False).exists()


def test_filtres_et_perimetre(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    rai = client_de(e.users["rai"])
    base = f"{ACTIONS}?mission={e.mission.pk}"
    assert rai.get(base).json()["count"] == 2
    assert rai.get(f"{base}&recommandation={e.recommandations[0].pk}").json()["count"] == 1
    assert rai.get(f"{base}&constat={e.recommandations[0].constat_id}").json()["count"] == 2
    assert rai.get(f"{base}&responsable={e.users['audite_a'].pk}").json()["count"] == 1
    assert rai.get(f"{base}&ordering=-echeance").status_code == 200
    audite = client_de(e.users["audite_a"])
    assert audite.get(f"{base}&mine=true").json()["count"] == 1
    assert audite.get(f"{base}&mine=false").json()["count"] == 1
    # une action d'une autre entité est invisible : 404, jamais 403
    autre = ActionFactory(
        recommandation=e.recommandations[2],
        proposee_par=e.users["chef"],
        responsable=e.users["audite_b"],
    )
    assert audite.get(f"{ACTIONS}{autre.pk}/").status_code == 404
    assert audite.get(base).json()["count"] == 2
    assert client_de(e.users["audite_b"]).get(base).json()["count"] == 1


def test_liste_exige_une_mission_visible(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    rai = client_de(e.users["rai"])
    assert rai.get(ACTIONS).status_code == 400
    assert rai.get(f"{ACTIONS}?mission=xyz").status_code == 400
    assert rai.get(f"{ACTIONS}?mission=00000000-0000-0000-0000-000000000000").status_code == 404


def test_actions_possibles_concorde_avec_les_routes(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    for qui in ("rai", "chef", "auditeur", "superviseur", "audite_a", "audite_b"):
        client = client_de(e.users[qui])
        liste = client.get(f"{ACTIONS}?mission={e.mission.pk}").json()["results"]
        for ligne in liste:
            r = client.patch(f"{ACTIONS}{ligne['id']}/", {"moyens": "Temps"}, format="json")
            attendu = 200 if "MODIFIER" in ligne["actions_possibles"] else 403
            assert r.status_code == attendu, (qui, ligne["reference"], ligne["actions_possibles"])
        for ligne in liste:  # les suppressions en dernier : elles retirent l'action
            r = client.delete(f"{ACTIONS}{ligne['id']}/")
            attendu = 204 if "SUPPRIMER" in ligne["actions_possibles"] else 403
            assert r.status_code == attendu, (qui, ligne["reference"])


def test_api_gel_422_routes_plan(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    forcer_etapes(e.mission, {16: StatutEtape.TERMINEE})
    chef = client_de(e.users["chef"])
    liste = chef.get(f"{ACTIONS}?mission={e.mission.pk}").json()["results"]
    assert all(ligne["actions_possibles"] == [] for ligne in liste)
    assert _creer(e, "chef") == 422
    assert _modifier(e, "chef") == 422
    assert chef.delete(f"{ACTIONS}{e.action_a.pk}/").status_code == 422
    assert _accepter(e, "audite_b") == 422
    assert _engager(e, "audite_a") == 422
    # le droit reste évalué avant le gel : l'audité d'une autre entité ne voit rien (404)
    assert _modifier(e, "audite_b") == 404
    assert _modifier(e, "audite_a") == 403


def test_listes_requetes_bornees(equipe_plan: EquipePlan, django_assert_max_num_queries) -> None:  # type: ignore[no-untyped-def]
    e = equipe_plan
    for _ in range(50):
        ActionFactory(
            recommandation=e.recommandations[0],
            proposee_par=e.users["chef"],
            responsable=e.users["audite_a"],
        )
    for qui in ("chef", "audite_a"):
        client = client_de(e.users[qui])
        with django_assert_max_num_queries(6):
            r = client.get(f"{ACTIONS}?mission={e.mission.pk}&page_size=50")
        assert r.status_code == 200
        assert len(r.json()["results"]) >= 20


def test_utilisateur_inconnu_de_la_mission_ne_peut_pas_etre_responsable(
    equipe_plan: EquipePlan,
) -> None:
    e = equipe_plan
    etranger = make_user(Role.AUDITE)
    r = client_de(e.users["chef"]).patch(
        f"{ACTIONS}{e.action_a.pk}/", {"responsable": etranger.pk}, format="json"
    )
    assert r.status_code == 422
