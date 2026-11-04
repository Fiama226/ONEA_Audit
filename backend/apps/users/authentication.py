import base64
import binascii
import json
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db import DatabaseError
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied
from rest_framework.request import Request

from apps.core.middleware import session_ouverte_par_connexion

logger = logging.getLogger(__name__)

INVALID_TOKEN = "Session expirée ou jeton invalide."  # noqa: S105
ACCOUNT_DISABLED = "Compte désactivé."


class AuthServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service d'authentification indisponible. Réessayez plus tard."
    default_code = "auth_unavailable"


CSRF_REFUSE = "Jeton CSRF absent ou invalide : rechargez la page."


class SessionAuthentication401(SessionAuthentication):
    """Session auth (the API's own login) answering 401, not 403, to anonymous requests.

    DRF turns a 401 into a 403 when the first authentication class has no challenge, hence
    `authenticate_header`. CSRF is enforced on unsafe methods of session-authenticated
    requests (stock DRF behaviour), with a French message; Bearer requests never reach it.
    A disabled account is anonymous here: Django's ModelBackend.get_user drops inactive users.
    Only sessions opened by POST /api/v1/auth/login/ count: a session from the Django admin
    login (or ``force_login``) is anonymous for the API, so it cannot skip the login checks.
    """

    def authenticate(self, request: Request) -> tuple[Any, None] | None:
        session = getattr(request._request, "session", None)
        if session is None or not session_ouverte_par_connexion(session):
            return None
        return super().authenticate(request)

    def authenticate_header(self, request: Request) -> str:
        return "Session"

    def enforce_csrf(self, request: Request) -> None:
        try:
            super().enforce_csrf(request)
        except PermissionDenied:
            raise PermissionDenied(CSRF_REFUSE) from None


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
