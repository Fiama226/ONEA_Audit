import uuid
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from .audit import actor_scope
from .exceptions import SuppressionPhysiqueInterditeError
from .managers import AllObjectsManager, SoftDeleteManager

if TYPE_CHECKING:
    from apps.users.models import User


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()  # noqa: DJ012

    class Meta:
        abstract = True

    def soft_delete(self, by: "User") -> None:
        """Logical deletion: never remove the row, keep the audit trail."""
        if self.deleted_at is not None:
            return
        self.deleted_at = timezone.now()
        self.updated_by = by
        with actor_scope(by):
            self.save(update_fields=["deleted_at", "updated_by", "updated_at"])

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise SuppressionPhysiqueInterditeError

    def hard_delete(self) -> None:
        """Physical deletion escape hatch for tests/admin maintenance.

        Must NEVER be called from request code (CLAUDE.md rule 4).
        """
        super().delete()
