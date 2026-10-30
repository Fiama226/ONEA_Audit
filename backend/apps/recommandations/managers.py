"""Managers du plan d'actions : numérotation et gardes appliquées aux écritures en masse.

Limite connue (idem lots 3 et 6) : SQL brut, `_base_manager` et `hard_delete()` contournent
ces gardes.
"""

import copy
from collections.abc import Callable, Iterable
from typing import Any
from uuid import UUID

from django.db import connection
from django.db.models import Max, Model
from django.db.models.expressions import Combinable

from apps.core.exceptions import RegleMetierError
from apps.missions.managers import (
    MissionEnfantAllManager,
    MissionEnfantManager,
    MissionEnfantQuerySet,
)

from .exceptions import MSG_UPSERT_INTERDIT, EngagementAjoutSeulError

LOCK_NUMERO_ACTION = 0x41435449  # « ACTI »


def prochain_numero_action(mission_id: UUID) -> int:
    """Prochain numéro d'action : maximum sur TOUTES les lignes (jamais réattribué)."""
    from .models import Action

    if not connection.in_atomic_block:
        raise RuntimeError("prochain_numero_action doit être appelé dans une transaction.")
    with connection.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
            [LOCK_NUMERO_ACTION, str(mission_id)],
        )
    maximum = Action._base_manager.filter(mission_id=mission_id).aggregate(  # noqa: SLF001
        m=Max("numero")
    )["m"]
    return int(maximum or 0) + 1


type Controle = Callable[..., None]


class GardeDiffQuerySet[T: Model](MissionEnfantQuerySet[T]):
    """QuerySet qui compare la ligne en base à la ligne après écriture (garde `_garde`)."""

    def _garde(self, avant: T | None, apres: T, **kw: Any) -> None:
        raise NotImplementedError

    def update(self, **kwargs: Any) -> int:
        for ligne in list(self.order_by()):
            apres = copy.copy(ligne)
            forces: set[str] = set()
            for champ, valeur in kwargs.items():
                if isinstance(valeur, Combinable):
                    forces.add(self.model._meta.get_field(champ).name)
                else:
                    setattr(apres, champ, valeur)
            self._garde(ligne, apres, forces=forces)
        return super(MissionEnfantQuerySet, self).update(**kwargs)

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        objs = list(objs)
        fields = list(fields)
        tous: Any = self.model.all_objects  # type: ignore[attr-defined]
        en_base = {o.pk: o for o in tous.filter(pk__in=[o.pk for o in objs])}
        for obj in objs:
            self._garde(en_base.get(obj.pk), obj, touches=set(fields))
        return super(MissionEnfantQuerySet, self).bulk_update(objs, fields, batch_size)

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(MSG_UPSERT_INTERDIT)
        objs = list(objs)
        for obj in objs:
            self._garde(None, obj)
        return super(MissionEnfantQuerySet, self).bulk_create(objs, *args, **kwargs)


class ActionQuerySet[T: Model](GardeDiffQuerySet[T]):
    def _garde(self, avant: T | None, apres: T, **kw: Any) -> None:
        from . import gardes

        gardes.controler_action(avant, apres, **kw)  # type: ignore[arg-type]


class AcceptationQuerySet[T: Model](GardeDiffQuerySet[T]):
    def _garde(self, avant: T | None, apres: T, **kw: Any) -> None:
        from . import gardes

        gardes.controler_acceptation(avant, apres, **kw)


class EngagementQuerySet[T: Model](MissionEnfantQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        raise EngagementAjoutSeulError

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        raise EngagementAjoutSeulError

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise EngagementAjoutSeulError
        return super().bulk_create(objs, *args, **kwargs)


class ActionManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> ActionQuerySet[T]:
        return ActionQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ActionAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> ActionQuerySet[T]:
        return ActionQuerySet(self.model, using=self._db)


class AcceptationManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> AcceptationQuerySet[T]:
        return AcceptationQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class AcceptationAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> AcceptationQuerySet[T]:
        return AcceptationQuerySet(self.model, using=self._db)


class EngagementManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> EngagementQuerySet[T]:
        return EngagementQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class EngagementAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> EngagementQuerySet[T]:
        return EngagementQuerySet(self.model, using=self._db)
