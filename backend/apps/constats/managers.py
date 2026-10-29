"""Managers des constats : numérotation, réponses de l'audité et journal en ajout seul.

Même principe que `missions/managers.py` : les gardes de `save()` ne suffisent pas, `update`,
`bulk_update` et `bulk_create(update_conflicts=True)` les appliquent aussi.
Limite connue : SQL brut, `_base_manager`, `hard_delete()` et la table de liaison `fiches.through`
utilisée directement contournent ces gardes.
"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from django.db import connection, transaction
from django.db.models import Max, Model

from apps.core.exceptions import RegleMetierError
from apps.missions.managers import (
    EvenementAllManager,
    EvenementManager,
    EvenementQuerySet,
    MissionEnfantAllManager,
    MissionEnfantManager,
    MissionEnfantQuerySet,
)

from .exceptions import MSG_EVENEMENT_AJOUT_SEUL, ReponseAjoutSeulError

LOCK_NUMERO_CONSTAT = 0x434F4E53  # « CONS »


def prochain_numero_constat(mission_id: UUID) -> int:
    """Prochain numéro de constat de la mission : maximum sur TOUTES les lignes.

    Les constats supprimés comptent : une référence n'est jamais réattribuée. Le verrou
    consultatif (par mission) tient jusqu'à la fin de la transaction courante.
    """
    from .models import Constat

    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
                [LOCK_NUMERO_CONSTAT, str(mission_id)],
            )
        maximum = Constat._base_manager.filter(mission_id=mission_id).aggregate(  # noqa: SLF001
            m=Max("numero")
        )["m"]
    return int(maximum or 0) + 1


class ReponseQuerySet[T: Model](MissionEnfantQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        raise ReponseAjoutSeulError

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        raise ReponseAjoutSeulError

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise ReponseAjoutSeulError
        return super().bulk_create(objs, *args, **kwargs)


class ReponseManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> ReponseQuerySet[T]:
        return ReponseQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ReponseAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> ReponseQuerySet[T]:
        return ReponseQuerySet(self.model, using=self._db)


class JournalConstatQuerySet[T: Model](EvenementQuerySet[T]):
    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(MSG_EVENEMENT_AJOUT_SEUL)
        return super().bulk_create(objs, *args, **kwargs)


class JournalConstatManager[T: Model](EvenementManager[T]):
    def get_queryset(self) -> JournalConstatQuerySet[T]:
        return JournalConstatQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class JournalConstatAllManager[T: Model](EvenementAllManager[T]):
    def get_queryset(self) -> JournalConstatQuerySet[T]:
        return JournalConstatQuerySet(self.model, using=self._db)
