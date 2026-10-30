"""Manager et QuerySet d'une notification : seuls les champs d'état changent.

Limite connue : le SQL brut et `hard_delete()` contournent ces gardes.
"""

from collections.abc import Iterable
from typing import Any

from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet

from .exceptions import NotificationImmuableError

CHAMPS_MODIFIABLES = frozenset({"lue_le", "deleted_at", "updated_at", "updated_by"})


def verifier_champs(champs: Iterable[str]) -> None:
    interdits = set(champs) - CHAMPS_MODIFIABLES
    if interdits:
        raise NotificationImmuableError


class NotificationQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        verifier_champs(kwargs)
        return super().update(**kwargs)

    def bulk_update(self, objs: Any, fields: Any, batch_size: int | None = None) -> int:
        verifier_champs(fields)
        return super().bulk_update(objs, fields, batch_size)

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise NotificationImmuableError
        return super().bulk_create(objs, *args, **kwargs)


class NotificationManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> NotificationQuerySet:
        return NotificationQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class NotificationAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> NotificationQuerySet:
        return NotificationQuerySet(self.model, using=self._db)
