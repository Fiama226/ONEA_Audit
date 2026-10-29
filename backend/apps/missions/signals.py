"""Signaux du module missions, points d'extension pour les lots suivants."""

from django.dispatch import Signal

# Émis par `EvenementEtape.journaliser` après la création de l'événement, dans la transaction de
# l'appelant. Arguments : sender=EtapeMission, etape, evenement, par.
# Une exception levée par un récepteur remonte à l'appelant et annule donc la transition.
etape_changee = Signal()
