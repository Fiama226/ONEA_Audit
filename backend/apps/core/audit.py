from typing import Any

from auditlog.registry import auditlog


def register(model: Any, m2m_fields: set[str] | None = None) -> None:
    """Register a model in the audit trail (who/when/what changed).

    `m2m_fields` lists many-to-many fields whose additions/removals are logged too.
    """
    auditlog.register(model, exclude_fields=["updated_at"], m2m_fields=m2m_fields)
