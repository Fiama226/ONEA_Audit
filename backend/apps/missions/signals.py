"""Signaux du module missions, points d'extension pour les lots suivants."""

from django.dispatch import Signal

# Émis par `EvenementEtape.journaliser` après la création de l'événement, dans la transaction de
# l'appelant. Arguments : sender=EtapeMission, etape, evenement, par, type_evenement, motif,
# statut_avant.
# - Une exception levée par un récepteur remonte à l'appelant et annule donc la transition.
# - Le signal part avant que `avancer_phase` ne s'exécute (statut de la mission pas encore
#   recalculé) ; pour agir après validation de la transaction, utiliser `transaction.on_commit`.
# - Pour éviter un double branchement (rechargement de module), connecter avec `dispatch_uid`.
etape_changee = Signal()
