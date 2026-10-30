"""Confirmations de démonstration.

Aucune création directe : une confirmation n'existe que produite par les services qui la
requièrent (ordre de mission, déclarations d'indépendance, validation du référentiel), déjà
appelés par le peuplement des missions et de l'analyse.
"""

from apps.core.demo import ContexteDemo


def peupler(ctx: ContexteDemo) -> None:
    ctx.ecrire("  Confirmations produites par les services de mission et d'analyse.")
