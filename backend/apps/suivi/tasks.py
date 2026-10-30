"""Tâches Celery du suivi."""

from celery import shared_task

from .services import ouverture


@shared_task(name="suivi.reconcilier_suivis")  # type: ignore[untyped-decorator]
def reconcilier_suivis() -> int:
    """Ouvre le suivi des actions que le signal du lot 7 n'a pas couvertes (filet horaire)."""
    return ouverture.reconcilier()
