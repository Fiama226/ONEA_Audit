"""Tâches Celery de l'index de recherche (la logique est dans `services.py`)."""

from celery import shared_task

from .exceptions import RechercheIndisponibleError
from .services import indexer_objet_maintenant, reconcilier_index


@shared_task(  # type: ignore[untyped-decorator]
    name="recherche.indexer_objet",
    autoretry_for=(RechercheIndisponibleError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
    acks_late=True,
)
def indexer_objet(type: str, pk: str) -> None:  # noqa: A002
    """Idempotente : l'objet absent, supprimé ou non indexable est retiré de l'index."""
    indexer_objet_maintenant(type, pk)


@shared_task(  # type: ignore[untyped-decorator]
    name="recherche.reconcilier",
    autoretry_for=(RechercheIndisponibleError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
    acks_late=True,
)
def reconcilier() -> int:
    """Réindexation complète (rattrape les écritures en masse) ; renvoie le nombre indexé."""
    return reconcilier_index()
