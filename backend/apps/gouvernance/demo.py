"""Peuplement de démonstration : règles de gouvernance.

Aucune donnée : la démonstration garde les valeurs de référence (les plus prudentes), comme
une installation neuve. Les autres peuplements s'y conforment (programme approuvé, risques
couverts désignés, équipes objectives).
"""

from apps.core.demo import ContexteDemo


def peupler(ctx: ContexteDemo) -> None:
    ctx.ecrire("  Règles de gouvernance : valeurs de référence (aucune donnée de démonstration).")
