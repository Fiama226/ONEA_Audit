"""Peuplement de démonstration : accomplissement.

Pas de données fictives pour l'instant : les programmes de travail, fiches et constats sont
produits par l'usage. Un peuplement dédié pourra être ajouté à la fin du lot 6.
"""

from apps.core.demo import ContexteDemo


def peupler(ctx: ContexteDemo) -> None:
    ctx.ecrire("  accomplissement : aucune donnée de démonstration.")
