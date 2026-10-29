"""Récepteurs de signaux de l'app accomplissement."""

from typing import Any

from django.dispatch import receiver

from apps.missions.models import EtapeMission, TypeEvenementEtape
from apps.missions.signals import etape_changee

from .services.instantanes import creer_instantane

ETAPE_ORGANISATION = 10


@receiver(etape_changee, sender=EtapeMission, dispatch_uid="accomplissement_instantane_programme")
def figer_a_la_validation_de_x(
    sender: Any, etape: EtapeMission, evenement: Any, par: Any, **kwargs: Any
) -> None:
    """Chaque validation de l'étape X fige un instantané du programme (D14)."""
    if etape.numero == ETAPE_ORGANISATION and evenement.type == TypeEvenementEtape.VALIDEE:
        creer_instantane(etape, by=par)
