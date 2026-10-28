from contextlib import AbstractContextManager, nullcontext
from typing import Any

from auditlog.context import auditlog_value, set_actor
from auditlog.registry import auditlog
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save


def register(model: Any, m2m_fields: set[str] | None = None) -> None:
    """Register a model in the audit trail (who/when/what changed).

    `m2m_fields` lists many-to-many fields whose additions/removals are logged too.
    """
    auditlog.register(model, exclude_fields=["updated_at"], m2m_fields=m2m_fields)


def actor_is_live() -> bool:
    """True when an auditlog context with a (resolvable) actor is currently live.

    The context var is never reset by auditlog, so a stale value is told apart from a
    live one by checking that its pre_save receiver is still connected.
    """
    ctx = auditlog_value.get(None)
    if not ctx or not isinstance(ctx.get("actor"), get_user_model()):
        return False
    return any(key[0] == ctx["signal_duid"] for key, *_ in pre_save.receivers)


def actor_scope(by: Any) -> AbstractContextManager[Any]:
    """Context manager recording `by` as the audit actor outside a request (services).

    Inside a request an actor is already in the auditlog context and is kept as is:
    nesting set_actor would replace it and drop the outer remote_addr.
    """
    return nullcontext() if actor_is_live() else set_actor(by)
