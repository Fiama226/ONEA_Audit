from unittest.mock import patch

from django.core.cache import cache
from rest_framework.test import APIClient

CHEMIN = "/api/v1/health/ready/"
SONDES = "apps.core.metriques"


def test_ready_200_quand_tout_va_bien(api_client: APIClient) -> None:
    with (
        patch(f"{SONDES}.base_up", return_value=True),
        patch(f"{SONDES}.redis_up", return_value=True),
        patch(f"{SONDES}.gotenberg_up", return_value=True),
    ):
        r = api_client.get(CHEMIN)
    assert r.status_code == 200
    assert r.json()["composants"]["base"] == "ok"


def test_ready_503_si_base_indisponible(api_client: APIClient) -> None:
    with (
        patch(f"{SONDES}.base_up", return_value=False),
        patch(f"{SONDES}.redis_up", return_value=True),
        patch(f"{SONDES}.gotenberg_up", return_value=True),
    ):
        r = api_client.get(CHEMIN)
    assert r.status_code == 503
    assert r.json()["composants"]["base"] == "indisponible"


def test_ready_503_si_redis_indisponible(api_client: APIClient) -> None:
    with (
        patch(f"{SONDES}.base_up", return_value=True),
        patch(f"{SONDES}.redis_up", return_value=False),
        patch(f"{SONDES}.gotenberg_up", return_value=True),
    ):
        r = api_client.get(CHEMIN)
    assert r.status_code == 503


def test_ready_200_degrade_si_seul_gotenberg_tombe(api_client: APIClient) -> None:
    with (
        patch(f"{SONDES}.base_up", return_value=True),
        patch(f"{SONDES}.redis_up", return_value=True),
        patch(f"{SONDES}.gotenberg_up", return_value=False),
    ):
        r = api_client.get(CHEMIN)
    assert r.status_code == 200
    assert r.json()["status"] == "degrade"
    assert r.json()["composants"]["gotenberg"] == "indisponible"


def test_ready_signale_un_beat_perime(api_client: APIClient) -> None:
    with (
        patch(f"{SONDES}.base_up", return_value=True),
        patch(f"{SONDES}.redis_up", return_value=True),
        patch(f"{SONDES}.gotenberg_up", return_value=True),
        patch(f"{SONDES}.age_pouls_beat", return_value=3600.0),
    ):
        r = api_client.get(CHEMIN)
    assert r.status_code == 200
    assert r.json()["composants"]["beat"] == "perime"
    assert r.json()["status"] == "degrade"


def test_pouls_beat_ecrit_dans_le_cache() -> None:
    from apps.core import metriques
    from apps.core.tasks import pouls_beat

    cache.delete(metriques.CLE_POULS_BEAT)
    assert metriques.age_pouls_beat() is None
    pouls_beat()
    age = metriques.age_pouls_beat()
    assert age is not None
    assert age < 5


def test_health_inchange_et_non_authentifie(api_client: APIClient) -> None:
    body = api_client.get("/api/v1/health/").json()
    assert set(body) == {"status", "version", "stockage_documents"}
