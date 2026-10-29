"""Grille de séparation des tâches (outil II, D6)."""

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from django.db import transaction

from apps.core.services import enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.referentiel.models import Processus
from apps.users.models import User

from ..models import GrilleSeparation, RoleTache
from ._fenetres import ouvrir_iii
from .descriptions import controler_processus

MAX_TACHES = 100
MAX_ACTEURS = 30
MSG_LIMITES = "La grille est limitée à 100 tâches et 30 acteurs."

INCOMPATIBLES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({RoleTache.EXECUTE.value, RoleTache.AUTORISE.value}),
        frozenset({RoleTache.EXECUTE.value, RoleTache.CONTROLE.value}),
        frozenset({RoleTache.ENREGISTRE.value, RoleTache.CONTROLE.value}),
    }
)


@dataclass(frozen=True)
class Cumul:
    tache: str
    acteur: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class AnalyseGrille:
    taches_sans_acteur: list[str]
    taches_multi_executants: list[str]
    cumuls: list[Cumul]


def analyser_grille(grille: GrilleSeparation) -> AnalyseGrille:
    """Analyse pure : tâches sans acteur, multi-exécutants, cumuls incompatibles."""
    taches: list[str] = list(grille.taches)
    acteurs: list[str] = list(grille.acteurs)
    cellules = sorted(grille.cellules, key=lambda c: (c["tache"], c["acteur"]))
    avec_acteur: set[int] = set()
    executants: dict[int, int] = {}
    cumuls: list[Cumul] = []
    for cellule in cellules:
        roles = set(cellule["roles"])
        if not roles:
            continue
        i = cellule["tache"]
        avec_acteur.add(i)
        if RoleTache.EXECUTE.value in roles:
            executants[i] = executants.get(i, 0) + 1
        if any(frozenset(paire) in INCOMPATIBLES for paire in combinations(sorted(roles), 2)):
            cumuls.append(Cumul(taches[i], acteurs[cellule["acteur"]], tuple(sorted(roles))))
    return AnalyseGrille(
        taches_sans_acteur=[t for i, t in enumerate(taches) if i not in avec_acteur],
        taches_multi_executants=[t for i, t in enumerate(taches) if executants.get(i, 0) > 1],
        cumuls=cumuls,
    )


def _libelles(valeurs: Any, champ: str, maximum: int, nom: str) -> list[str]:
    if not isinstance(valeurs, list | tuple):
        message = f"La liste des {nom} est invalide."
        raise refuser(message, **{champ: message})
    if len(valeurs) > maximum:
        raise refuser(MSG_LIMITES, **{champ: MSG_LIMITES})
    if not valeurs:
        message = f"Ajoutez au moins un élément à la liste des {nom}."
        raise refuser(message, **{champ: message})
    propres: list[str] = []
    for valeur in valeurs:
        if not isinstance(valeur, str) or not valeur.strip():
            message = "Le libellé ne peut pas être vide."
            raise refuser(message, **{champ: message})
        propres.append(valeur.strip())
    return propres


def _indice(valeur: Any, borne: int) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool) and 0 <= valeur < borne


def _cellules(valeurs: Any, nb_taches: int, nb_acteurs: int) -> list[dict[str, Any]]:
    if not isinstance(valeurs, list | tuple):
        message = "La liste des cellules est invalide."
        raise refuser(message, cellules=message)
    vues: set[tuple[int, int]] = set()
    propres: list[dict[str, Any]] = []
    for cellule in valeurs:
        if not isinstance(cellule, dict):
            message = "Cellule invalide."
            raise refuser(message, cellules=message)
        i: Any = cellule.get("tache")
        j: Any = cellule.get("acteur")
        if not _indice(i, nb_taches):
            message = f"Indice de tâche hors de la grille : {i}."
            raise refuser(message, cellules=message)
        if not _indice(j, nb_acteurs):
            message = f"Indice d'acteur hors de la grille : {j}."
            raise refuser(message, cellules=message)
        roles = cellule.get("roles")
        if not isinstance(roles, list | tuple):
            message = "Les rôles d'une cellule doivent former une liste."
            raise refuser(message, cellules=message)
        for role in roles:
            if role not in RoleTache.values:
                message = f"Rôle inconnu : {role}."
                raise refuser(message, cellules=message)
        if (i, j) in vues:
            message = f"Cellule en double pour la tâche {i} et l'acteur {j}."
            raise refuser(message, cellules=message)
        vues.add((i, j))
        ordonnes = [r.value for r in RoleTache if r.value in roles]
        propres.append({"tache": i, "acteur": j, "roles": ordonnes})
    return propres


@transaction.atomic
def enregistrer_grille(
    mission: Mission,
    *,
    processus: Processus,
    taches: list[str],
    acteurs: list[str],
    cellules: list[dict[str, Any]],
    by: User,
    commentaire: str = "",
) -> GrilleSeparation:
    mission = ouvrir_iii(mission)
    controler_processus(mission, processus)
    taches_ok = _libelles(taches, "taches", MAX_TACHES, "tâches")
    acteurs_ok = _libelles(acteurs, "acteurs", MAX_ACTEURS, "acteurs")
    cellules_ok = _cellules(cellules, len(taches_ok), len(acteurs_ok))
    existante = GrilleSeparation.objects.filter(mission=mission, processus=processus).first()
    if existante is None:
        grille = GrilleSeparation(mission=mission, processus=processus)
        creation = True
    else:
        grille = relire(existante)
        creation = False
    grille.taches = taches_ok
    grille.acteurs = acteurs_ok
    grille.cellules = cellules_ok
    grille.commentaire = commentaire
    enregistrer(grille, by=by, creation=creation)
    return grille


@transaction.atomic
def retirer_grille(grille: GrilleSeparation, *, by: User) -> None:
    ouvrir_iii(grille.mission)
    relire(grille).soft_delete(by)
