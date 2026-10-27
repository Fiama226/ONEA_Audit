from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .exceptions import RegleMetierError

INVALID_DATA = "Données invalides."


def _flatten(detail: Any, path: str = "") -> dict[str, list[str]]:
    """Flatten DRF nested error details into {"a.b.0.c": [messages]}."""
    out: dict[str, list[str]] = {}
    if isinstance(detail, dict):
        for key, value in detail.items():
            out.update(_flatten(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(detail, list):
        messages = [str(item) for item in detail if not isinstance(item, dict | list)]
        if messages:
            out.setdefault(path or "non_field_errors", []).extend(messages)
        for index, item in enumerate(detail):
            if isinstance(item, dict | list):
                out.update(_flatten(item, f"{path}.{index}" if path else str(index)))
    else:
        out[path or "non_field_errors"] = [str(detail)]
    return out


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, RegleMetierError):
        return Response(
            {"detail": exc.message, "errors": exc.errors},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        response.data = {"detail": INVALID_DATA, "errors": _flatten(exc.detail)}
    elif isinstance(exc, APIException):
        response.data = {"detail": str(exc.detail), "errors": {}}
    return response
