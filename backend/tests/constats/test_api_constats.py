import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.constats.models import CauseConstat, Constat, Recommandation
from tests.accomplissement.fixtures_api import client_de
from tests.constats.factories import ConstatFactory, fiche_anomalie
from tests.constats.fixtures_api import EquipeConstats, equipe_constats  # noqa: F401
from tests.factories import DirectionFactory, ProcessusFactory
from apps.missions.models import StatutEtape
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db
URL = "/api/v1/findings/"


def test_creation_puis_cycle_complet(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    chef = client_de(e.users["chef"])
    fiche = fiche_anomalie(e.mission)
    entite, processus = DirectionFactory(), ProcessusFactory()
    forcer_etapes(e.mission, {1: StatutEtape.EN_COURS})
    e.mission.entites.add(entite)
    e.mission.processus.add(processus)
    forcer_etapes(e.mission, {1: StatutEtape.VALIDEE})
    r = chef.post(
        URL,
        {
            "mission": str(e.mission.pk),
            "titre": "Absence de rapprochement",
            "entite": str(entite.pk),
            "processus": str(processus.pk),
            "fiches": [str(fiche.pk)],
            "fait_constate": "Pas de rapprochement.",
            "referentiel": "Procédure",
            "consequence": "Erreurs",
            "conclusion": "Insuffisant",
            "probabilite": 3,
            "impact": 4,
            "causes": [{"categorie": "METHODES", "description": "Pas de procédure"}],
            "recommandations": [{"libelle": "Formaliser", "priorite": "HAUTE"}],
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["reference"] == "C-03"
    assert corps["score"] == 12 and corps["niveau"] == "MOYEN"
    assert len(corps["causes"]) == 1 and len(corps["recommandations"]) == 1
    assert corps["fiches_detail"][0]["test_code"]
    assert "SOUMETTRE" in corps["actions_possibles"]
    pk = corps["id"]
    r = chef.post(f"{URL}{pk}/submit/")
    assert r.status_code == 200 and r.json()["statut"] == "SOUMIS", r.json()
    rai = client_de(e.users["rai"])
    assert chef.post(f"{URL}{pk}/validate/").status_code == 403
    r = rai.post(f"{URL}{pk}/return/", {}, format="json")
    assert r.status_code == 400
    r = rai.post(f"{URL}{pk}/return/", {"motif": "Précisez"}, format="json")
    assert r.status_code == 200 and r.json()["motif_renvoi"] == "Précisez"
    assert chef.post(f"{URL}{pk}/submit/").status_code == 200
    r = rai.post(f"{URL}{pk}/validate/")
    assert r.status_code == 200 and r.json()["statut"] == "VALIDE"
    r = rai.post(f"{URL}{pk}/reopen/", {"motif": "Erreur"}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "BROUILLON"
    assert chef.delete(f"{URL}{pk}/").status_code == 204
    assert chef.get(f"{URL}{pk}/").status_code == 404


def test_patch_remplace_causes_et_recommandations(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    c = e.brouillon
    chef = client_de(e.users["chef"])
    ancienne = CauseConstat.objects.get(constat=c)
    r = chef.patch(
        f"{URL}{c.pk}/",
        {
            "causes": [
                {"id": str(ancienne.pk), "categorie": "MATERIEL", "description": "Modifiée"},
                {"categorie": "MILIEU", "description": "Nouvelle"},
            ],
            "recommandations": [],
        },
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert [x["description"] for x in r.json()["causes"]] == ["Modifiée", "Nouvelle"]
    assert r.json()["recommandations"] == []
    assert Recommandation.objects.filter(constat=c).count() == 0
    assert CauseConstat.objects.filter(constat=c).count() == 2


def test_audite_ne_voit_que_les_constats_soumis(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"])
    assert audite.get(f"{URL}{e.brouillon.pk}/").status_code == 404
    r = audite.get(f"{URL}?mission={e.mission.pk}")
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["results"]] == [str(e.soumis.pk)]
    # entité d'un autre : invisible
    autre = client_de(e.users["autre_audite"])
    assert autre.get(f"{URL}{e.soumis.pk}/").status_code == 404
    assert autre.get(f"{URL}?mission={e.mission.pk}").json()["count"] == 0
    # mission invisible
    r = client_de(e.users["audite_non_affecte"]).get(f"{URL}?mission={e.mission.pk}")
    assert r.status_code == 404


def test_audite_champs_internes_nuls(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    r = client_de(e.users["audite"]).get(f"{URL}{e.soumis.pk}/")
    assert r.status_code == 200
    corps = r.json()
    assert corps["fiches_detail"] is None
    assert corps["motif_renvoi"] is None
    assert corps["risque_mission"] is None
    assert corps["empreinte_soumise"] == e.soumis.empreinte_soumise
    assert "en accord" in corps["texte_reponse"]["accord"]
    assert "en désaccord" in corps["texte_reponse"]["desaccord"]
    assert corps["actions_possibles"] == ["REPONDRE"]
    assert corps["derniere_reponse"] is None and corps["reponse_cycle_courant"] is False
    interne = client_de(e.users["chef"]).get(f"{URL}{e.soumis.pk}/").json()
    assert interne["fiches_detail"] and interne["texte_reponse"] is None


def test_audite_ecritures_refusees(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"])
    assert audite.patch(f"{URL}{e.soumis.pk}/", {"titre": "x"}, format="json").status_code == 403
    assert audite.post(f"{URL}{e.soumis.pk}/validate/").status_code == 403
    assert audite.delete(f"{URL}{e.soumis.pk}/").status_code == 403
    r = audite.post(URL, {"mission": str(e.mission.pk)}, format="json")
    assert r.status_code == 403


def test_actions_possibles_concorde_avec_les_routes(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    chef = client_de(e.users["chef"])
    corps = chef.get(f"{URL}{e.brouillon.pk}/").json()
    assert set(corps["actions_possibles"]) == {"MODIFIER", "SUPPRIMER", "SOUMETTRE"}
    assert chef.get(f"{URL}{e.soumis.pk}/").json()["actions_possibles"] == []
    rai = client_de(e.users["rai"])
    assert set(rai.get(f"{URL}{e.soumis.pk}/").json()["actions_possibles"]) == {
        "VALIDER",
        "RENVOYER",
    }
    assert rai.post(f"{URL}{e.soumis.pk}/validate/").status_code == 200
    assert rai.get(f"{URL}{e.soumis.pk}/").json()["actions_possibles"] == ["ROUVRIR"]
    auditeur = client_de(e.users["auditeur"])
    assert "SOUMETTRE" not in auditeur.get(f"{URL}{e.brouillon.pk}/").json()["actions_possibles"]
    assert auditeur.post(f"{URL}{e.brouillon.pk}/submit/").status_code == 403


def test_api_gel_422_routes_lot6(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    chef = client_de(e.users["chef"])
    forcer_etapes(e.mission, {14: "TERMINEE"})
    r = chef.patch(f"{URL}{e.brouillon.pk}/", {"titre": "Nouveau"}, format="json")
    assert r.status_code == 422 and set(r.json()) == {"detail", "errors"}
    assert chef.post(f"{URL}{e.brouillon.pk}/submit/").status_code == 422
    assert chef.delete(f"{URL}{e.brouillon.pk}/").status_code == 422
    assert Constat.objects.filter(pk=e.brouillon.pk).exists()


def test_filtres_et_a_repondre(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    rai = client_de(e.users["rai"])
    base = f"{URL}?mission={e.mission.pk}"
    assert rai.get(base).json()["count"] == 2
    assert rai.get(f"{base}&statut=SOUMIS").json()["count"] == 1
    assert rai.get(f"{base}&entite={e.soumis.entite_id}").json()["count"] == 1
    assert rai.get(f"{base}&ordering=-score").status_code == 200
    audite = client_de(e.users["audite"])
    assert audite.get(f"{base}&a_repondre=true").json()["count"] == 1
    assert audite.get(f"{base}&a_repondre=false").json()["count"] == 0
    assert rai.get(URL).status_code == 400  # mission obligatoire


def test_listes_requetes_bornees(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    for _ in range(28):
        ConstatFactory(mission=e.mission)
    rai = client_de(e.users["rai"])
    with CaptureQueriesContext(connection) as ctx:
        r = rai.get(f"{URL}?mission={e.mission.pk}&page_size=50")
    assert r.status_code == 200 and r.json()["count"] == 30
    assert len(ctx) <= 6, '
'.join(q['sql'].split(' FROM ')[1][:70] for q in ctx.captured_queries)


def test_erreurs_au_format_unique(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    for reponse in (
        client_de(e.users["rai"]).get(f"{URL}00000000-0000-0000-0000-000000000000/"),
        client_de(e.users["admin"]).get(f"{URL}?mission={e.mission.pk}"),
        client_de(e.users["non_affecte"]).get(f"{URL}{e.soumis.pk}/"),
    ):
        assert set(reponse.json()) == {"detail", "errors"}
