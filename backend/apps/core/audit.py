from typing import Any

from auditlog.registry import auditlog


def register(model: Any) -> None:
    """Register a model in the audit trail (who/when/what changed)."""
    auditlog.register(model, exclude_fields=["updated_at"])
