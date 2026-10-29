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

from apps.core.exceptions import RegleMetierError
from apps.missions.gardes import controler_ecriture, exiger_etape_ouverte

from .exceptions import MSG_AUTRE_MISSION, ConstatValideError
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


# Seuls champs que la sauvegarde de `rouvrir` peut changer sur un constat VALIDE.
CHAMPS_REOUVERTURE: frozenset[str] = frozenset(
    {"statut", "validee_par", "validee_le", "motif_renvoi"}
)
# Champs sans effet métier (calculés ou techniques) : ignorés par la comparaison.
_CHAMPS_IGNORES: frozenset[str] = frozenset({"updated_at", "updated_by", "score", "niveau"})


def _champs_modifies(constat: Constat, en_base: Constat) -> set[str]:
    return {
        f.name
        for f in Constat._meta.concrete_fields
        if f.name not in _CHAMPS_IGNORES
        and getattr(constat, f.attname) != getattr(en_base, f.attname)
    }


def controler_constat(constat: Constat) -> None:
    """Gel D10 : ligne VALIDE en base -> refus (sauf réouverture) ; XIV close -> refus."""
    if not constat._state.adding:
        en_base = Constat.all_objects.filter(pk=constat.pk).first()
        if en_base is not None and en_base.statut == StatutConstat.VALIDE:
            if _REOUVERTURE.get() != constat.pk or _champs_modifies(constat, en_base) - (
                CHAMPS_REOUVERTURE
            ):
                raise ConstatValideError(en_base.reference)
    exiger_etape_ouverte(constat.mission_id, ETAPE_CONSTATS)


def _constat_du_dependant(objet: Any) -> tuple[str, str, UUID] | None:
    return (
        Constat.all_objects.filter(pk=objet.constat_id)
        .values_list("statut", "reference", "mission_id")
        .first()
    )


def controler_dependant(objet: Any) -> None:
    """Cause ou recommandation : même gel que le constat auquel elle est rattachée."""
    ligne = _constat_du_dependant(objet)
    if ligne is not None:
        if ligne[2] != objet.mission_id:
            raise RegleMetierError(MSG_AUTRE_MISSION)
        if ligne[0] == StatutConstat.VALIDE:
            raise ConstatValideError(ligne[1])
    exiger_etape_ouverte(objet.mission_id, ETAPE_CONSTATS)


def controler_reponse(reponse: Any) -> None:
    """Gel D11 : une réponse s'ajoute tant que l'étape XV n'est pas close."""
    ligne = _constat_du_dependant(reponse)
    if ligne is not None and ligne[2] != reponse.mission_id:
        raise RegleMetierError(MSG_AUTRE_MISSION)
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
        controler_ecriture(constat)  # mission figée, puis VALIDE / XIV
    if action == "pre_add":
        _exiger_meme_mission(instance, reverse, constats, pk_set)


def _exiger_meme_mission(
    instance: Any, reverse: bool, constats: list[Constat], pk_set: set[Any] | None
) -> None:
    """Les fiches liées à un constat appartiennent à sa mission."""
    from apps.accomplissement.models import FicheDeTest

    if reverse:  # instance = la fiche
        autres = {c.mission_id for c in constats}
        attendue = instance.mission_id
    else:  # instance = le constat
        autres = set(
            FicheDeTest.all_objects.filter(pk__in=pk_set or []).values_list("mission_id", flat=True)
        )
        attendue = instance.mission_id
    if autres - {attendue}:
        raise RegleMetierError(MSG_AUTRE_MISSION)
