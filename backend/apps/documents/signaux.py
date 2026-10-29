"""Automatic generation of the mission order when its issuing confirmation is recorded (D13)."""

import logging
from typing import Any

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.exceptions import RegleMetierError
from apps.signatures.models import Confirmation, TypeDocumentSignable

from .exceptions import ContratNonRespecteError

logger = logging.getLogger(__name__)


def _generer_ordre(confirmation: Confirmation) -> None:
    from .services.generation import demander_generation

    try:
        demander_generation(
            type_document="ORDRE_MISSION",
            objet_id=confirmation.object_id,
            by=confirmation.signataire,
        )
    except (RegleMetierError, ContratNonRespecteError) as exc:
        # The issuing of the order must never fail because of the document engine; a second
        # call for the same data ("already up to date") ends here as well (idempotence).
        logger.warning(
            "Génération automatique de l'ordre de mission impossible (confirmation %s) : %s",
            confirmation.pk,
            exc,
        )


@receiver(post_save, sender=Confirmation, dispatch_uid="documents.generer_ordre_mission")
def generer_ordre_a_la_confirmation(
    sender: Any, instance: Confirmation, created: bool, **kwargs: Any
) -> None:
    if not created or instance.type_document != TypeDocumentSignable.ORDRE_MISSION:
        return
    transaction.on_commit(lambda: _generer_ordre(instance), robust=True)
