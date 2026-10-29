"""Gardes de gel des constats (D10, D11 du plan du lot 6).

Elles lisent l'état EN BASE (jamais l'instance seule) et sont appelées par
`exiger_travaux_ouverts()` des modèles, donc par `save()`, `update`, `bulk_update` et
`bulk_create`, ainsi que par le récepteur `m2m_changed` des fiches d'un constat.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from apps.missions.gardes import exiger_etape_ouverte

from .exceptions import ConstatValideError
from .models import Constat, StatutConstat

ETAPE_CONSTATS = 14
ETAPE_REUNION_CLOTURE = 15

# Pk du constat en cours de réouverture (seule écriture permise sur un constat VALIDE).
_REOUVERTURE: ContextVar[UUID | None] = ContextVar("reouverture_constat", default=None)

_ACTIONS_GARDEES = frozenset({"pre_add", "pre_remove", "pre_clear"})


@contextmanager
def reouverture(constat_id: UUID) -> Iterator[None]:
    """Autorise l'écriture de la réouverture d'un constat validé dans ce bloc."""
    jeton = _REOUVERTURE.set(constat_id)
    try:
        yield
    finally:
        _REOUVERTURE.reset(jeton)


def controler_constat(constat: Constat) -> None:
    """Gel D10 : ligne VALIDE en base -> refus (sauf réouverture) ; XIV close -> refus."""
    if not constat._state.adding:
        en_base = Constat.all_objects.filter(pk=constat.pk).values_list("statut", "reference")
        ligne = en_base.first()
        if (
            ligne is not None
            and ligne[0] == StatutConstat.VALIDE
            and _REOUVERTURE.get() != constat.pk
        ):
            raise ConstatValideError(ligne[1])
    exiger_etape_ouverte(constat.mission_id, ETAPE_CONSTATS)


def controler_dependant(objet: Any) -> None:
    """Cause ou recommandation : même gel que le constat auquel elle est rattachée."""
    ligne = (
        Constat.all_objects.filter(pk=objet.constat_id).values_list("statut", "reference").first()
    )
    if ligne is not None and ligne[0] == StatutConstat.VALIDE:
        raise ConstatValideError(ligne[1])
    exiger_etape_ouverte(objet.mission_id, ETAPE_CONSTATS)


def controler_reponse(reponse: Any) -> None:
    """Gel D11 : une réponse s'ajoute tant que l'étape XV n'est pas close."""
    exiger_etape_ouverte(reponse.mission_id, ETAPE_REUNION_CLOTURE)


def garder_fiches(
    sender: type,
    instance: Any,
    action: str,
    reverse: bool,
    pk_set: set[Any] | None,
    **_: object,
) -> None:
    """Récepteur `m2m_changed` de `Constat.fiches` : même garde que le constat (les deux sens)."""
    if action not in _ACTIONS_GARDEES:
        return
    if not reverse:
        constats = [instance]
    elif action == "pre_clear":  # fiche.constats.clear() : instance = la fiche
        constats = list(Constat.all_objects.filter(fiches=instance))
    else:
        constats = list(Constat.all_objects.filter(pk__in=pk_set or []))
    for constat in constats:
        controler_constat(constat)
