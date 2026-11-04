"""Tâches Celery du suivi : réconciliation (ouverture) et relances (logique dans `relances.py`)."""

from smtplib import SMTPException
from typing import Any

from celery import shared_task
from django.conf import settings

from . import relances
from .services import ouverture


@shared_task(name="suivi.reconcilier_suivis")  # type: ignore[untyped-decorator]
def reconcilier_suivis() -> int:
    """Ouvre le suivi des actions que le signal du lot 7 n'a pas couvertes (filet horaire)."""
    return ouverture.reconcilier()


@shared_task(name="suivi.relances_quotidiennes")  # type: ignore[untyped-decorator]
def relances_quotidiennes() -> int:
    """Planifie les relances du jour puis envoie un e-mail par destinataire (plafonné)."""
    if not settings.RELANCES_ACTIVES:
        return 0
    return relances.executer_relances(asynchrone=True)


@shared_task(  # type: ignore[untyped-decorator]
    name="suivi.envoyer_lot_relances",
    rate_limit="20/m",
    acks_late=True,
    autoretry_for=(SMTPException, OSError),
    retry_backoff=60,
    max_retries=3,
)
def envoyer_lot_relances(destinataire_id: int, relance_ids: list[str]) -> int:
    """Envoie l'e-mail regroupé d'un destinataire ; les échecs d'envoi sont consignés (ECHEC)."""
    return relances.envoyer_lot(destinataire_id, relance_ids)


__all__: list[Any] = [
    "envoyer_lot_relances",
    "reconcilier_suivis",
    "relances_quotidiennes",
]
