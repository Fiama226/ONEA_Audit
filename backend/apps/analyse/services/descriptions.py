"""Description des processus (étape III)."""

from typing import Any

from django.db import transaction

from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.referentiel.models import Processus
from apps.users.models import User

from ..models import CategorieObjectif, DescriptionProcessus
from ._fenetres import ouvrir_iii

_CHAMPS = {
    "typologie",
    "categories_objectifs",
    "description",
    "objectifs",
    "indicateurs",
    "sources",
    "references_diagrammes",
}


def controler_processus(mission: Mission, processus: Processus) -> None:
    if not mission.processus.filter(pk=processus.pk).exists():
        message = "Le processus doit être un processus de la mission."
        raise refuser(message, processus=message)


@transaction.atomic
def enregistrer_description(
    mission: Mission, *, processus: Processus, by: User, **champs: Any
) -> DescriptionProcessus:
    mission = ouvrir_iii(mission)
    controler_processus(mission, processus)
    categories = champs.get("categories_objectifs")
    if categories is not None:
        if not isinstance(categories, list | tuple) or any(
            c not in CategorieObjectif.values for c in categories
        ):
            message = "Catégorie d'objectifs inconnue."
            raise refuser(message, categories_objectifs=message)
        champs["categories_objectifs"] = list(dict.fromkeys(categories))
    existante = DescriptionProcessus.objects.filter(mission=mission, processus=processus).first()
    if existante is None:
        description = DescriptionProcessus(mission=mission, processus=processus)
        appliquer(description, champs, _CHAMPS)
        enregistrer(description, by=by, creation=True)
        return description
    modifiee: DescriptionProcessus = relire(existante)
    appliquer(modifiee, champs, _CHAMPS)
    enregistrer(modifiee, by=by)
    return modifiee


@transaction.atomic
def retirer_description(description: DescriptionProcessus, *, by: User) -> None:
    ouvrir_iii(description.mission)
    relire(description).soft_delete(by)
