from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .exceptions import RegleMetierError

INVALID_DATA = "Données invalides."
NOT_FOUND = "Non trouvé."
FORBIDDEN = "Accès refusé."


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


def _detail_message(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("detail"), str):
        return str(data["detail"])
    messages = [m for msgs in _flatten(data).values() for m in msgs]
    return " ".join(messages) or INVALID_DATA


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, RegleMetierError):
        set_rollback()
        return Response(
            {"detail": exc.message, "errors": exc.errors},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        response.data = {"detail": INVALID_DATA, "errors": _flatten(exc.detail)}
    elif isinstance(exc, Http404):
        response.data = {"detail": NOT_FOUND, "errors": {}}
    elif isinstance(exc, PermissionDenied):
        response.data = {"detail": FORBIDDEN, "errors": {}}
    elif isinstance(exc, APIException):
        detail = _detail_message(response.data)
        if response.status_code == status.HTTP_403_FORBIDDEN and exc.get_codes() == (
            "permission_denied"
        ):
            detail = FORBIDDEN
        response.data = {"detail": detail, "errors": {}}
    else:
        response.data = {"detail": _detail_message(response.data), "errors": {}}
    return response
