import hashlib
import logging
import time
from typing import Any
from unittest import mock

import pytest
import requests
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.users.models import User

from .test_oidc import claims, make_token

URL_GET = "mozilla_django_oidc.auth.requests.get"


def reponse(donnees: dict[str, Any] | None = None, statut: int = 200) -> mock.Mock:
    r = mock.Mock()
    r.status_code = statut
    r.headers = {"content-type": "application/json"}
    r.json.return_value = donnees if donnees is not None else claims()
    if statut >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(response=r)
    return r


def jeton(expire_dans: int = 3600) -> str:
    return make_token(exp=int(time.time()) + expire_dans)


def appeler(client: APIClient, token: str, chemin: str = "/api/v1/me/", post: bool = False) -> Any:
    en_tete = f"Bearer {token}"
    return (
        client.post(chemin, HTTP_AUTHORIZATION=en_tete)
        if post
        else client.get(chemin, HTTP_AUTHORIZATION=en_tete)
    )


@pytest.mark.django_db
def test_deux_appels_meme_jeton_un_seul_userinfo(api_client: APIClient) -> None:
    t = jeton()
    with mock.patch(URL_GET, return_value=reponse()) as get:
        assert appeler(api_client, t).status_code == 200
        assert appeler(api_client, t).status_code == 200
    assert get.call_count == 1


@pytest.mark.django_db
def test_jetons_differents_pas_de_partage(api_client: APIClient) -> None:
    with mock.patch(URL_GET, return_value=reponse()) as get:
        appeler(api_client, jeton(3600))
        appeler(api_client, jeton(3601))
    assert get.call_count == 2


@pytest.mark.django_db
def test_duree_bornee_par_expiration_du_jeton(api_client: APIClient) -> None:
    t = jeton(10)
    with (
        mock.patch(URL_GET, return_value=reponse()),
        mock.patch("apps.users.oidc.cache") as c,
    ):
        c.get.return_value = None
        appeler(api_client, t)
    ttl = c.set.call_args.args[2]
    assert 0 < ttl <= 10


@pytest.mark.django_db
def test_duree_plafonnee_a_la_configuration(api_client: APIClient) -> None:
    with (
        mock.patch(URL_GET, return_value=reponse()),
        mock.patch("apps.users.oidc.cache") as c,
    ):
        c.get.return_value = None
        appeler(api_client, jeton(86400))
    assert c.set.call_args.args[2] == 60


@pytest.mark.django_db
@pytest.mark.parametrize("token_fn", [lambda: make_token(), lambda: jeton(-5)])
def test_jeton_sans_exp_ou_expire_non_mis_en_cache(api_client: APIClient, token_fn: Any) -> None:
    t = token_fn()
    with mock.patch(URL_GET, return_value=reponse()) as get:
        appeler(api_client, t)
        appeler(api_client, t)
    assert get.call_count == 2


@pytest.mark.django_db
@pytest.mark.parametrize("statut", [401, 500, 503])
def test_erreurs_non_mises_en_cache(api_client: APIClient, statut: int) -> None:
    t = jeton()
    with mock.patch(URL_GET, return_value=reponse(statut=statut)) as get:
        assert appeler(api_client, t).status_code == (401 if statut == 401 else 503)
        assert appeler(api_client, t).status_code == (401 if statut == 401 else 503)
    assert get.call_count == 2
    with mock.patch(URL_GET, return_value=reponse()) as get:
        assert appeler(api_client, t).status_code == 200
    assert get.call_count == 1


@pytest.mark.django_db
def test_fin_de_session_purge_le_cache(api_client: APIClient) -> None:
    t = jeton()
    with mock.patch(URL_GET, return_value=reponse()) as get:
        appeler(api_client, t)
        assert appeler(api_client, t, "/api/v1/session/fin/", post=True).status_code == 204
        appeler(api_client, t)
    assert get.call_count == 2


@pytest.mark.django_db
def test_fin_de_session_ne_purge_que_son_jeton(api_client: APIClient) -> None:
    a, b = jeton(3600), jeton(3601)
    with mock.patch(URL_GET, return_value=reponse()) as get:
        appeler(api_client, a)
        appeler(api_client, b)
        appeler(api_client, a, "/api/v1/session/fin/", post=True)
        appeler(api_client, b)
    assert get.call_count == 2


@pytest.mark.django_db
def test_fin_de_session_sans_jeton_401(api_client: APIClient) -> None:
    assert api_client.post("/api/v1/session/fin/").status_code == 401


@pytest.mark.django_db
def test_fin_de_session_jeton_refuse_401(api_client: APIClient) -> None:
    with mock.patch(URL_GET, return_value=reponse(statut=401)):
        assert appeler(api_client, jeton(), "/api/v1/session/fin/", post=True).status_code == 401


@pytest.mark.django_db
def test_compte_desactive_403_malgre_le_cache(api_client: APIClient) -> None:
    t = jeton()
    with mock.patch(URL_GET, return_value=reponse()) as get:
        assert appeler(api_client, t).status_code == 200
        User.objects.update(is_active=False)
        r = appeler(api_client, t)
    assert get.call_count == 1
    assert r.status_code == 403


@pytest.mark.django_db
def test_aucune_cle_ne_contient_le_jeton_en_clair(api_client: APIClient) -> None:
    t = jeton()
    with mock.patch(URL_GET, return_value=reponse()):
        appeler(api_client, t)
    cles = list(cache._cache)  # type: ignore[attr-defined]  # LocMemCache
    assert cles
    assert not any(t in c or t.split(".")[1] in c for c in cles)
    assert any(hashlib.sha256(t.encode()).hexdigest() in c for c in cles)


@pytest.mark.django_db
def test_jeton_jamais_journalise(api_client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    t = jeton()
    with caplog.at_level(logging.DEBUG), mock.patch(URL_GET, return_value=reponse()):
        appeler(api_client, t)
        appeler(api_client, t, "/api/v1/session/fin/", post=True)
    assert t not in caplog.text


@pytest.mark.django_db
def test_cache_en_panne_authentification_maintenue(api_client: APIClient) -> None:
    with (
        mock.patch(URL_GET, return_value=reponse()),
        mock.patch("apps.users.oidc.cache") as c,
    ):
        c.get.side_effect = ConnectionError("redis")
        c.set.side_effect = ConnectionError("redis")
        assert appeler(api_client, jeton()).status_code == 200
