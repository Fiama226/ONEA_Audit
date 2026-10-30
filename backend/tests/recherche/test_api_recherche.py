"""API de la recherche : matrice des rôles, validation de `q` et `types`, 429, 503, nettoyage."""

from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.missions.models import Mission
from apps.recherche.client import MARQUEUR_DEBUT, MARQUEUR_FIN, Hit
from apps.recherche.exceptions import RechercheIndisponibleError
from apps.recherche.views import construire_resultats
from apps.users.models import User
from tests.accomplissement.fixtures_api import client_de

URL = "/api/v1/search/"
CLES = {
    "type",
    "objet_id",
    "mission_id",
    "mission_reference",
    "titre",
    "sous_titre",
    "extrait",
    "etape",
}


@pytest.fixture(autouse=True)
def _cache_propre() -> None:
    cache.clear()


def _types_trouves(client: APIClient, q: str = "Rapprochement", **params: str) -> list[str]:
    reponse = client.get(URL, {"q": q, **params})
    assert reponse.status_code == 200, reponse.json()
    return [r["objet_id"] for r in reponse.json()["resultats"]]


@pytest.mark.parametrize(
    "acteur, attendu",
    [
        ("rai", {"CONSTAT-brouillon", "CONSTAT-soumis"}),
        ("auditeur_mission", {"CONSTAT-brouillon", "CONSTAT-soumis"}),
        ("autre_auditeur", set()),
        ("audite_affecte", {"CONSTAT-soumis"}),
        ("dg", set()),
    ],
)
def test_api_recherche_matrice_roles(
    index_peuple: dict[str, str], request: pytest.FixtureRequest, acteur: str, attendu: set[str]
) -> None:
    user: User = request.getfixturevalue(acteur)
    trouves = {f"CONSTAT-{pk}" for pk in _types_trouves(client_de(user), types="CONSTAT")}
    assert trouves == {index_peuple[cle] for cle in attendu}


def test_api_recherche_admin_403_sans_appel_moteur(
    index_peuple: dict[str, str], admin: User, index: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interdit(*_a: Any, **_k: Any) -> None:
        raise AssertionError("moteur interrogé")

    monkeypatch.setattr(index, "rechercher", interdit)
    reponse = client_de(admin).get(URL, {"q": "Rapprochement"})
    assert reponse.status_code == 403
    assert set(reponse.json()) == {"detail", "errors"}


def test_api_recherche_anonyme_401(api_client: APIClient) -> None:
    assert api_client.get(URL, {"q": "Rapprochement"}).status_code == 401


def test_api_recherche_forme_des_resultats(index_peuple: dict[str, str], rai: User) -> None:
    corps = client_de(rai).get(URL, {"q": "Rapprochement", "types": "CONSTAT"}).json()
    assert corps["resultats"]
    for resultat in corps["resultats"]:
        assert set(resultat) == CLES
        assert resultat["type"] == "CONSTAT"
        assert resultat["etape"] is None
        assert resultat["mission_reference"]
        assert MARQUEUR_DEBUT in resultat["titre"]


def test_api_recherche_sans_total(index_peuple: dict[str, str], rai: User) -> None:
    reponse = client_de(rai).get(URL, {"q": "Rapprochement"})
    assert set(reponse.json()) == {"resultats", "plus"}
    assert reponse.json()["plus"] is False
    assert reponse["Cache-Control"] == "no-store"


def test_api_recherche_limitee(
    index_peuple: dict[str, str], rai: User, autre_auditeur: User
) -> None:
    client = client_de(rai)
    for _ in range(60):
        assert client.get(URL, {"q": "Rapprochement"}).status_code == 200
    reponse = client.get(URL, {"q": "Rapprochement"})
    assert reponse.status_code == 429
    assert set(reponse.json()) == {"detail", "errors"}
    assert int(reponse["Retry-After"]) >= 1
    # la limite est par utilisateur : un autre compte n'est pas touché
    assert client_de(autre_auditeur).get(URL, {"q": "Rapprochement"}).status_code == 200


def test_api_recherche_503(rai: User, index: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def indisponible(*_a: Any, **_k: Any) -> None:
        raise RechercheIndisponibleError

    monkeypatch.setattr(index, "rechercher", indisponible)
    reponse = client_de(rai).get(URL, {"q": "Rapprochement"})
    assert reponse.status_code == 503
    assert set(reponse.json()) == {"detail", "errors"}


@pytest.mark.parametrize(
    "params, champ",
    [
        ({}, "q"),
        ({"q": ""}, "q"),
        ({"q": "a"}, "q"),
        ({"q": " a "}, "q"),
        ({"q": "x" * 201}, "q"),
        ({"q": "x" * 5000}, "q"),
        ({"q": "ab\x00cd"}, "q"),
        ({"q": "Rapprochement", "types": "INCONNU"}, "types"),
        ({"q": "Rapprochement", "types": ""}, "types"),
        ({"q": "Rapprochement", "types": "CONSTAT,,MISSION"}, "types"),
        ({"q": "Rapprochement", "types": 'CONSTAT" OR 1=1'}, "types"),
        ({"q": "Rapprochement", "types": "x" * 500}, "types"),
    ],
)
def test_api_recherche_validation_400(rai: User, params: dict[str, str], champ: str) -> None:
    reponse = client_de(rai).get(URL, params)
    assert reponse.status_code == 400
    assert champ in reponse.json()["errors"]


def test_api_recherche_types_multiples_et_doublons(index_peuple: dict[str, str], rai: User) -> None:
    assert _types_trouves(client_de(rai), types="CONSTAT,CONSTAT,MISSION")
    assert not _types_trouves(client_de(rai), types="MISSION")


def test_api_recherche_injection_de_filtre_inoperante(
    index_peuple: dict[str, str], autre_auditeur: User
) -> None:
    for q in ('" OR audience = "EQUIPE', 'Rapprochement" OR type != "', "\\\\"):
        reponse = client_de(autre_auditeur).get(URL, {"q": q})
        assert reponse.status_code in (200, 400)
        if reponse.status_code == 200:
            assert reponse.json()["resultats"] == []


def test_api_recherche_nettoie_les_caracteres_de_controle(
    index_peuple: dict[str, str], index: Any, rai: User
) -> None:
    identifiant = index_peuple["CONSTAT-soumis"]
    index.documents[identifiant]["titre"] = "Rap\x07pro\u202e\x00chement\nbancaire \x02ajout"
    index.documents[identifiant]["texte"] = "Texte\x1b[31m rouge\u200b bancaire"
    index.documents[identifiant]["sous_titre"] = "Sous\x02-titre\x07"
    corps = client_de(rai).get(URL, {"q": "bancaire", "types": "CONSTAT"}).json()
    resultat = next(r for r in corps["resultats"] if identifiant.endswith(r["objet_id"]))
    for champ in ("titre", "extrait", "sous_titre"):
        for c in resultat[champ]:
            assert c in (MARQUEUR_DEBUT, MARQUEUR_FIN) or (ord(c) >= 32 and c != "\x7f")
        assert "\u202e" not in resultat[champ]
        assert "\u200b" not in resultat[champ]
    assert MARQUEUR_DEBUT not in resultat["sous_titre"]
    assert "Rapprochement bancaire ajout" in resultat["titre"].replace(MARQUEUR_DEBUT, "").replace(
        MARQUEUR_FIN, ""
    )
    assert "Rap" in resultat["titre"]


def test_api_recherche_etape_et_reference_des_documents(
    mission_lancee: Mission, creer_document: Any
) -> None:
    document = creer_document(mission_lancee, "ORDRE_MISSION", mission_lancee)
    hits = [
        Hit(
            id=f"DOCUMENT-{document.pk}",
            type="DOCUMENT",
            objet_id=str(document.pk),
            mission_id=str(mission_lancee.pk),
            titre="Ordre",
            sous_titre="",
            extrait="",
        ),
        Hit("MISSION-x", "MISSION", "x", None, "T", "", ""),
    ]
    resultats = construire_resultats(hits)
    assert resultats[0]["mission_reference"] == mission_lancee.reference
    assert isinstance(resultats[0]["etape"], int)
    assert resultats[1]["etape"] is None
    assert resultats[1]["mission_reference"] == ""
