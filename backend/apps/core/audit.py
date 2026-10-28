from contextlib import AbstractContextManager, nullcontext
from typing import Any

from auditlog.context import set_actor
from auditlog.registry import auditlog


def register(model: Any, m2m_fields: set[str] | None = None) -> None:
    """Register a model in the audit trail (who/when/what changed).

    `m2m_fields` lists many-to-many fields whose additions/removals are logged too.
    """
    auditlog.register(model, exclude_fields=["updated_at"], m2m_fields=m2m_fields)


def actor_scope(by: Any) -> AbstractContextManager[Any]:
    """Context manager recording `by` as the audit actor outside a request (services).

    Inside a request an actor is already in the auditlog context and is kept as is.
    """
    from .models import _auditlog_actor_active

    return nullcontext() if _auditlog_actor_active() else set_actor(by)
