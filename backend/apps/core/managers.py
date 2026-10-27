from django.db import models


class SoftDeleteManager[T: models.Model](models.Manager[T]):
    """Default manager: hides rows whose `deleted_at` is set."""

    def get_queryset(self) -> models.QuerySet[T]:
        return super().get_queryset().filter(deleted_at__isnull=True)
