from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.referentiel.models import CartographieVersion, StatutCartographie
from apps.users.models import Role, User
from tests.factories import (
    CartographieVersionFactory,
    EntretienFactory,
    ReunionFactory,
    RisqueFactory,
    RisqueMissionFactory,
    make_user,
)

Equipe = tuple[Mission, dict[str, User]]


def _reunion_corps(m: Mission, **extra: object) -> dict[str, object]:
    return {"mission": str(m.id), "type": "OUVERTURE", "date": "2026-03-02T09:00:00Z", **extra}


# ------------------------------------------------------------------ réunions


def test_reunion_cycle(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/meetings/",
        _reunion_corps(m, participants=[users["rai"].id], participants_externes="M. Sawadogo"),
        format="json",
    )
    assert r.status_code == 201, r.json()
    rid = r.json()["id"]
    assert r.json()["participants_detail"][0]["id"] == users["rai"].id
    assert r.json()["etape_close"] is False
    # Doublon de type : 422 posé sur le champ.
    r2 = api_client.post("/api/v1/meetings/", _reunion_corps(m), format="json")
    assert r2.status_code == 422
    assert "type" in r2.json()["errors"]
    # Le type et la mission ne changent pas.
    assert (
        api_client.patch(f"/api/v1/meetings/{rid}/", {"type": "CLOTURE"}, format="json").status_code
        == 400
    )
    # Marquer tenue sans compte rendu : 422.
    assert api_client.post(f"/api/v1/meetings/{rid}/mark-held/").status_code == 422
    r = api_client.patch(
        f"/api/v1/meetings/{rid}/", {"compte_rendu": "Ouverture réalisée."}, format="json"
    )
    assert r.status_code == 200, r.json()
    r = api_client.post(f"/api/v1/meetings/{rid}/mark-held/")
    assert r.status_code == 200, r.json()
    assert r.json()["tenue_le"] is not None


def test_reunion_etape_close_et_filtres(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    reunion = ReunionFactory(mission=m, type="OUVERTURE", date=timezone.now() - timedelta(days=1))
    EtapeMission.objects.filter(mission=m, numero=2).update(statut=StatutEtape.TERMINEE)
    api_client.force_authenticate(users["audite_affecte"])
    r = api_client.get(f"/api/v1/meetings/?mission={m.id}&type=OUVERTURE")
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["results"]] == [str(reunion.id)]
    assert r.json()["results"][0]["etape_close"] is True
    assert api_client.get("/api/v1/meetings/?type=CLOTURE").json()["count"] == 0
    api_client.force_authenticate(users["chef"])
    r = api_client.patch(f"/api/v1/meetings/{reunion.id}/", {"lieu": "X"}, format="json")
    assert r.status_code == 422


def test_reunion_audite_ecriture_403_et_suppression(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    reunion = ReunionFactory(mission=m, type="LANCEMENT")
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.delete(f"/api/v1/meetings/{reunion.id}/").status_code == 403
    api_client.force_authenticate(users["auditeur_non_confirme"])
    assert api_client.delete(f"/api/v1/meetings/{reunion.id}/").status_code == 403
    api_client.force_authenticate(users["auditeur_non_affecte"])
    assert api_client.delete(f"/api/v1/meetings/{reunion.id}/").status_code == 404
    api_client.force_authenticate(users["rai"])
    assert api_client.delete(f"/api/v1/meetings/{reunion.id}/").status_code == 204


# ------------------------------------------------------------------ entretiens


def _entretien_corps(m: Mission, **extra: object) -> dict[str, object]:
    return {
        "mission": str(m.id),
        "objet": "Entretien DAF",
        "date_prevue": "2026-03-04T09:00:00Z",
        **extra,
    }


def test_entretien_cycle(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["auditeur_confirme"])
    etape2 = EtapeMission.objects.get(mission=m, numero=2)
    r = api_client.post(
        "/api/v1/interviews/",
        _entretien_corps(
            m,
            etape=str(etape2.id),
            auditeurs=[users["auditeur_confirme"].id],
            interlocuteurs=[users["audite_affecte"].id],
            duree_minutes=60,
        ),
        format="json",
    )
    assert r.status_code == 201, r.json()
    eid = r.json()["id"]
    assert r.json()["etape_romain"] == "II"
    assert r.json()["statut"] == "PLANIFIE"
    assert r.json()["interlocuteurs_detail"][0]["id"] == users["audite_affecte"].id
    assert api_client.post(f"/api/v1/interviews/{eid}/mark-done/").status_code == 422
    api_client.patch(f"/api/v1/interviews/{eid}/", {"compte_rendu": "Fait."}, format="json")
    r = api_client.post(f"/api/v1/interviews/{eid}/mark-done/")
    assert r.status_code == 200, r.json()
    assert r.json()["statut"] == "REALISE"
    assert (
        api_client.post(
            f"/api/v1/interviews/{eid}/cancel/", {"motif": "x"}, format="json"
        ).status_code
        == 422
    )
    # Une durée hors bornes est refusée.
    r = api_client.post("/api/v1/interviews/", _entretien_corps(m, duree_minutes=0), format="json")
    assert r.status_code in (400, 422)
    # Les auditeurs doivent faire partie de l'équipe.
    r = api_client.post(
        "/api/v1/interviews/",
        _entretien_corps(m, auditeurs=[users["auditeur_non_affecte"].id]),
        format="json",
    )
    assert r.status_code == 422
    assert "auditeurs" in r.json()["errors"]


def test_entretien_annulation(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    entretien = EntretienFactory(mission=m)
    api_client.force_authenticate(users["chef"])
    route = f"/api/v1/interviews/{entretien.id}/cancel/"
    assert api_client.post(route, {}, format="json").status_code == 400
    r = api_client.post(route, {"motif": "Indisponible"}, format="json")
    assert r.status_code == 200
    assert r.json()["motif_annulation"] == "Indisponible"
    assert api_client.get("/api/v1/interviews/?statut=ANNULE").json()["count"] == 1


def test_audite_ne_voit_que_ses_entretiens(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    le_sien = EntretienFactory(mission=m, compte_rendu="Interne", note_synthese="Note interne")
    le_sien.interlocuteurs.add(users["audite_affecte"])
    EntretienFactory(mission=m)
    api_client.force_authenticate(users["audite_affecte"])
    r = api_client.get(f"/api/v1/interviews/?mission={m.id}")
    assert [x["id"] for x in r.json()["results"]] == [str(le_sien.id)]
    # Les notes internes de l'équipe ne sont pas communiquées.
    assert r.json()["results"][0]["compte_rendu"] == ""
    assert r.json()["results"][0]["note_synthese"] == ""
    assert api_client.get(f"/api/v1/interviews/{le_sien.id}/").status_code == 200
    autre = EntretienFactory(mission=m)
    assert api_client.get(f"/api/v1/interviews/{autre.id}/").status_code == 404
    api_client.force_authenticate(users["chef"])
    assert api_client.get(f"/api/v1/interviews/?mission={m.id}").json()["count"] == 3
    assert api_client.get(f"/api/v1/interviews/{le_sien.id}/").json()["compte_rendu"] == "Interne"


# ------------------------------------------------------------------ risques de mission


def _ouvrir_etape_iv(m: Mission) -> None:
    EtapeMission.objects.filter(mission=m, numero=4).update(statut=StatutEtape.EN_COURS)


def test_risque_de_cartographie_et_nouveau(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    processus = m.processus.first()
    # Une cartographie validée est figée : le risque est créé en brouillon puis la version validée.
    version = CartographieVersionFactory()
    source = RisqueFactory(version=version, processus=processus, probabilite=4, impact=3)
    CartographieVersion._base_manager.filter(pk=version.pk).update(  # noqa: SLF001
        statut=StatutCartographie.VALIDEE, validee_le=timezone.now(), validee_par=users["rai"]
    )
    Mission._base_manager.filter(pk=m.pk).update(cartographie=version)  # noqa: SLF001
    _ouvrir_etape_iv(m)
    api_client.force_authenticate(users["auditeur_confirme"])
    r = api_client.post(
        "/api/v1/mission-risks/",
        {"mission": str(m.id), "risque_source": str(source.id), "probabilite": 5},
        format="json",
    )
    assert r.status_code == 201, r.json()
    rid = r.json()["id"]
    assert r.json()["nouveau"] is False
    assert r.json()["code_source"] == source.code
    assert (r.json()["probabilite"], r.json()["impact"]) == (5, 3)
    assert (r.json()["probabilite_reference"], r.json()["impact_reference"]) == (4, 3)
    assert (r.json()["score"], r.json()["niveau"]) == (15, "ELEVE")
    r = api_client.patch(
        f"/api/v1/mission-risks/{rid}/", {"impact": 1, "commentaire": "Atténué"}, format="json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["score"] == 5
    assert (
        api_client.patch(
            f"/api/v1/mission-risks/{rid}/", {"processus": str(processus.id)}, format="json"
        ).status_code
        == 200
    )
    # Hors échelle : 400.
    assert (
        api_client.patch(f"/api/v1/mission-risks/{rid}/", {"impact": 6}, format="json").status_code
        == 400
    )
    r = api_client.post(
        "/api/v1/mission-risks/",
        {
            "mission": str(m.id),
            "processus": str(processus.id),
            "libelle": "Fraude",
            "probabilite": 2,
            "impact": 4,
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["nouveau"] is True
    assert r.json()["code_source"] == ""
    assert r.json()["probabilite_reference"] is None
    r = api_client.get(f"/api/v1/mission-risks/?mission={m.id}&nouveau=true")
    assert r.json()["count"] == 1
    r = api_client.get(f"/api/v1/mission-risks/?mission={m.id}&niveau=ELEVE")
    assert r.json()["count"] == 0
    r = api_client.get(f"/api/v1/mission-risks/?mission={m.id}&ordering=-score")
    assert [x["score"] for x in r.json()["results"]] == [8, 5]
    assert api_client.delete(f"/api/v1/mission-risks/{rid}/").status_code == 204


def test_risque_hors_etape_iv_ouverte_422(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["chef"])
    r = api_client.post(
        "/api/v1/mission-risks/",
        {
            "mission": str(m.id),
            "processus": str(m.processus.first().id),
            "libelle": "R",
            "probabilite": 1,
            "impact": 1,
        },
        format="json",
    )
    assert r.status_code == 422


def test_new_risks_rai_seul(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    RisqueMissionFactory(mission=m, processus=m.processus.first())
    api_client.force_authenticate(users["rai"])
    r = api_client.get("/api/v1/mission-risks/?nouveau=true")
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["results"][0]["mission_reference"] == "DAI/2026/M01"
    api_client.force_authenticate(users["chef"])
    assert api_client.get("/api/v1/mission-risks/?nouveau=true").status_code == 403
    assert api_client.get(f"/api/v1/mission-risks/?nouveau=true&mission={m.id}").status_code == 200


# ------------------------------------------------------------------ requêtes bornées


def test_listes_requetes_bornees(
    api_client: APIClient, equipe_complete: Equipe, django_assert_max_num_queries
) -> None:
    m, users = equipe_complete
    proprio = make_user(Role.AUDITEUR)
    for type_ in ("OUVERTURE", "LANCEMENT", "CLOTURE"):
        reunion = ReunionFactory(mission=m, type=type_)
        reunion.participants.add(users["rai"], users["chef"])
    for _ in range(8):
        entretien = EntretienFactory(mission=m, etape=EtapeMission.objects.get(mission=m, numero=2))
        entretien.auditeurs.add(users["chef"], proprio)
        entretien.interlocuteurs.add(users["audite_affecte"])
    for _ in range(8):
        RisqueMissionFactory(mission=m, processus=m.processus.first())
    api_client.force_authenticate(users["chef"])
    with django_assert_max_num_queries(4):
        assert api_client.get(f"/api/v1/meetings/?mission={m.id}").status_code == 200
    with django_assert_max_num_queries(5):
        assert api_client.get(f"/api/v1/interviews/?mission={m.id}").status_code == 200
    with django_assert_max_num_queries(3):
        assert api_client.get(f"/api/v1/mission-risks/?mission={m.id}").status_code == 200
