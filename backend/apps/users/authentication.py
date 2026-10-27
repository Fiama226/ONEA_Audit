import logging

from django.db import DatabaseError
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

logger = logging.getLogger(__name__)

INVALID_TOKEN = "Session expirée ou jeton invalide."  # noqa: S105


class SessionAuthentication401(SessionAuthentication):
    """Session auth that makes DRF answer 401 (not 403) to anonymous requests."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"


class OIDCBearerAuthentication(OIDCAuthentication):  # type: ignore[misc]
    """Keycloak bearer-token authentication (token verified through userinfo).

    Any failure while validating a presented token (invalid/expired/foreign-realm
    token, Keycloak unreachable, malformed header, bad payload...) is a 401 with
    the French message, never a 500. Only database errors propagate.
    """

    www_authenticate_realm = "onea"

    def authenticate(self, request: Request) -> tuple[object, str] | None:
        try:
            result: tuple[object, str] | None = super().authenticate(request)
        except AuthenticationFailed:
            raise AuthenticationFailed(INVALID_TOKEN) from None
        except DatabaseError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Bearer token validation failed: %s", type(exc).__name__)
            raise AuthenticationFailed(INVALID_TOKEN) from None
        return result
