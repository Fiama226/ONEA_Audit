from django.db import models

from .exceptions import SuppressionPhysiqueInterditeError


class SoftDeleteQuerySet[T: models.Model](models.QuerySet[T]):
    def delete(self) -> tuple[int, dict[str, int]]:
        raise SuppressionPhysiqueInterditeError

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Maintenance only; never call from request code (owner connection only, see D6)."""
        from .gardes_sql import maintenance

        with maintenance():
            return super().delete()


class SoftDeleteManager[T: models.Model](models.Manager[T]):
    """Default manager: hides rows whose `deleted_at` is set."""

    def get_queryset(self) -> SoftDeleteQuerySet[T]:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class AllObjectsManager[T: models.Model](models.Manager[T]):
    """Includes soft-deleted rows; bulk physical deletion is still forbidden."""

    def get_queryset(self) -> SoftDeleteQuerySet[T]:
        return SoftDeleteQuerySet(self.model, using=self._db)
