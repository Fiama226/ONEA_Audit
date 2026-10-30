from typing import Any
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

CHEMIN = "/api/v1/metrics/"


@pytest.fixture(autouse=True)
def _jeton(settings: Any) -> None:
    settings.METRICS_TOKEN = "jeton-de-test-metriques"  # noqa: S105


def test_metriques_404_sans_jeton(api_client: APIClient) -> None:
    assert api_client.get(CHEMIN).status_code == 404


def test_metriques_404_avec_mauvais_jeton(api_client: APIClient) -> None:
    assert api_client.get(CHEMIN, HTTP_AUTHORIZATION="Bearer faux").status_code == 404


def test_metriques_404_si_jeton_non_configure(api_client: APIClient, settings: Any) -> None:
    settings.METRICS_TOKEN = ""
    r = api_client.get(CHEMIN, HTTP_AUTHORIZATION="Bearer ")
    assert r.status_code == 404


def test_metriques_200_format_texte_avec_jeton(api_client: APIClient, db: None) -> None:
    with (
        patch("apps.core.metriques.redis_up", return_value=True),
        patch("apps.core.metriques.gotenberg_up", return_value=False),
        patch("apps.core.metriques.longueur_file_celery", return_value=4),
    ):
        r = api_client.get(CHEMIN, HTTP_AUTHORIZATION="Bearer jeton-de-test-metriques")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/plain")
    corps = r.content.decode()
    for nom in (
        "onea_build_info",
        "onea_db_up",
        "onea_redis_up",
        "onea_gotenberg_up",
        "onea_celery_file_attente",
        "onea_documents_espace_libre_octets",
        "onea_generations_bloquees",
    ):
        assert f"# TYPE {nom} gauge" in corps
    assert "onea_db_up 1" in corps
    assert "onea_gotenberg_up 0" in corps
    assert "onea_celery_file_attente 4" in corps
    for ligne in corps.splitlines():
        assert ligne.startswith("#") or ligne.count(" ") >= 1
