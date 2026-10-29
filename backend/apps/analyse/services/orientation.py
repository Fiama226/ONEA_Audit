"""Rapport d'orientation de l'étape VII (D9, D12 du plan du lot 5)."""

from typing import Any

from django.db import transaction

from apps.core.services import appliquer, enregistrer, refuser
from apps.missions.models import Mission
from apps.users.models import User

from ..models import CouvertureOrdre, RapportOrientation
from .objectifs import ouvrir_ecriture

_MODIFIABLES = {
    "variante",
    "contexte",
    "approche",
    "observations",
    "couverture_ordre",
    "justification_couverture",
}


def obtenir_rapport(mission: Mission) -> RapportOrientation | None:
    return RapportOrientation.objects.filter(mission=mission).first()


@transaction.atomic
def enregistrer_rapport(mission: Mission, *, by: User, **champs: Any) -> RapportOrientation:
    mission = ouvrir_ecriture(mission)
    rapport = obtenir_rapport(mission)
    creation = rapport is None
    if rapport is None:
        rapport = RapportOrientation(mission=mission)
    appliquer(rapport, champs, _MODIFIABLES)
    if (
        rapport.couverture_ordre not in ("", CouvertureOrdre.EXACTE)
        and not rapport.justification_couverture.strip()
    ):
        message = "Une justification est obligatoire hors couverture exacte."
        raise refuser(message, justification_couverture=message)
    enregistrer(rapport, by=by, creation=creation)
    return rapport
