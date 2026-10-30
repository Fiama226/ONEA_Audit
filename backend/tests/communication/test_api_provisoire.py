# ruff: noqa: F811, F401
"""API du rapport provisoire (XV) et des réponses des audités (XVI)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.communication.models import Rapport, RapportProvisoire, ReponseRapport
from apps.constats.models import Constat
from apps.missions.models import Mission, StatutEtape
from apps.missions.services import aujourd_hui
from apps.users.models import Role, User
from tests.accomplissement.fixtures_api import client_de
from tests.communication.fixtures_api import (
    PROVISOIRES,
    RAPPORTS,
    REPONSES,
    EquipeRapport,
)
from tests.communication.support_provisoire import (
    affecter,
    audite_affecte,
    audite_entite_a,
    audite_entite_b,
    auditeur_mission,
    aujourd_hui_le,
    chef,
    constat_a,
    constat_b,
    constat_hors_provisoire,
    mission_en_xiv,
    mission_lancee,
    mission_xv,
    provisoire_transmis,
    rapport_xv,
)
from tests.communication.support_t8 import admin, dg
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


@pytest.fixture
def equipe_xv(
    mission_xv: Mission,
    rai: User,
    chef: User,
    auditeur_mission: User,
    audite_entite_a: User,
    audite_entite_b: User,
    admin: User,
    dg: User,
) -> EquipeRapport:
    Mission.objects.filter(pk=mission_xv.pk).update(ordre_mission_emis_le=timezone.now())
    mission_xv.refresh_from_db()
    users = {
        "rai": rai,
        "chef": chef,
        "auditeur": auditeur_mission,
        "audite_a": audite_entite_a,
        "audite_b": audite_entite_b,
        "non_affecte": make_user(Role.AUDITEUR),
        "audite_non_affecte": make_user(Role.AUDITE),
        "admin": admin,
        "dg": dg,
    }
    return EquipeRapport(mission_xv, users)


def _corps(provisoire: RapportProvisoire, constat: Constat, **extra: object) -> dict[str, object]:
    return {
        "provisoire": str(provisoire.pk),
        "constat": str(constat.pk),
        "commentaire": "La direction prend acte et s'engage.",
        "confirme": True,
        **extra,
    }


# --------------------------------------------------------------------------- transmission


def test_transmission_du_provisoire(equipe_xv: EquipeRapport, rapport_xv: Rapport) -> None:
    url = f"{RAPPORTS}{rapport_xv.pk}/transmit-draft/"
    e = equipe_xv
    for qui, statut in (
        ("auditeur", 403),
        ("audite_a", 403),
        ("dg", 403),
        ("admin", 403),
        ("non_affecte", 404),
    ):
        assert client_de(e.users[qui]).post(url, {}, format="json").status_code == statut, qui
    chef = client_de(e.users["chef"])
    assert chef.post(url, {"delai_jours": 120}, format="json").status_code == 422
    assert chef.post(url, {"delai_jours": "abc"}, format="json").status_code == 400
    r = chef.post(url, {"delai_jours": 10}, format="json")
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["numero"] == 1 and corps["rapport"] == str(rapport_xv.pk)
    assert corps["date_limite_reponses"] == str(aujourd_hui() + timedelta(days=10))
    assert len(corps["constats"]) == 2 and not any(c["a_repondre"] for c in corps["constats"])
    # le RAI peut transmettre à nouveau (numéro suivant)
    assert client_de(e.users["rai"]).post(url, {}, format="json").json()["numero"] == 2


def test_transmission_xv_close_422(equipe_xv: EquipeRapport, rapport_xv: Rapport) -> None:
    forcer_etapes(equipe_xv.mission, {15: StatutEtape.TERMINEE})
    r = client_de(equipe_xv.users["chef"]).post(
        f"{RAPPORTS}{rapport_xv.pk}/transmit-draft/", {}, format="json"
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------- lecture


def test_lecture_du_provisoire_par_perimetre(
    equipe_xv: EquipeRapport, provisoire_transmis: RapportProvisoire, constat_a: Constat
) -> None:
    e = equipe_xv
    par_rapport = f"{PROVISOIRES}?rapport={provisoire_transmis.rapport_id}"
    equipe = client_de(e.users["chef"]).get(par_rapport).json()["results"][0]
    assert len(equipe["constats"]) == 2
    # l'audité de l'entité A ne voit que le constat de sa direction, et doit y répondre
    a = client_de(e.users["audite_a"]).get(f"{PROVISOIRES}{provisoire_transmis.pk}/").json()
    assert [c["id"] for c in a["constats"]] == [str(constat_a.pk)]
    assert a["constats"][0]["a_repondre"] is True
    b = client_de(e.users["audite_b"]).get(f"{PROVISOIRES}{provisoire_transmis.pk}/").json()
    assert [c["id"] for c in b["constats"]] != [str(constat_a.pk)]
    # refus de rôle, puis visibilité
    assert client_de(e.users["dg"]).get(par_rapport).status_code == 403
    assert client_de(e.users["admin"]).get(par_rapport).status_code == 403
    assert client_de(e.users["non_affecte"]).get(par_rapport).status_code == 404
    assert client_de(e.users["audite_non_affecte"]).get(par_rapport).status_code == 404
    assert client_de(e.users["chef"]).get(PROVISOIRES).status_code == 400
    assert (
        client_de(e.users["auditeur"]).get(f"{PROVISOIRES}?mission={e.mission.pk}").status_code
        == 200
    )


# --------------------------------------------------------------------------- réponses


def test_texte_a_confirmer(
    equipe_xv: EquipeRapport, provisoire_transmis: RapportProvisoire, constat_a: Constat
) -> None:
    e = equipe_xv
    url = f"{REPONSES}texte/?provisoire={provisoire_transmis.pk}&constat={constat_a.pk}"
    r = client_de(e.users["audite_a"]).get(url)
    assert r.status_code == 200
    assert constat_a.reference in r.json()["texte"] and r.json()["hors_delai"] is False
    assert client_de(e.users["chef"]).get(url).status_code == 403
    assert client_de(e.users["dg"]).get(url).status_code == 403
    assert (
        client_de(e.users["audite_b"]).get(url).status_code == 404
    )  # constat d'une autre direction
    assert (
        client_de(e.users["audite_a"])
        .get(f"{REPONSES}texte/?provisoire={provisoire_transmis.pk}")
        .status_code
        == 400
    )


def test_reponse_confirmee_de_l_audite(
    equipe_xv: EquipeRapport, provisoire_transmis: RapportProvisoire, constat_a: Constat
) -> None:
    audite = client_de(equipe_xv.users["audite_a"])
    r = audite.post(REPONSES, _corps(provisoire_transmis, constat_a), format="json")
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["hors_delai"] is False and corps["auteur"]["id"] == equipe_xv.users["audite_a"].pk
    assert corps["confirmation"]["empreinte"] and constat_a.reference in corps["texte"]
    assert ReponseRapport.objects.filter(provisoire=provisoire_transmis).count() == 1


def test_reponse_sans_confirme_400(
    equipe_xv: EquipeRapport, provisoire_transmis: RapportProvisoire, constat_a: Constat
) -> None:
    audite = client_de(equipe_xv.users["audite_a"])
    for extra in ({"confirme": False}, {"confirme": "false"}):
        r = audite.post(REPONSES, _corps(provisoire_transmis, constat_a, **extra), format="json")
        assert r.status_code == 400
    sans = _corps(provisoire_transmis, constat_a)
    del sans["confirme"]
    assert audite.post(REPONSES, sans, format="json").status_code == 400
    assert ReponseRapport.objects.count() == 0


def test_reponse_ordre_des_refus(
    equipe_xv: EquipeRapport,
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    constat_hors_provisoire: Constat,
) -> None:
    e = equipe_xv
    corps = _corps(provisoire_transmis, constat_a)
    for qui, statut in (
        ("chef", 403),
        ("rai", 403),
        ("auditeur", 403),
        ("dg", 403),
        ("admin", 403),
    ):
        assert client_de(e.users[qui]).post(REPONSES, corps, format="json").status_code == statut, (
            qui
        )
    # constat d'une autre direction : invisible pour l'audité B (404), même sans `confirme`
    sans_confirme = _corps(provisoire_transmis, constat_a, confirme=False)
    assert (
        client_de(e.users["audite_b"]).post(REPONSES, sans_confirme, format="json").status_code
        == 404
    )
    assert (
        client_de(e.users["audite_non_affecte"]).post(REPONSES, corps, format="json").status_code
        == 404
    )
    # constat non validé hors provisoire : invisible pour l'audité
    hors = _corps(provisoire_transmis, constat_hors_provisoire)
    assert client_de(e.users["audite_a"]).post(REPONSES, hors, format="json").status_code == 404
    # corps incomplet : 400
    assert (
        client_de(e.users["audite_a"]).post(REPONSES, {"confirme": True}, format="json").status_code
        == 400
    )
    # commentaire vide : règle métier (422)
    vide = _corps(provisoire_transmis, constat_a, commentaire="  ")
    assert client_de(e.users["audite_a"]).post(REPONSES, vide, format="json").status_code == 422


def test_reponse_hors_delai(
    equipe_xv: EquipeRapport,
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    aujourd_hui_le,  # type: ignore[no-untyped-def]
) -> None:
    aujourd_hui_le(provisoire_transmis.date_limite_reponses + timedelta(days=3))
    r = client_de(equipe_xv.users["audite_a"]).post(
        REPONSES, _corps(provisoire_transmis, constat_a), format="json"
    )
    assert r.status_code == 201 and r.json()["hors_delai"] is True


def test_reponses_closes_422(
    equipe_xv: EquipeRapport, provisoire_transmis: RapportProvisoire, constat_a: Constat
) -> None:
    forcer_etapes(equipe_xv.mission, {16: StatutEtape.TERMINEE})
    r = client_de(equipe_xv.users["audite_a"]).post(
        REPONSES, _corps(provisoire_transmis, constat_a), format="json"
    )
    assert r.status_code == 422


def test_audite_ne_voit_que_ses_reponses(
    equipe_xv: EquipeRapport,
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    constat_b: Constat,
) -> None:
    e = equipe_xv
    client_de(e.users["audite_a"]).post(
        REPONSES, _corps(provisoire_transmis, constat_a), format="json"
    )
    client_de(e.users["audite_b"]).post(
        REPONSES, _corps(provisoire_transmis, constat_b), format="json"
    )
    url = f"{REPONSES}?provisoire={provisoire_transmis.pk}"
    assert client_de(e.users["audite_a"]).get(url).json()["count"] == 1
    assert client_de(e.users["audite_a"]).get(url).json()["results"][0]["constat"] == str(
        constat_a.pk
    )
    assert client_de(e.users["audite_b"]).get(url).json()["results"][0]["constat"] == str(
        constat_b.pk
    )
    assert client_de(e.users["chef"]).get(url).json()["count"] == 2
    assert client_de(e.users["rai"]).get(f"{url}&constat={constat_b.pk}").json()["count"] == 1
    assert client_de(e.users["dg"]).get(url).status_code == 403
    assert client_de(e.users["non_affecte"]).get(url).status_code == 404
    assert client_de(e.users["audite_non_affecte"]).get(url).status_code == 404
    assert client_de(e.users["chef"]).get(REPONSES).status_code == 400


def test_listes_requetes_bornees_reponses(
    equipe_xv: EquipeRapport, provisoire_transmis: RapportProvisoire, constat_a: Constat
) -> None:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from tests.communication.factories import ReponseRapportFactory

    url = f"{REPONSES}?provisoire={provisoire_transmis.pk}"
    auteur = equipe_xv.users["audite_a"]

    def compter(qui: str) -> int:
        with CaptureQueriesContext(connection) as ctx:
            assert client_de(equipe_xv.users[qui]).get(url).status_code == 200
        return len(ctx)

    ReponseRapportFactory(provisoire=provisoire_transmis, constat=constat_a, auteur=auteur)
    avant = (compter("chef"), compter("audite_a"))
    for _ in range(20):
        ReponseRapportFactory(provisoire=provisoire_transmis, constat=constat_a, auteur=auteur)
    assert (compter("chef"), compter("audite_a")) == avant
    assert client_de(auteur).get(url).json()["count"] == 21
