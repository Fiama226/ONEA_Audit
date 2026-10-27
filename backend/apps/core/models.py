import contextlib
import uuid
from typing import TYPE_CHECKING, Any

from auditlog.context import auditlog_value, set_actor
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import pre_save
from django.utils import timezone

from .exceptions import SuppressionPhysiqueInterditeError
from .managers import AllObjectsManager, SoftDeleteManager

if TYPE_CHECKING:
    from apps.users.models import User


def _auditlog_actor_active() -> bool:
    """True when an auditlog context with a (resolvable) actor is currently live.

    The context var is never reset by auditlog, so a stale value is told apart from a
    live one by checking that its pre_save receiver is still connected.
    """
    ctx = auditlog_value.get(None)
    if not ctx or not isinstance(ctx.get("actor"), get_user_model()):
        return False
    return any(key[0] == ctx["signal_duid"] for key, *_ in pre_save.receivers)


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
        # set_actor records the actor outside a request (services, Celery). Inside a
        # request an actor is already in the auditlog context: nesting set_actor would
        # replace it and drop the outer remote_addr.
        has_actor = _auditlog_actor_active()
        with contextlib.nullcontext() if has_actor else set_actor(by):
            self.save(update_fields=["deleted_at", "updated_by", "updated_at"])

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise SuppressionPhysiqueInterditeError

    def hard_delete(self) -> None:
        """Physical deletion escape hatch for tests/admin maintenance.

        Must NEVER be called from request code (CLAUDE.md rule 4).
        """
        super().delete()
