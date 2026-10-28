import copy
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from rest_framework.test import APIClient

from apps.users.keycloak_admin import KeycloakAdminError, KeycloakIntrouvable
from apps.users.models import Role, User

from .factories import make_user, reset_sequences


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db: None) -> User:
    return make_user(Role.AUDITEUR)


@pytest.fixture
def rai(db: None) -> User:
    return make_user(Role.RAI)


@pytest.fixture
def admin(db: None) -> User:
    return make_user(Role.ADMIN)


@pytest.fixture
def audite(db: None) -> User:
    return make_user(Role.AUDITE)


@pytest.fixture
def dg(db: None) -> User:
    return make_user(Role.DG)


@pytest.fixture
def auth_client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture(autouse=True)
def _reset_factory_sequences() -> None:
    """Keep sequence-based values (years, risk numbers) deterministic across tests."""
    reset_sequences()


class FakeKeycloakAdmin:
    """In-memory `KeycloakAdmin` for tests of the user-management features."""

    def __init__(self) -> None:
        self.users: dict[UUID, dict[str, Any]] = {}
        self.roles: dict[UUID, set[str]] = {}
        self.calls: list[tuple[Any, ...]] = []
        self._failures: list[Exception] = []
        self._on_set_enabled: Callable[[UUID, bool], None] | None = None

    # --- test helpers ---
    def add_user(self, username: str, **attrs: Any) -> UUID:
        user_id = uuid4()
        roles = attrs.pop("roles", set())
        self.users[user_id] = {"id": str(user_id), "username": username, "enabled": True, **attrs}
        self.roles[user_id] = set(roles)
        return user_id

    def enabled(self, user_id: UUID) -> bool:
        return bool(self.users[user_id]["enabled"])

    def fail_with(self, exc: Exception, times: int = 1) -> None:
        """Make the next `times` calls raise (a fresh copy of `exc` each time)."""
        self._failures.extend([exc] * times)

    def on_set_enabled(self, callback: Callable[[UUID, bool], None]) -> None:
        self._on_set_enabled = callback

    # --- KeycloakAdmin protocol ---
    def _enter(self, *call: Any) -> None:
        self.calls.append(call)
        if self._failures:
            template = self._failures.pop(0)
            if isinstance(template, KeycloakAdminError):
                raise type(template)(template.message, template.status)
            raise copy.copy(template)

    def _user(self, user_id: UUID) -> dict[str, Any]:
        if user_id not in self.users:
            raise KeycloakIntrouvable("Compte introuvable dans Keycloak.", 404)
        return self.users[user_id]

    def set_enabled(self, user_id: UUID, enabled: bool) -> None:
        self._enter("set_enabled", user_id, enabled)
        user = self._user(user_id)
        if self._on_set_enabled is not None:
            self._on_set_enabled(user_id, enabled)
        user["enabled"] = enabled

    def logout(self, user_id: UUID) -> None:
        self._enter("logout", user_id)
        self._user(user_id)

    def search_users(self, q: str, *, max_results: int = 20) -> list[dict[str, Any]]:
        self._enter("search_users", q, max_results)
        needle = q.lower()
        fields = ("username", "email", "firstName", "lastName")
        found = [
            copy.deepcopy(u)
            for u in self.users.values()
            if any(needle in str(u.get(f, "")).lower() for f in fields)
        ]
        return found[:max_results]

    def iter_users(self, *, page_size: int = 100) -> Iterator[dict[str, Any]]:
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        self._enter("iter_users", page_size)
        snapshot = [copy.deepcopy(u) for u in self.users.values()]
        for first in range(0, len(snapshot), page_size):
            yield from snapshot[first : first + page_size]

    def get_user(self, user_id: UUID) -> dict[str, Any]:
        self._enter("get_user", user_id)
        return dict(self._user(user_id))

    def effective_realm_roles(self, user_id: UUID) -> set[str]:
        self._enter("effective_realm_roles", user_id)
        self._user(user_id)
        return set(self.roles[user_id])


@pytest.fixture
def fake_keycloak(monkeypatch: pytest.MonkeyPatch) -> FakeKeycloakAdmin:
    fake = FakeKeycloakAdmin()
    monkeypatch.setattr("apps.users.keycloak_admin.get_keycloak_admin", lambda: fake)
    return fake
