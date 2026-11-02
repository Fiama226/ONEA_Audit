import math
import re
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework.exceptions import NotFound, ParseError, Throttled, ValidationError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .exceptions import RegleMetierError

INVALID_DATA = "Données invalides."
NOT_FOUND = "Non trouvé."
FORBIDDEN = "Accès refusé."
UNREADABLE_BODY = "La requête est mal formée : son contenu est illisible."


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


_DJANGO_404 = re.compile(r"^No .+ matches the given query\.$")


def _localized(exc: Exception, detail: str) -> str:
    """Use the French default only when the message is a framework default."""
    if isinstance(exc, NotFound | Http404):
        if detail == str(NotFound.default_detail) or _DJANGO_404.match(detail):
            return NOT_FOUND
    elif isinstance(exc, DRFPermissionDenied | PermissionDenied):
        if detail == str(DRFPermissionDenied.default_detail):
            return FORBIDDEN
    return detail


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, RegleMetierError):
        set_rollback()
        return Response(
            {"detail": exc.message, "errors": exc.errors},
            status=exc.status_http,
        )
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, Throttled):
        secondes = max(1, math.ceil(getattr(exc, "wait", None) or 1))
        response["Retry-After"] = str(secondes)
        response.data = {
            "detail": f"Trop de requêtes : réessayez dans {secondes} secondes.",
            "errors": {},
        }
        return response
    if isinstance(exc, ParseError):
        # le message du décodeur (anglais, technique) ne doit pas atteindre l'utilisateur
        response.data = {"detail": UNREADABLE_BODY, "errors": {}}
    elif isinstance(exc, ValidationError):
        response.data = {"detail": INVALID_DATA, "errors": _flatten(exc.detail)}
    else:
        response.data = {"detail": _localized(exc, _detail_message(response.data)), "errors": {}}
    return response
