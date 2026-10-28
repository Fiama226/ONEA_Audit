"""Services de pilotage des missions : un module par sous-domaine (D16)."""

from datetime import date
from zoneinfo import ZoneInfo

from django.utils import timezone

# Verrou consultatif de la numérotation des références de mission (D3), « MISS ».
LOCK_REFERENCE_MISSION = 0x4D495353

FUSEAU_ONEA = ZoneInfo("Africa/Ouagadougou")


def aujourd_hui() -> date:
    """Date calendaire du jour à Ouagadougou."""
    return timezone.now().astimezone(FUSEAU_ONEA).date()
