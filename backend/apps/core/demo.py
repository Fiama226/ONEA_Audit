"""Données de démonstration : registre des peuplements, contexte partagé et garde d'environnement.

Règles du lot 9 (tâche 4) :

- jamais lancé automatiquement : seule la commande `peupler_demo` (opt-in) y recourt ;
- refus en production (et en recette sans l'option explicite `--recette`) ;
- toutes les données passent par les services publics des applications (règles, machines à
  états et gels respectés, piste d'audit alimentée) : aucun SQL brut, aucun contournement ;
- déterministe : toute valeur aléatoire vient de `ContexteDemo.rng` (graine) ;
- aucune donnée personnelle réelle : noms fictifs, adresses en `@example.org`.

Chaque application à modèles expose `apps.<label>.demo.peupler(ctx)` et figure dans `ORDRE`
(ordre des dépendances). Le test d'exhaustivité l'impose pour toute nouvelle application.
"""

import importlib
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.core.management.base import CommandError
from django.db import transaction

# Ordre des dépendances : comptes -> référentiel -> programme -> missions -> analyse ->
# signatures (rien à créer : produites par les services de mission) -> documents.
ORDRE: tuple[str, ...] = (
    "users",
    "referentiel",
    "programmation",
    "missions",
    "analyse",
    "signatures",
    "core",
    "accomplissement",
    "constats",
    "documents",
    "notifications",
)
# Les documents écrivent des fichiers et lancent leurs propres transactions : hors bloc atomique.
SANS_TRANSACTION_GLOBALE = frozenset({"documents"})

PROFILS = ("formation", "volumetrie")
GRAINE_PAR_DEFAUT = 2026
ACTEUR = "demo"


@dataclass(frozen=True)
class Volumes:
    utilisateurs: int  # comptes actifs (hors acteur système)
    comptes_charge: int  # dont comptes « chargeNN » (volumétrie)
    processus: int
    entites: int  # directions + départements
    directions: int
    cartographies: int
    risques_par_cartographie: int
    programmes: int
    lignes_par_programme: int
    missions: int
    versions: int


_BASE: dict[str, dict[str, int]] = {
    "volumetrie": {
        "nommes": 20,
        "charge": 40,
        "processus": 11,
        "entites": 30,
        "cartographies": 3,
        "risques": 150,
        "programmes": 3,
        "lignes": 40,
        "missions": 60,
        "versions": 300,
    },
    "formation": {
        "nommes": 7,
        "charge": 0,
        "processus": 5,
        "entites": 8,
        "cartographies": 2,
        "risques": 30,
        "programmes": 2,
        "lignes": 8,
        "missions": 6,
        "versions": 12,
    },
}


def _echelonner(valeur: int, echelle: float, plancher: int) -> int:
    return max(plancher, round(valeur * echelle))


def volumes(profil: str, echelle: float) -> Volumes:
    """Volumes d'un profil à l'échelle `echelle` (1 = volumes du cahier des charges)."""
    if profil not in _BASE:
        raise CommandError(f"Profil inconnu : {profil}.")
    if not echelle > 0:
        raise CommandError("L'échelle doit être un nombre strictement positif.")
    b = _BASE[profil]
    charge = _echelonner(b["charge"], echelle, 2) if b["charge"] else 0
    entites = _echelonner(b["entites"], echelle, 4)
    return Volumes(
        utilisateurs=b["nommes"] + charge,
        comptes_charge=charge,
        processus=_echelonner(b["processus"], echelle, 3),
        entites=entites,
        directions=max(2, round(entites * 8 / 30)),
        cartographies=b["cartographies"],
        risques_par_cartographie=_echelonner(b["risques"], echelle, 6),
        programmes=b["programmes"],
        lignes_par_programme=_echelonner(b["lignes"], echelle, 4),
        missions=_echelonner(b["missions"], echelle, 4 if profil == "volumetrie" else 6),
        versions=_echelonner(b["versions"], echelle, 6),
    )


def verifier_environnement(*, recette: bool) -> None:
    """Refuse la production ; la recette n'est admise qu'avec l'option explicite."""
    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    nom = module.rsplit(".", 1)[-1]
    if "prod" in nom:
        raise CommandError("Interdit en production.")
    if nom == "recette":
        if not recette:
            raise CommandError(
                "Environnement de recette : relancez avec l'option explicite --recette."
            )
        return
    if nom not in {"dev", "test"}:
        raise CommandError(
            f"Environnement « {module or 'inconnu'} » non reconnu : "
            "seuls dev, test et recette (avec --recette) sont autorisés."
        )


@dataclass
class ContexteDemo:
    profil: str
    echelle: float
    graine: int
    volumes: Volumes
    avec_pdf: bool = False
    sortie: Callable[[str], None] = print
    rng: random.Random = field(init=False)
    acteur: Any = None  # compte système « demo » (piste d'audit)
    groupes: dict[str, list[Any]] = field(default_factory=dict)
    etat: dict[str, Any] = field(default_factory=dict)
    finaliseurs: list[Callable[[], None]] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.graine)  # noqa: S311 - données fictives, non cryptographiques

    @property
    def rai(self) -> Any:
        return self.groupes["rai"][0]

    def ecrire(self, message: str) -> None:
        self.sortie(message)

    def avertir(self, message: str) -> None:
        self.avertissements.append(message)


def peupler(ctx: ContexteDemo) -> None:
    ctx.ecrire("  Consultations : produites par l'usage (aucune donnée de démonstration).")


def peupler_application(label: str, ctx: ContexteDemo) -> None:
    module = importlib.import_module(f"apps.{label}.demo")
    module.peupler(ctx)


def peupler_tout(ctx: ContexteDemo) -> None:
    for label in ORDRE:
        debut = time.monotonic()
        if label in SANS_TRANSACTION_GLOBALE:
            peupler_application(label, ctx)
        else:
            with transaction.atomic():
                peupler_application(label, ctx)
        ctx.ecrire(f"Peuplement : {label} ({time.monotonic() - debut:.1f} s)")
    for finaliseur in ctx.finaliseurs:
        finaliseur()
