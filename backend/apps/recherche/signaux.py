"""Synchronisation de l'index (R15) : `post_save` -> `on_commit` -> tâche `indexer_objet`.

Une panne du courtier ou du moteur ne doit jamais faire échouer une écriture métier : l'erreur
est journalisée et la réconciliation nocturne rattrape l'objet.
"""

import logging
from typing import Any

from django.db import transaction
from django.db.models import Model
from django.db.models.signals import post_save

from .sources import MODELES_SURVEILLES, objets_a_reindexer

logger = logging.getLogger(__name__)


def _planifier(sender: type[Model], instance: Model, raw: bool = False, **kwargs: Any) -> None:
    if raw:
        return

    def apres_commit() -> None:
        from .tasks import indexer_objet

        try:
            cibles = objets_a_reindexer(instance)
        except Exception:  # noqa: BLE001
            logger.warning("Recherche : dépendants de %s illisibles.", sender.__name__)
            return
        for type_, pk in cibles:
            try:
                indexer_objet.delay(type_, str(pk))
            except Exception:  # noqa: BLE001
                logger.warning("Recherche : indexation de %s-%s non planifiée.", type_, pk)

    transaction.on_commit(apres_commit)


def connecter() -> None:
    for modele in MODELES_SURVEILLES:
        post_save.connect(
            _planifier,
            sender=modele,
            dispatch_uid=f"recherche.indexer.{modele._meta.label_lower}",
        )
