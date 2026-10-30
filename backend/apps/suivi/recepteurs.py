"""Récepteur du signal `rapport_diffuse` du lot 7 : ouvre le suivi (R6)."""

import logging
from typing import Any

from .services import ouverture

logger = logging.getLogger(__name__)


def sur_rapport_diffuse(sender: Any, *, rapport: Any, par: Any = None, **kwargs: Any) -> None:  # noqa: ARG001
    """Un échec ne remonte jamais à la diffusion : la réconciliation horaire rattrape."""
    try:
        ouverture.initialiser_suivi(rapport.mission, by=par)
    except Exception:
        logger.exception("Ouverture du suivi impossible pour la mission %s.", rapport.mission_id)
