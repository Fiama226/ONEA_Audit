"""Accès à l'API de l'accomplissement (D13) : RAI et intervenants seulement.

Ordre des refus : rôle global (403, ADMIN, DG et AUDITE inclus : `audite_actions` reste vide
en v1, l'audité ne voit ni fiches ni pièces) -> mission ou objet invisible (404) -> droit (403)
-> contenu de la requête (400) -> règle métier, gel ou fenêtre d'écriture (422, par les
services).
"""

from apps.missions.permissions import MissionAccessPermission


class AccomplissementAccessPermission(MissionAccessPermission):
    """Refuse tout rôle autre que RAI et AUDITEUR ; l'AUDITE n'a aucune action ouverte.

    Les vues de l'accomplissement ne déclarent jamais `audite_actions` : le comportement par
    défaut de `MissionAccessPermission` (403 pour l'audité) est voulu.
    """
