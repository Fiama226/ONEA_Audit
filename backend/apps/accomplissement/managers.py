"""Managers de l'accomplissement : pièces (champs de fichier immuables), journaux en ajout seul.

Même principe que `missions/managers.py` : les gardes de `save()` ne suffisent pas, `update`,
`bulk_update` et `bulk_create(update_conflicts=True)` les appliquent aussi.
Limite connue : SQL brut, `_base_manager` et `hard_delete()` contournent ces gardes.
"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from django.db import models, transaction
from django.db.models import Max, Model

from apps.core.exceptions import RegleMetierError
from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet
from apps.missions.managers import (
    EvenementAllManager,
    EvenementManager,
    EvenementQuerySet,
    MissionEnfantAllManager,
    MissionEnfantManager,
    MissionEnfantQuerySet,
)

from .exceptions import MSG_AJOUT_SEUL, InstantaneImmuableError


def prochain_numero(modele: type[models.Model], mission_id: UUID) -> int:
    """Prochain numéro de la mission : maximum sur TOUTES les lignes (supprimées incluses).

    Le verrou de la ligne de mission sérialise les attributions concurrentes.
    """
    from apps.missions.models import Mission

    with transaction.atomic():
        Mission.all_objects.select_for_update().filter(pk=mission_id).first()
        maximum = modele._base_manager.filter(mission_id=mission_id).aggregate(m=Max("numero"))["m"]
    return int(maximum or 0) + 1


class PieceQuerySet[T: Model](MissionEnfantQuerySet[T]):
    def _refuser_champs_fichier(self, champs: Iterable[str]) -> None:
        from .gardes import CHAMPS_FICHIER, champs_ecrits

        if champs_ecrits(champs) & CHAMPS_FICHIER:
            from .exceptions import PieceImmuableError

            raise PieceImmuableError

    def update(self, **kwargs: Any) -> int:
        self._refuser_champs_fichier(kwargs)
        return super().update(**kwargs)

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        fields = list(fields)
        self._refuser_champs_fichier(fields)
        return super().bulk_update(objs, fields, batch_size)

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            from .exceptions import PieceImmuableError

            raise PieceImmuableError
        return super().bulk_create(objs, *args, **kwargs)


class PieceManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> PieceQuerySet[T]:
        return PieceQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class PieceAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> PieceQuerySet[T]:
        return PieceQuerySet(self.model, using=self._db)


class JournalFicheQuerySet[T: Model](EvenementQuerySet[T]):
    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(MSG_AJOUT_SEUL)
        return super().bulk_create(objs, *args, **kwargs)


class JournalFicheManager[T: Model](EvenementManager[T]):
    def get_queryset(self) -> JournalFicheQuerySet[T]:
        return JournalFicheQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class JournalFicheAllManager[T: Model](EvenementAllManager[T]):
    def get_queryset(self) -> JournalFicheQuerySet[T]:
        return JournalFicheQuerySet(self.model, using=self._db)


class InstantaneQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        raise InstantaneImmuableError

    def bulk_update(self, objs: Any, fields: Any, batch_size: int | None = None) -> int:
        raise InstantaneImmuableError

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise InstantaneImmuableError
        from apps.missions.gardes import refuser_si_figee

        objs = list(objs)
        for obj in objs:
            refuser_si_figee(obj.mission_id)
        return super().bulk_create(objs, *args, **kwargs)


class InstantaneManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> InstantaneQuerySet:
        return InstantaneQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class InstantaneAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> InstantaneQuerySet:
        return InstantaneQuerySet(self.model, using=self._db)
