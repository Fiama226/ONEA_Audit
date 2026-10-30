"""Programmes annuels de démonstration : le dernier reste en brouillon, les autres sont validés."""

from datetime import date, timedelta
from decimal import Decimal

from apps.core.demo import ContexteDemo

from .models import TypeIntervention
from .services import creer_ligne, creer_programme, valider_programme

ANNEES = (2024, 2025, 2026)
VERBES = ("Évaluation du dispositif de contrôle de", "Revue de", "Audit de", "Examen de")


def peupler(ctx: ContexteDemo) -> None:
    v, rai, rng = ctx.volumes, ctx.rai, ctx.rng
    processus, entites = ctx.etat["processus"], ctx.etat["entites"]
    for rang in range(v.programmes):
        annee = ANNEES[rang]
        programme = creer_programme(
            annee=annee, libelle=f"Programme annuel d'audit interne {annee} (démonstration)", by=rai
        )
        for i in range(v.lignes_par_programme):
            p = processus[i % len(processus)]
            debut = date(annee, rng.randint(1, 11), rng.randint(1, 28))
            creer_ligne(
                programme=programme,
                titre=f"{rng.choice(VERBES)} {p.libelle.lower()}",
                type=rng.choice(list(TypeIntervention)),
                processus=p,
                entites=rng.sample(entites, k=rng.choice((1, 2))),
                debut_prevu=debut,
                fin_prevue=debut + timedelta(days=rng.randint(10, 60)),
                charge_prevue_jours=Decimal(rng.randint(5, 60)),
                justification="Mission inscrite pour la démonstration.",
                by=rai,
            )
        if rang < v.programmes - 1:
            valider_programme(programme, by=rai)
