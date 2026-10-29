"""Probes and minimal Prometheus-style metrics (text exposition format)."""

import time
import urllib.request
from typing import cast

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection

from apps.documents.stockage import stockage_documents
from config import __version__

CLE_POULS_BEAT = "onea:beat:pouls"
BEAT_PERIME_SECONDES = 600  # beat writes a pulse every minute
_TIMEOUT = 2


def base_up() -> bool:
    try:
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


def _client_redis() -> "redis.Redis":
    return redis.Redis.from_url(
        settings.REDIS_URL, socket_connect_timeout=_TIMEOUT, socket_timeout=_TIMEOUT
    )


def redis_up() -> bool:
    try:
        return bool(_client_redis().ping())
    except Exception:  # noqa: BLE001
        return False


def gotenberg_up() -> bool:
    try:
        with urllib.request.urlopen(  # noqa: S310 - fixed configured http(s) URL
            f"{settings.GOTENBERG_URL}/health", timeout=_TIMEOUT
        ) as reponse:
            return bool(reponse.status == 200)
    except Exception:  # noqa: BLE001
        return False


def longueur_file_celery() -> int:
    try:
        return int(cast(int, _client_redis().llen("celery")))
    except Exception:  # noqa: BLE001
        return -1


def age_pouls_beat() -> float | None:
    try:
        pouls = cache.get(CLE_POULS_BEAT)
    except Exception:  # noqa: BLE001
        return None
    return None if pouls is None else max(0.0, time.time() - float(pouls))


def espace_libre_documents() -> int:
    import shutil
    from pathlib import Path

    from django.core.files.storage import FileSystemStorage

    stockage = stockage_documents()
    if not isinstance(stockage, FileSystemStorage):
        return -1
    try:
        return shutil.disk_usage(Path(stockage.location)).free
    except OSError:
        return -1


def generations_bloquees() -> int:
    from datetime import timedelta

    from django.utils import timezone

    from apps.documents.models import DocumentVersion, StatutGeneration

    limite = timezone.now() - timedelta(minutes=15)
    try:
        return (
            DocumentVersion.objects.filter(
                statut=StatutGeneration.EN_ATTENTE, created_at__lt=limite
            ).count()
            + DocumentVersion.objects.filter(
                statut=StatutGeneration.EN_COURS, debut_traitement__lt=limite
            ).count()
        )
    except Exception:  # noqa: BLE001
        return -1


def etat_composants() -> dict[str, str]:
    """Readiness components: base and redis are vital, the others only degrade."""
    age = age_pouls_beat()
    return {
        "base": "ok" if base_up() else "indisponible",
        "redis": "ok" if redis_up() else "indisponible",
        "gotenberg": "ok" if gotenberg_up() else "indisponible",
        "beat": "inconnu" if age is None else ("ok" if age < BEAT_PERIME_SECONDES else "perime"),
    }


def exposition() -> str:
    mesures: list[tuple[str, str, float]] = [
        ("onea_db_up", "Base de données joignable (1/0)", int(base_up())),
        ("onea_redis_up", "Redis joignable (1/0)", int(redis_up())),
        ("onea_gotenberg_up", "Gotenberg joignable (1/0)", int(gotenberg_up())),
        ("onea_celery_file_attente", "Tâches en attente (-1 : inconnu)", longueur_file_celery()),
        (
            "onea_documents_espace_libre_octets",
            "Espace libre du stockage documents (-1 : inconnu)",
            espace_libre_documents(),
        ),
        (
            "onea_generations_bloquees",
            "Générations de documents bloquées depuis plus de 15 min",
            generations_bloquees(),
        ),
    ]
    lignes = [
        "# HELP onea_build_info Version de l'application",
        "# TYPE onea_build_info gauge",
        f'onea_build_info{{version="{__version__}"}} 1',
    ]
    for nom, aide, valeur in mesures:
        lignes += [f"# HELP {nom} {aide}", f"# TYPE {nom} gauge", f"{nom} {valeur}"]
    return "\n".join(lignes) + "\n"
