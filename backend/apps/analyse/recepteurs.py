"""Récepteurs de signaux de l'app analyse."""

from typing import Any

from django.dispatch import receiver

from apps.missions.models import EtapeMission, TypeEvenementEtape
from apps.missions.services.risques import enregistrer_garde_retrait
from apps.missions.signals import etape_changee

from .services.marc import garde_retrait_risque
from .services.referentiel import figer_referentiel

ETAPE_REFERENTIEL = 6

enregistrer_garde_retrait(garde_retrait_risque)


@receiver(etape_changee, sender=EtapeMission, dispatch_uid="analyse_figer_referentiel")
def figer_a_la_validation_de_vi(
    sender: Any, etape: EtapeMission, evenement: Any, par: Any, **kwargs: Any
) -> None:
    """Chaque validation de l'étape VI fige un instantané du référentiel (D3)."""
    if etape.numero == ETAPE_REFERENTIEL and evenement.type == TypeEvenementEtape.VALIDEE:
        figer_referentiel(etape.mission, by=par)
