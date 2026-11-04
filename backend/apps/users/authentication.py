from typing import Any

from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from apps.core.middleware import session_ouverte_par_connexion

CSRF_REFUSE = "Jeton CSRF absent ou invalide : rechargez la page."


class SessionAuthentication401(SessionAuthentication):
    """Session auth (the API's own login) answering 401, not 403, to anonymous requests.

    DRF turns a 401 into a 403 when the first authentication class has no challenge, hence
    `authenticate_header`. CSRF is enforced on unsafe methods of session-authenticated
    requests (stock DRF behaviour), with a French message.
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
