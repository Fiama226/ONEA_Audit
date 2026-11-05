from collections.abc import Iterator

import pytest
from rest_framework.test import APIClient

from apps.users.models import Role, User

from .connexion import connecter
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
    """API client holding a real API session of ``user`` (see ``tests.connexion``)."""
    return connecter(api_client, user)


@pytest.fixture(autouse=True)
def _reset_factory_sequences() -> None:
    """Keep sequence-based values (years, risk numbers) deterministic across tests."""
    reset_sequences()


@pytest.fixture(autouse=True)
def _cache_vide() -> Iterator[None]:
    """Le cache local sert aux compteurs de limitation de débit : aucune fuite entre tests."""
    from django.core.cache import cache

    cache.clear()
    yield
