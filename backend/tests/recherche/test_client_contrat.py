"""Contrat du moteur de recherche : même suite sur le faux en mémoire et sur Meilisearch."""

import logging
import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.recherche.client import (
    MARQUEUR_DEBUT,
    MARQUEUR_FIN,
    MeilisearchHttp,
    MoteurRecherche,
    echapper_filtre,
    moteur,
    reinitialiser_moteur,
)
from apps.recherche.exceptions import RechercheIndisponibleError
from tests.recherche.fakes import MoteurMemoire
from tests.test_prod_settings import PROD_ENV, load_prod

MEILI_URL = os.environ.get("MEILI_URL", "http://localhost:7700")
MEILI_CLE = os.environ.get("MEILI_MASTER_KEY", "")


def _meili_disponible() -> bool:
    try:
        return requests.get(f"{MEILI_URL}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(
    params=[
        "memoire",
        pytest.param(
            "meili",
            marks=[
                pytest.mark.meili,
                pytest.mark.skipif(not _meili_disponible(), reason="Meilisearch indisponible"),
            ],
        ),
    ]
)
def un_moteur(request: pytest.FixtureRequest) -> Iterator[MoteurRecherche]:
    if request.param == "memoire":
        yield MoteurMemoire()
        return
    index = f"onea-test-{uuid.uuid4().hex[:12]}"
    m = MeilisearchHttp(url=MEILI_URL, cle=MEILI_CLE, index=index, timeout=5)
    m.configurer()
    yield m
    requests.delete(
        f"{MEILI_URL}/indexes/{index}",
        headers={"Authorization": f"Bearer {MEILI_CLE}"},
        timeout=5,
    )


def _doc(i: str, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": f"recommandation:{i}",
        "type": "recommandation",
        "objet_id": i,
        "mission_id": "m1",
        "titre": f"Recommandation {i}",
        "reference": f"R{i}",
        "mission_reference": "DAI/2026/M01",
        "sous_titre": "Mission de test",
        "texte": "Renforcer le contrôle des encaissements à la caisse centrale",
        "audience": ["AUDITEUR", "RAI"],
        "annee": 2026,
        "date": 1790000000,
    }
    return {**base, **extra}


def test_indexer_puis_rechercher(un_moteur: MoteurRecherche) -> None:
    un_moteur.indexer([_doc("1"), _doc("2", texte="Autre sujet", titre="Autre")])
    hits = un_moteur.rechercher("encaissements", filtre="", limite=10)
    assert [h.id for h in hits] == ["recommandation:1"]
    assert hits[0].type == "recommandation"
    assert hits[0].objet_id == "1"
    assert hits[0].mission_id == "m1"
    assert hits[0].sous_titre == "Mission de test"


def test_filtre_mission_et_audience(un_moteur: MoteurRecherche) -> None:
    un_moteur.indexer(
        [
            _doc("1"),
            _doc("2", mission_id="m2"),
            _doc("3", audience=["DG"]),
        ]
    )
    sur_m1 = un_moteur.rechercher("", filtre='mission_id IN ["m1"]', limite=10)
    assert {h.objet_id for h in sur_m1} == {"1", "3"}
    dg = un_moteur.rechercher("", filtre='audience = "DG"', limite=10)
    assert [h.objet_id for h in dg] == ["3"]
    combine = un_moteur.rechercher(
        "", filtre='type = "recommandation" AND mission_id = "m2"', limite=10
    )
    assert [h.objet_id for h in combine] == ["2"]


def test_retirer(un_moteur: MoteurRecherche) -> None:
    un_moteur.indexer([_doc("1"), _doc("2")])
    un_moteur.retirer(["recommandation:1"])
    assert [h.objet_id for h in un_moteur.rechercher("", filtre="", limite=10)] == ["2"]
    un_moteur.vider()
    assert un_moteur.rechercher("", filtre="", limite=10) == []


def test_surlignage_par_marqueurs(un_moteur: MoteurRecherche) -> None:
    un_moteur.indexer([_doc("1")])
    hit = un_moteur.rechercher("caisse", filtre="", limite=10)[0]
    assert f"{MARQUEUR_DEBUT}caisse{MARQUEUR_FIN}" in hit.extrait
    assert "<em>" not in hit.extrait + hit.titre


def test_filtre_injection_echappe(un_moteur: MoteurRecherche) -> None:
    un_moteur.indexer([_doc("1", audience=["DG"]), _doc("2", mission_id='x" OR audience = "DG')])
    hostile = 'x" OR audience = "DG'
    filtre = f'mission_id = "{echapper_filtre(hostile)}" AND audience = "RAI"'
    hits = un_moteur.rechercher("", filtre=filtre, limite=10)
    # La valeur hostile reste un littéral : seul le document dont mission_id la contient
    # exactement pourrait correspondre, jamais le document « DG » de la mission m1.
    assert "1" not in {h.objet_id for h in hits}
    assert {h.objet_id for h in hits} <= {"2"}


def test_echapper_filtre() -> None:
    assert echapper_filtre('a"b\\c') == 'a\\"b\\\\c'


def test_indisponible_leve_503_sans_cle(caplog: pytest.LogCaptureFixture) -> None:
    secret = "cle-secrete-tres-privee"  # noqa: S105
    m = MeilisearchHttp(url="http://127.0.0.1:1", cle=secret, index="onea", timeout=1)
    with caplog.at_level(logging.DEBUG), pytest.raises(RechercheIndisponibleError) as exc:
        m.rechercher("x", filtre="", limite=5)
    assert exc.value.status_http == 503
    assert secret not in str(exc.value)
    assert secret not in caplog.text
    assert m.sante() is False


def test_reponse_5xx_leve_503() -> None:
    class Session:
        def request(self, *_a: Any, **_k: Any) -> requests.Response:
            r = requests.Response()
            r.status_code = 502
            return r

    m = MeilisearchHttp(url="http://x", cle="k", index="onea", session=Session())
    with pytest.raises(RechercheIndisponibleError):
        m.indexer([_doc("1")])


def test_envoie_en_tete_et_parametres_de_recherche() -> None:
    vus: dict[str, Any] = {}

    class Session:
        def request(self, methode: str, url: str, **k: Any) -> requests.Response:
            vus.update(k, methode=methode, url=url)
            r = requests.Response()
            r.status_code = 200
            r._content = b'{"hits": []}'
            return r

    m = MeilisearchHttp(url="http://x", cle="abc", index="onea", session=Session())
    m.rechercher("q", filtre='type = "a"', limite=7)
    assert vus["headers"] == {"Authorization": "Bearer abc"}
    assert vus["url"] == "http://x/indexes/onea/search"
    corps = vus["json"]
    assert corps["highlightPreTag"] == MARQUEUR_DEBUT
    assert corps["highlightPostTag"] == MARQUEUR_FIN
    assert corps["attributesToCrop"] == ["texte:30"]
    assert corps["attributesToHighlight"] == ["titre", "texte"]
    assert corps["filter"] == 'type = "a"'
    assert corps["limit"] == 7


def test_moteur_utilise_le_backend_des_reglages() -> None:
    reinitialiser_moteur()
    assert isinstance(moteur(), MoteurMemoire)
    assert moteur() is moteur()
    with override_settings(
        RECHERCHE={
            "BACKEND": "apps.recherche.client.MeilisearchHttp",
            "URL": "http://x",
            "CLE": "k",
            "INDEX": "onea",
            "TIMEOUT": 3,
        }
    ):
        assert isinstance(moteur(), MeilisearchHttp)
    reinitialiser_moteur()


def test_commande_configurer_recherche() -> None:
    reinitialiser_moteur()
    call_command("configurer_recherche")
    assert moteur().configure is True  # type: ignore[attr-defined]
    reinitialiser_moteur()


def test_commande_configurer_recherche_indisponible() -> None:
    reinitialiser_moteur()
    with (
        override_settings(
            RECHERCHE={
                "BACKEND": "apps.recherche.client.MeilisearchHttp",
                "URL": "http://127.0.0.1:1",
                "CLE": "k",
                "INDEX": "onea",
                "TIMEOUT": 1,
            }
        ),
        pytest.raises(CommandError, match="momentanément indisponible"),
    ):
        call_command("configurer_recherche")
    reinitialiser_moteur()


def test_prod_exige_la_cle() -> None:
    env = {k: v for k, v in PROD_ENV.items() if k != "MEILI_MASTER_KEY"}
    sans = load_prod(env, "import django; django.setup()")
    assert sans.returncode != 0
    assert "MEILI_MASTER_KEY" in sans.stderr
    avec = load_prod(PROD_ENV, "import django; django.setup()")
    assert avec.returncode == 0, avec.stderr
