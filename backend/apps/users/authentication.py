from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


class SessionAuthentication401(SessionAuthentication):
    """Session auth that makes DRF answer 401 (not 403) to anonymous requests."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"
