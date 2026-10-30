"""Peuplement de démonstration : notifications.

Les notifications sont produites par les services du suivi : rien à créer ici.
"""

from apps.core.demo import ContexteDemo


def peupler(ctx: ContexteDemo) -> None:
    ctx.ecrire("  notifications : aucune donnée de démonstration.")
