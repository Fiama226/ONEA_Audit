import datetime as dt
import uuid

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.analyse.models import EvaluationConception
from apps.analyse.services import referentiel as svc_referentiel
from apps.missions.models import EtapeMission, StatutEtape
from tests.factories import (
    AvisAuditeFactory,
    ForceFaiblesseFactory,
    LigneMARCFactory,
    RisqueMissionFactory,
)

from .fixtures_api import EquipeVI, equipe_complete, equipe_en_vi, travaux_ouverts  # noqa: F401


def test_marc_cycle_et_synchronisation_des_forces_faiblesses(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
) -> None:
    m, users, risque = equipe_en_vi
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/marc-lines/", {"mission": str(m.id), "risque": str(risque.id)}, format="json"
    )
    assert r.status_code == 201, r.json()
    ligne = r.json()
    assert ligne["risque_niveau"] == "ELEVE"
    assert ligne["risque_score"] == 20
    assert ligne["a_objectif"] is False
    assert ligne["appreciation"] is None
    lid = ligne["id"]
    r = api_client.patch(
        f"/api/v1/marc-lines/{lid}/",
        {"evaluation": "ABSENTE", "composante": "ACTIVITE"},
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert r.json()["appreciation"] == "FAIBLESSE"
    # La faiblesse liée apparaît, en lecture seule.
    r = api_client.get(f"/api/v1/strengths-weaknesses/?mission={m.id}&type=FAIBLESSE")
    assert r.json()["count"] == 1
    liee = r.json()["results"][0]
    assert liee["liee"] is True
    assert liee["ligne_marc"] == lid
    r = api_client.delete(f"/api/v1/strengths-weaknesses/{liee['id']}/")
    assert r.status_code == 422
    # Règle D7 : évaluation « adéquate » sans contrôle existant, 422 sur le champ.
    r = api_client.patch(f"/api/v1/marc-lines/{lid}/", {"evaluation": "ADEQUATE"}, format="json")
    assert r.status_code == 422
    assert "controle_existant" in r.json()["errors"]
    # Le risque est fixé à la création.
    with travaux_ouverts(m):
        autre = RisqueMissionFactory(mission=m, processus=risque.processus)
    r = api_client.patch(f"/api/v1/marc-lines/{lid}/", {"risque": str(autre.id)}, format="json")
    assert r.status_code == 400
    assert api_client.delete(f"/api/v1/marc-lines/{lid}/").status_code == 204


def test_marc_initialize_et_filtres(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    m, users, risque = equipe_en_vi
    with travaux_ouverts(m):
        RisqueMissionFactory(mission=m, processus=risque.processus, probabilite=1, impact=1)
    api_client.force_authenticate(users["rai"])
    r = api_client.post("/api/v1/marc-lines/initialize/", {"mission": str(m.id)}, format="json")
    assert r.status_code == 200, r.json()
    assert len(r.json()) == 2
    assert (
        api_client.post(
            "/api/v1/marc-lines/initialize/", {"mission": str(m.id)}, format="json"
        ).json()
        == []
    )
    r = api_client.get(f"/api/v1/marc-lines/?mission={m.id}&ordering=-risque__score")
    assert [x["risque_score"] for x in r.json()["results"]] == [20, 1]
    r = api_client.get(f"/api/v1/marc-lines/?mission={m.id}&risque={risque.id}")
    assert r.json()["count"] == 1
    r = api_client.get(f"/api/v1/marc-lines/?mission={m.id}&cle=true")
    assert r.json()["count"] == 0
    r = api_client.post("/api/v1/marc-lines/initialize/", {}, format="json")
    assert r.status_code == 400


def test_force_faiblesse_manuelle(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    m, users, _ = equipe_en_vi
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/strengths-weaknesses/",
        {"mission": str(m.id), "type": "FORCE", "libelle": "Séparation des tâches"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["liee"] is False
    fid = r.json()["id"]
    r = api_client.patch(
        f"/api/v1/strengths-weaknesses/{fid}/", {"type": "FAIBLESSE"}, format="json"
    )
    assert r.status_code == 200
    assert api_client.delete(f"/api/v1/strengths-weaknesses/{fid}/").status_code == 204


def test_avis_remarques_sans_commentaire_422(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
) -> None:
    m, users, _ = equipe_en_vi
    api_client.force_authenticate(users["audite_affecte"])
    r = api_client.post(
        f"/api/v1/audit-frameworks/{m.id}/opinions/", {"avis": "REMARQUES"}, format="json"
    )
    assert r.status_code == 422
    assert "commentaire" in r.json()["errors"]
    r = api_client.post(
        f"/api/v1/audit-frameworks/{m.id}/opinions/",
        {"avis": "REMARQUES", "commentaire": "À revoir."},
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["auteur"]["id"] == users["audite_affecte"].id
    assert (
        api_client.post(
            f"/api/v1/audit-frameworks/{m.id}/opinions/", {"avis": "X"}, format="json"
        ).status_code
        == 400
    )


def test_snapshot_404_puis_200(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    m, users, risque = equipe_en_vi
    with travaux_ouverts(m):
        LigneMARCFactory(mission=m, risque=risque)
    api_client.force_authenticate(users["rai"])
    assert api_client.get(f"/api/v1/audit-frameworks/{m.id}/snapshot/").status_code == 404
    svc_referentiel.figer_referentiel(m, by=users["rai"])
    EtapeMission.objects.filter(mission=m, numero=6).update(statut=StatutEtape.VALIDEE)
    r = api_client.get(f"/api/v1/audit-frameworks/{m.id}/snapshot/")
    assert r.status_code == 200, r.json()
    assert r.json()["donnees"]["mission"]["reference"] == m.reference
    assert r.json()["confirmation"]["type_document"] == "VALIDATION_REFERENTIEL"
    synthese = api_client.get(f"/api/v1/audit-frameworks/{m.id}/").json()
    assert synthese["statut"] == "VALIDE"
    assert synthese["validation_verifiee"] is True
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.get(f"/api/v1/audit-frameworks/{m.id}/snapshot/").status_code == 200


def test_listes_requetes_bornees(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    m, users, risque = equipe_en_vi
    with travaux_ouverts(m):
        for _ in range(3):
            ligne = LigneMARCFactory(
                mission=m,
                risque=RisqueMissionFactory(mission=m, processus=risque.processus),
                controle_existant="Contrôle.",
                evaluation=EvaluationConception.ADEQUATE,
            )
            ForceFaiblesseFactory(mission=m, ligne_marc=ligne, type="FORCE")
        AvisAuditeFactory(mission=m, auteur=users["audite_affecte"])
    api_client.force_authenticate(users["rai"])
    for url, budget in (
        (f"/api/v1/marc-lines/?mission={m.id}", 5),
        (f"/api/v1/strengths-weaknesses/?mission={m.id}", 4),
        (f"/api/v1/audit-frameworks/{m.id}/", 8),
    ):
        with CaptureQueriesContext(connection) as q:
            r = api_client.get(url)
        assert r.status_code == 200, r.json()
        assert len(q) <= budget, (url, len(q), [x["sql"][:120] for x in q.captured_queries])


def test_droits_analyse_concordent_avec_les_routes(
    api_client: APIClient,
    equipe_en_vi: EquipeVI,  # noqa: F811
) -> None:
    m, users, risque = equipe_en_vi
    for qui in ("rai", "chef", "auditeur_non_confirme", "audite_affecte"):
        api_client.force_authenticate(users[qui])
        droits = api_client.get(f"/api/v1/audit-frameworks/{m.id}/").json()["mes_droits"]
        lire = api_client.get(f"/api/v1/marc-lines/?mission={m.id}").status_code
        assert (lire != 403) is droits["voir_referentiel"], qui
        r = api_client.post(
            "/api/v1/marc-lines/",
            {"mission": str(m.id), "risque": str(risque.id), "ordre": 99},
            format="json",
        )
        if droits["contribuer_v"]:
            assert r.status_code == 201, (qui, r.json())
            api_client.delete(f"/api/v1/marc-lines/{r.json()['id']}/")
        else:
            assert r.status_code in (403, 422), qui
        r = api_client.post(
            f"/api/v1/audit-frameworks/{m.id}/opinions/", {"avis": "ACCORD"}, format="json"
        )
        assert (r.status_code == 201) is droits["donner_avis"], qui
        # Étape III close : plus aucun droit de contribuer à la prise de connaissance.
        assert droits["contribuer_iii"] is False, qui
        assert droits["contribuer_vii"] is False, qui


def test_api_contrat_referentiel(api_client: APIClient, equipe_en_vi: EquipeVI) -> None:  # noqa: F811
    """JSON exact d'une synthèse SOUMIS ; recopié tel quel dans les fixtures MSW de T10."""
    m, users, risque = equipe_en_vi
    with travaux_ouverts(m):
        ligne_f = LigneMARCFactory(
            mission=m,
            risque=risque,
            controle_existant="Double signature.",
            evaluation=EvaluationConception.ADEQUATE,
        )
        ligne_w = LigneMARCFactory(
            mission=m,
            risque=RisqueMissionFactory(
                mission=m, processus=risque.processus, probabilite=1, impact=1
            ),
            evaluation=EvaluationConception.ABSENTE,
        )
        ForceFaiblesseFactory(mission=m, ligne_marc=ligne_f, type="FORCE")
        ForceFaiblesseFactory(mission=m, ligne_marc=ligne_w, type="FAIBLESSE")
        AvisAuditeFactory(
            id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
            mission=m,
            auteur=users["audite_affecte"],
            avis="ACCORD",
            donne_le=dt.datetime(2026, 3, 20, 9, 0, tzinfo=dt.UTC),
        )
    EtapeMission.objects.filter(mission=m, numero=6).update(statut=StatutEtape.TERMINEE)
    api_client.force_authenticate(users["rai"])
    r = api_client.get(f"/api/v1/audit-frameworks/{m.id}/")
    assert r.status_code == 200, r.json()
    corps = r.json()
    auteur = corps["avis"][0]["auteur"]
    attendu = {
        "mission": str(m.id),
        "statut": "SOUMIS",
        "statut_v": "TERMINEE",
        "statut_vi": "TERMINEE",
        "nb_lignes": 2,
        "nb_forces": 1,
        "nb_faiblesses": 1,
        "risques_non_couverts": [],
        "validation": None,
        "validation_verifiee": False,
        "avis": [
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "auteur": auteur,
                "avis": "ACCORD",
                "commentaire": "",
                "donne_le": "2026-03-20T09:00:00Z",
            }
        ],
        "mes_droits": {
            "voir_travaux": True,
            "contribuer_iii": False,
            "contribuer_v": False,
            "donner_avis": False,
            "voir_referentiel": True,
            "contribuer_vii": False,
        },
    }
    assert corps == attendu
    assert set(auteur) == {"id", "username", "nom_complet", "role", "direction_code", "fonction"}
    assert auteur["role"] == "AUDITE"
