import pytest
from rest_framework.test import APIClient

from apps.users.models import Role, User

from .factories import make_user


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
