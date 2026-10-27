import base64
import binascii
import json
import logging

import requests
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db import DatabaseError
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied
from rest_framework.request import Request

logger = logging.getLogger(__name__)

INVALID_TOKEN = "Session expirée ou jeton invalide."  # noqa: S105
ACCOUNT_DISABLED = "Compte désactivé."


class AuthServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service d'authentification indisponible. Réessayez plus tard."
    default_code = "auth_unavailable"


class SessionAuthentication401(SessionAuthentication):
    """Session auth that makes DRF answer 401 (not 403) to anonymous requests."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"


def _authorized_party(token: str) -> str | None:
    """`azp` of the access token payload. NO signature check here: Keycloak has
    validated the token through userinfo; this only reads which client it was issued to."""
    parts = token.split(".")
    if len(parts) != 3:  # noqa: PLR2004
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (binascii.Error, ValueError):
        return None
    azp = payload.get("azp") if isinstance(payload, dict) else None
    return azp if isinstance(azp, str) else None


class OIDCBearerAuthentication(OIDCAuthentication):  # type: ignore[misc]
    """Keycloak bearer-token authentication (token verified through userinfo).

    - Invalid/expired/foreign-realm token, bad payload: 401, never a 500.
    - Keycloak unreachable or answering 5xx: 503 (do not log everybody out).
    - Tokens issued to a client not in OIDC_ALLOWED_AZP are refused. Every client of
      the realm can emit tokens with the shared `roles` claim (e.g. admin-cli), so
      without this check a token from another client would reach the role mapping.
    - Only database errors propagate.
    """

    www_authenticate_realm = "onea"

    def _check_azp(self, request: Request) -> None:
        token = self.get_access_token(request)
        if token is None:
            return
        azp = _authorized_party(token)
        if azp is None or azp not in settings.OIDC_ALLOWED_AZP:
            logger.warning("Bearer token refused: client not allowed")
            raise AuthenticationFailed(INVALID_TOKEN)

    def authenticate(self, request: Request) -> tuple[object, str] | None:
        try:
            self._check_azp(request)
            result: tuple[object, str] | None = super().authenticate(request)
        except AuthenticationFailed:
            raise AuthenticationFailed(INVALID_TOKEN) from None
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else 0
            if code >= 500:  # noqa: PLR2004
                logger.error("Keycloak userinfo answered HTTP %s", code)
                raise AuthServiceUnavailable from None
            raise AuthenticationFailed(INVALID_TOKEN) from None
        except (requests.ConnectionError, requests.Timeout):
            logger.error("Keycloak userinfo unreachable")
            raise AuthServiceUnavailable from None
        except (requests.RequestException, SuspiciousOperation, ValueError) as exc:
            logger.warning("Bearer token refused: %s", type(exc).__name__)
            raise AuthenticationFailed(INVALID_TOKEN) from None
        except DatabaseError:
            raise
        except Exception:  # noqa: BLE001
            # Last resort so that a token failure is never a 500 (no token, no claims logged).
            logger.exception("Unexpected error while validating a bearer token")
            raise AuthenticationFailed(INVALID_TOKEN) from None
        if result is not None and not result[0].is_active:  # type: ignore[attr-defined]
            raise PermissionDenied(ACCOUNT_DISABLED)
        return result
