"""Programmes annuels de démonstration : le dernier reste en brouillon, les autres sont validés
puis approuvés par la DG et le Conseil (règle de gouvernance par défaut). L'année des
missions de démonstration (2026) a toujours un programme approuvé."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.core.demo import ContexteDemo

from .models import NiveauApprobation, TypeIntervention
from .services import (
    approuver_programme,
    creer_ligne,
    creer_programme,
    niveaux_requis,
    valider_programme,
)

ANNEES = (2025, 2026, 2027)
VERBES = ("Évaluation du dispositif de contrôle de", "Revue de", "Audit de", "Examen de")


def peupler(ctx: ContexteDemo) -> None:
    v, rai, rng = ctx.volumes, ctx.rai, ctx.rng
    processus, entites = ctx.etat["processus"], ctx.etat["entites"]
    annees = ANNEES[-v.programmes :]
    for rang in range(v.programmes):
        annee = annees[rang]
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
            _approuver(ctx, programme, annee)


def _approuver(ctx: ContexteDemo, programme: Any, annee: int) -> None:
    dg = ctx.groupes["dg"][0]
    for niveau in niveaux_requis():
        conseil = niveau == NiveauApprobation.BOARD
        approuver_programme(
            programme,
            niveau=niveau,
            by=dg,
            date_decision=date(annee - 1, 12, 15 if conseil else 10),
            reference=f"Délibération n° {annee - 1}-12 (démonstration)" if conseil else "",
            commentaire="Approbation enregistrée pour la démonstration.",
        )
