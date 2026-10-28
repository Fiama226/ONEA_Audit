"""Least-privilege client of the Keycloak Admin REST API.

The platform authenticates as the realm's `onea-admin-sync` service account (client
credentials grant) which only holds `view-users` and `manage-users`. The access token is
cached per process behind a lock. Neither the client secret nor a token is ever put in an
exception message or a log record: error messages are fixed French strings that are safe
to show to a user.
"""

import threading
import time
from collections.abc import Iterator
from typing import Any, Protocol
from uuid import UUID

import requests
from django.conf import settings

_TOKEN_MARGIN = 30.0  # seconds: renew a token this long before it expires (a token living
# 30 s or less is therefore renewed on every call: harmless)
_MAX_PAGES = 1000  # hard bound on iter_users pagination (server ignoring `first`)


class KeycloakAdminError(Exception):
    """Failure of a Keycloak admin call. `message` is French and safe to display."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class KeycloakIndisponible(KeycloakAdminError):
    """Connection failure, timeout or 5xx."""


class KeycloakIntrouvable(KeycloakAdminError):
    """404: the account does not exist in Keycloak."""


class KeycloakRefus(KeycloakAdminError):
    """401/403 even after renewing the token: the service client lacks rights."""


class KeycloakNonConfigure(KeycloakAdminError):
    """No service-account secret configured."""


class KeycloakAdmin(Protocol):
    def set_enabled(self, user_id: UUID, enabled: bool) -> None: ...

    def logout(self, user_id: UUID) -> None: ...

    def search_users(self, q: str, *, max_results: int = 20) -> list[dict[str, Any]]: ...

    def iter_users(self, *, page_size: int = 100) -> Iterator[dict[str, Any]]: ...

    def get_user(self, user_id: UUID) -> dict[str, Any]: ...

    def effective_realm_roles(self, user_id: UUID) -> set[str]: ...


_lock = threading.Lock()
_token: str | None = None
_token_expires_at = 0.0
_token_key: tuple[str, str, str] | None = None  # (endpoint, client id, secret) of the cache
# One pooled session per process, reused by every client instance.
_SESSION = requests.Session()


def _reset_token_cache() -> None:
    global _token, _token_expires_at, _token_key
    with _lock:
        _token = None
        _token_expires_at = 0.0
        _token_key = None


def _indisponible() -> KeycloakIndisponible:
    return KeycloakIndisponible("Keycloak injoignable.")


def _http_indisponible(status: int) -> KeycloakIndisponible:
    return KeycloakIndisponible(f"Keycloak a répondu HTTP {status}.", status)


def _refus(status: int) -> KeycloakRefus:
    return KeycloakRefus(
        f"Keycloak a refusé l'opération (HTTP {status}) : "
        "vérifiez les droits du client de service.",
        status,
    )


def _admin_base() -> str:
    return str(settings.OIDC_OP_BASE_URL).replace("/realms/", "/admin/realms/", 1)


def _uid(user_id: UUID) -> UUID:
    """Runtime guard: the id goes into a URL path, it must be a real UUID."""
    return UUID(str(user_id))


class HttpKeycloakAdmin:
    """`requests` implementation of `KeycloakAdmin`."""

    def __init__(self) -> None:
        self._session = _SESSION

    # --- token ---------------------------------------------------------------

    def _cache_key(self) -> tuple[str, str, str]:
        return (
            str(settings.OIDC_OP_TOKEN_ENDPOINT),
            str(settings.KEYCLOAK_ADMIN_API_CLIENT_ID),
            str(settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET),
        )

    def _fetch_token(self, key: tuple[str, str, str]) -> str:
        global _token, _token_expires_at, _token_key
        try:
            resp = self._session.request(
                "POST",
                settings.OIDC_OP_TOKEN_ENDPOINT,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.KEYCLOAK_ADMIN_API_CLIENT_ID,
                    "client_secret": settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET,
                },
                timeout=settings.OIDC_TIMEOUT,
                verify=settings.OIDC_VERIFY_SSL,
                allow_redirects=False,  # the form body carries the client secret
            )
        except requests.RequestException:
            raise _indisponible() from None
        status = resp.status_code
        if status in (400, 401, 403):
            raise _refus(status)
        if status >= 500 or 300 <= status < 400:
            raise _http_indisponible(status)
        if status >= 400:
            raise KeycloakAdminError(
                f"Keycloak a refusé la demande de jeton (HTTP {status}) : "
                "vérifiez l'adresse du realm.",
                status,
            )
        try:
            body = resp.json()
            token = str(body["access_token"])
            lifetime = float(body.get("expires_in", 60))
        except (ValueError, KeyError, TypeError, AttributeError):
            raise _indisponible() from None
        _token = token
        _token_expires_at = time.monotonic() + lifetime - _TOKEN_MARGIN
        _token_key = key
        return token

    def _get_token(self, *, renew: bool = False) -> str:
        key = self._cache_key()
        with _lock:
            if (
                not renew
                and _token is not None
                and _token_key == key
                and time.monotonic() < _token_expires_at
            ):
                return _token
            return self._fetch_token(key)

    # --- transport -----------------------------------------------------------

    def _send(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        renewed = False
        while True:
            token = self._get_token(renew=renewed)
            try:
                resp = self._session.request(
                    method,
                    f"{_admin_base()}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=settings.OIDC_TIMEOUT,
                    verify=settings.OIDC_VERIFY_SSL,
                    allow_redirects=False,
                    **kwargs,
                )
            except requests.RequestException:
                raise _indisponible() from None
            status = resp.status_code
            if status in (401, 403):
                if not renewed:
                    renewed = True
                    continue
                raise _refus(status)
            if status == 404:
                raise KeycloakIntrouvable("Compte introuvable dans Keycloak.", 404)
            if status >= 500 or 300 <= status < 400:
                raise _http_indisponible(status)
            if status >= 400:
                raise KeycloakAdminError(f"Keycloak a refusé la requête (HTTP {status}).", status)
            return resp

    def _json(self, resp: requests.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            raise _indisponible() from None

    # --- operations ----------------------------------------------------------

    def get_user(self, user_id: UUID) -> dict[str, Any]:
        rep: dict[str, Any] = self._json(self._send("GET", f"/users/{_uid(user_id)}"))
        return rep

    def set_enabled(self, user_id: UUID, enabled: bool) -> None:
        uid = _uid(user_id)
        # Keycloak's PUT replaces the representation (unmanaged attributes would be lost
        # if a partial body were sent): read the full one, flip the flag, write it back.
        rep = self.get_user(uid)
        self._send("PUT", f"/users/{uid}", json={**rep, "enabled": enabled})

    def logout(self, user_id: UUID) -> None:
        self._send("POST", f"/users/{_uid(user_id)}/logout")

    def search_users(self, q: str, *, max_results: int = 20) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = self._json(
            self._send("GET", "/users", params={"search": q, "max": max_results})
        )
        return users

    def iter_users(self, *, page_size: int = 100) -> Iterator[dict[str, Any]]:
        first = 0
        for _ in range(_MAX_PAGES):
            page: list[dict[str, Any]] = self._json(
                self._send("GET", "/users", params={"first": first, "max": page_size})
            )
            yield from page
            if len(page) < page_size:
                return
            first += page_size
        raise KeycloakAdminError("Pagination Keycloak anormale : liste interrompue.")

    def effective_realm_roles(self, user_id: UUID) -> set[str]:
        roles: list[dict[str, Any]] = self._json(
            self._send("GET", f"/users/{_uid(user_id)}/role-mappings/realm/composite")
        )
        return {str(r["name"]) for r in roles}


def get_keycloak_admin() -> KeycloakAdmin:
    """Single entry point; raises `KeycloakNonConfigure` when no secret is configured."""
    if not settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET:
        raise KeycloakNonConfigure("Synchronisation Keycloak non configurée.")
    return HttpKeycloakAdmin()
