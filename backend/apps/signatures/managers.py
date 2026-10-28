"""Manager et QuerySet qui rendent les confirmations immuables.

Limite connue : le SQL brut (`cursor.execute`) et `hard_delete()` contournent ces gardes ;
c'est pourquoi `verifier` recalcule l'empreinte à partir des valeurs stockées.
"""

from typing import Any

from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet

from .exceptions import ConfirmationImmuableError


class ConfirmationQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        raise ConfirmationImmuableError

    def bulk_update(self, objs: Any, fields: Any, batch_size: int | None = None) -> int:
        raise ConfirmationImmuableError


class ConfirmationManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> ConfirmationQuerySet:
        return ConfirmationQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ConfirmationAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> ConfirmationQuerySet:
        return ConfirmationQuerySet(self.model, using=self._db)
