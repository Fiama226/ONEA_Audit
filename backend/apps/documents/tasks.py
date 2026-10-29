"""Celery tasks of the document engine (logic lives in `services/generation.py`)."""

import logging
from typing import Any

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from .pdf import GotenbergIndisponibleError
from .services import generation

logger = logging.getLogger(__name__)


@shared_task(  # type: ignore[untyped-decorator]
    name="documents.generer_version",
    acks_late=True,
    soft_time_limit=120,
    time_limit=180,
)
def generer_version(version_id: str) -> None:
    """Render and store the Word file of a version; idempotent (nothing if already settled)."""
    try:
        generation.executer_generation(version_id)
    except SoftTimeLimitExceeded:
        generation._echec(version_id, "La génération a dépassé le délai autorisé : relancez-la.")


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    name="documents.convertir_pdf",
    acks_late=True,
    autoretry_for=(GotenbergIndisponibleError,),
    max_retries=3,
    retry_backoff=True,
    soft_time_limit=420,
    time_limit=480,
)
def convertir_pdf(self: Any, version_id: str) -> None:
    """Convert the Word file to PDF; retried with backoff while Gotenberg is unavailable."""
    try:
        generation.executer_conversion(version_id)
    except GotenbergIndisponibleError as exc:
        # Eager mode (tests, no broker) cannot wait for a backoff: fail at once.
        if self.request.is_eager or self.request.retries >= self.max_retries:
            generation.marquer_echec_pdf(version_id, str(exc).rstrip("."))
            return
        raise
    except SoftTimeLimitExceeded:
        generation.marquer_echec_pdf(version_id, "délai dépassé")


@shared_task(name="documents.balayer_generations_bloquees")  # type: ignore[untyped-decorator]
def balayer_generations_bloquees() -> int:
    """Fail the generations and conversions stuck for more than 15 minutes (D10)."""
    nombre = generation.balayer()
    if nombre:
        logger.warning("%s génération(s) de document bloquée(s) marquée(s) en échec.", nombre)
    return nombre
