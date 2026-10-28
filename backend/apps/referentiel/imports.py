"""Import idempotent du référentiel (directions, départements, processus) depuis un CSV.

Format : UTF-8 (BOM toléré), séparateur « ; », en-tête exact `EN_TETE`. Trois passes
(directions, départements, processus) dans une seule transaction : la moindre erreur annule
tout. Les écritures passent par les services ; rien n'est jamais supprimé.
"""

import csv
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from functools import partial
from typing import TextIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.users.models import User

from . import services
from .models import Direction, FamilleProcessus, Processus, TypeEntite
from .validators import (
    CARACTERES_CONTROLE_RE,
    valider_code_direction,
    valider_code_processus,
)

EN_TETE = "type;code;libelle;famille;ordre;parent;directions"
MAX_LIGNES = 5000
_ORDRE_MAX = 32767
_TYPE_PROCESSUS = "PROCESSUS"
_TYPES = {TypeEntite.DIRECTION.value, TypeEntite.DEPARTEMENT.value, _TYPE_PROCESSUS}

MSG_EN_TETE = f"En-tête attendu : {EN_TETE}"
MSG_TROP_VOLUMINEUX = "Fichier trop volumineux : 5 000 lignes au maximum."
MSG_ENCODAGE = "Encodage invalide : enregistrez le fichier en UTF-8."


class ImportReferentielError(Exception):
    def __init__(self, erreurs: list[str]) -> None:
        super().__init__("\n".join(erreurs))
        self.erreurs = erreurs


def _compteurs() -> dict[str, int]:
    return {"directions": 0, "departements": 0, "processus": 0}


@dataclass
class RapportImport:
    crees: dict[str, int] = field(default_factory=_compteurs)
    mis_a_jour: dict[str, int] = field(default_factory=_compteurs)
    inchanges: int = 0


@dataclass
class _Ligne:
    numero: int
    type: str
    code: str
    libelle: str
    famille: str = ""
    ordre: int = 0
    parent: str = ""
    directions: list[str] = field(default_factory=list)


def _normaliser(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFD", texte)
    return "".join(c for c in sans_accent if not unicodedata.combining(c)).strip().upper()


_FAMILLES = {_normaliser(f.value): f.value for f in FamilleProcessus} | {
    _normaliser(f.label): f.value for f in FamilleProcessus
}


class _CsvIllisibleError(Exception):
    def __init__(self, numero: int) -> None:
        super().__init__(numero)
        self.numero = numero


def _lire(flux: TextIO) -> Iterator[tuple[int, list[str]]]:
    lecteur = csv.reader(flux, delimiter=";")
    try:
        for cellules in lecteur:
            yield lecteur.line_num, cellules
    except csv.Error as e:  # champ dépassant la limite du module csv, etc.
        raise _CsvIllisibleError(lecteur.line_num) from e


def _parser(flux: TextIO) -> list[_Ligne]:
    """Lit et valide la forme du fichier ; lève `ImportReferentielError` avec toutes les erreurs."""
    lignes: list[_Ligne] = []
    erreurs: list[str] = []
    vues: dict[tuple[bool, str], int] = {}
    en_tete_lu = False
    nb_donnees = 0
    try:
        for numero, cellules in _lire(flux):
            if not en_tete_lu:
                en_tete_lu = True
                cellules = [cellules[0].lstrip("﻿"), *cellules[1:]] if cellules else cellules
                if ";".join(c.strip() for c in cellules) != EN_TETE:
                    raise ImportReferentielError([MSG_EN_TETE])
                continue
            if not any(c.strip() for c in cellules):
                continue
            nb_donnees += 1
            if nb_donnees > MAX_LIGNES:
                raise ImportReferentielError([MSG_TROP_VOLUMINEUX])
            ligne = _parser_ligne(numero, cellules, erreurs, vues)
            if ligne is not None:
                lignes.append(ligne)
    except UnicodeDecodeError as e:
        raise ImportReferentielError([MSG_ENCODAGE]) from e
    except _CsvIllisibleError as e:
        erreurs.append(f"Ligne {e.numero} : champ illisible ou trop long.")
        raise ImportReferentielError(erreurs) from e
    if not en_tete_lu:
        raise ImportReferentielError([MSG_EN_TETE])
    if erreurs:
        raise ImportReferentielError(erreurs)
    return lignes


def _parser_ligne(
    numero: int,
    cellules: list[str],
    erreurs: list[str],
    vues: dict[tuple[bool, str], int],
) -> _Ligne | None:
    def erreur(message: str) -> None:
        erreurs.append(f"Ligne {numero} : {message}")

    if len(cellules) != 7:
        erreur(f"7 colonnes attendues, {len(cellules)} trouvées.")
        return None
    if any(CARACTERES_CONTROLE_RE.search(c) for c in cellules):
        erreur("caractère de contrôle interdit.")
        return None
    type_, code, libelle, famille, ordre, parent, directions = (c.strip() for c in cellules)
    type_ = type_.upper()
    if type_ not in _TYPES:
        erreur(
            "type « " + cellules[0].strip() + " » inconnu (DIRECTION, DEPARTEMENT ou PROCESSUS)."
        )
        return None
    if not code:
        erreur("code manquant.")
        return None
    validateur = valider_code_processus if type_ == _TYPE_PROCESSUS else valider_code_direction
    try:
        validateur(code)
    except ValidationError:
        erreur(f"code « {code} » invalide.")
        return None
    cle = (type_ == _TYPE_PROCESSUS, code)
    if cle in vues:
        erreur(f"code « {code} » en doublon (déjà présent ligne {vues[cle]}).")
        return None
    vues[cle] = numero
    if not libelle:
        erreur("libellé manquant.")
        return None

    ligne = _Ligne(numero=numero, type=type_, code=code, libelle=libelle)
    if type_ == TypeEntite.DIRECTION:
        if parent:
            erreur("une direction ne peut pas avoir de parent.")
            return None
    elif type_ == TypeEntite.DEPARTEMENT:
        if not parent:
            erreur("un département doit être rattaché à une direction (colonne parent).")
            return None
        ligne.parent = parent
    else:
        valeur_famille = _FAMILLES.get(_normaliser(famille))
        if valeur_famille is None:
            erreur(f"famille « {famille} » inconnue (Pilotage, Réalisation ou Support).")
            return None
        ligne.famille = valeur_famille
        if ordre:
            if not (ordre.isascii() and ordre.isdigit()) or int(ordre) > _ORDRE_MAX:
                erreur(f"ordre « {ordre} » invalide (entier de 0 à {_ORDRE_MAX}).")
                return None
            ligne.ordre = int(ordre)
        ligne.directions = [c.strip() for c in directions.split(",") if c.strip()]
    return ligne


def _message(e: RegleMetierError | Http404) -> str:
    if isinstance(e, RegleMetierError) and e.errors:
        return " ".join(m for messages in e.errors.values() for m in messages)
    return str(e)


def importer_referentiel(flux: TextIO, *, by: User, dry_run: bool = False) -> RapportImport:
    """Importe le référentiel ; lève `ImportReferentielError` (rien n'est alors écrit)."""
    lignes = _parser(flux)
    rapport = RapportImport()
    erreurs: list[str] = []
    with actor_scope(by), transaction.atomic():
        _passe_directions(lignes, by, rapport, erreurs, departements=False)
        _passe_directions(lignes, by, rapport, erreurs, departements=True)
        _passe_processus(lignes, by, rapport, erreurs)
        if erreurs:
            transaction.set_rollback(True)
            raise ImportReferentielError(sorted(erreurs, key=lambda e: int(e.split()[1])))
        if dry_run:
            transaction.set_rollback(True)
    return rapport


def _executer(ligne: _Ligne, erreurs: list[str], action: Callable[[], object]) -> bool:
    """Exécute `action()` ; convertit une règle métier refusée en erreur ligne."""
    try:
        with transaction.atomic():
            action()
    except (RegleMetierError, Http404) as e:
        erreurs.append(f"Ligne {ligne.numero} : {_message(e)}")
        return False
    return True


def _passe_directions(
    lignes: list[_Ligne],
    by: User,
    rapport: RapportImport,
    erreurs: list[str],
    *,
    departements: bool,
) -> None:
    type_ = TypeEntite.DEPARTEMENT if departements else TypeEntite.DIRECTION
    cle = "departements" if departements else "directions"
    for ligne in (li for li in lignes if li.type == type_):
        parent: Direction | None = None
        if departements:
            parent = Direction.objects.filter(code=ligne.parent, type=TypeEntite.DIRECTION).first()
            if parent is None:
                erreurs.append(f"Ligne {ligne.numero} : direction « {ligne.parent} » introuvable.")
                continue
        existante = Direction.objects.filter(code=ligne.code).select_related("parent").first()
        if existante is None:
            ok = _executer(
                ligne,
                erreurs,
                partial(
                    services.creer_direction,
                    code=ligne.code,
                    libelle=ligne.libelle,
                    type=ligne.type,
                    parent=parent,
                    by=by,
                ),
            )
            if ok:
                rapport.crees[cle] += 1
        elif existante.type != type_:
            erreurs.append(
                f"Ligne {ligne.numero} : le code « {ligne.code} » existe déjà avec un autre type."
            )
        elif existante.libelle == ligne.libelle and existante.parent_id == (
            parent.pk if parent else None
        ):
            rapport.inchanges += 1
        else:
            ok = _executer(
                ligne,
                erreurs,
                partial(
                    services.modifier_direction,
                    existante,
                    libelle=ligne.libelle,
                    parent=parent,
                    by=by,
                ),
            )
            if ok:
                rapport.mis_a_jour[cle] += 1


def _passe_processus(
    lignes: list[_Ligne], by: User, rapport: RapportImport, erreurs: list[str]
) -> None:
    for ligne in (li for li in lignes if li.type == _TYPE_PROCESSUS):
        trouvees = {
            d.code: d
            for d in Direction.objects.filter(code__in=ligne.directions, type=TypeEntite.DIRECTION)
        }
        absentes = [c for c in dict.fromkeys(ligne.directions) if c not in trouvees]
        if absentes:
            noms = ", ".join(f"« {c} »" for c in absentes)
            erreurs.append(f"Ligne {ligne.numero} : direction(s) {noms} introuvable(s).")
            continue
        cibles = list(trouvees.values())
        existant = Processus.objects.filter(code=ligne.code).first()
        if existant is None:
            ok = _executer(
                ligne,
                erreurs,
                partial(
                    services.creer_processus,
                    code=ligne.code,
                    libelle=ligne.libelle,
                    famille=ligne.famille,
                    ordre=ligne.ordre,
                    directions=cibles,
                    by=by,
                ),
            )
            if ok:
                rapport.crees["processus"] += 1
        elif (
            existant.libelle == ligne.libelle
            and existant.famille == ligne.famille
            and existant.ordre == ligne.ordre
            and set(existant.directions.values_list("pk", flat=True)) == {d.pk for d in cibles}
        ):
            rapport.inchanges += 1
        else:
            ok = _executer(
                ligne,
                erreurs,
                partial(
                    services.modifier_processus,
                    existant,
                    libelle=ligne.libelle,
                    famille=ligne.famille,
                    ordre=ligne.ordre,
                    directions=cibles,
                    by=by,
                ),
            )
            if ok:
                rapport.mis_a_jour["processus"] += 1
