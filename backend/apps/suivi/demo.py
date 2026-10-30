"""Peuplement de démonstration : suivi des recommandations (aucune donnée pour l'instant)."""

from apps.core.demo import ContexteDemo


def peupler(ctx: ContexteDemo) -> None:
    ctx.ecrire("  suivi : aucune donnée de démonstration.")
