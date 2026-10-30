import logging
import time
from typing import Any

from celery import shared_task

from apps.core.mail import send_mail_template

logger = logging.getLogger(__name__)


@shared_task(
    name="core.tasks.send_mail_task",
    acks_late=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=3,
)
def send_mail_task(to: list[str], subject: str, template: str, context: dict[str, Any]) -> None:
    """Send a templated email. Arguments are JSON-serialisable only."""
    send_mail_template(to, subject, template, context)


@shared_task(name="core.tasks.heartbeat")
def heartbeat() -> None:
    logger.info("celery beat heartbeat")


@shared_task(name="core.tasks.pouls_beat")
def pouls_beat() -> None:
    """Beat pulse read by the readiness probe to detect a stalled scheduler."""
    from django.core.cache import cache

    from apps.core.metriques import CLE_POULS_BEAT

    cache.set(CLE_POULS_BEAT, time.time(), timeout=3600)
