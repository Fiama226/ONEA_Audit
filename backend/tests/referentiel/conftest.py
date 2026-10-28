import pytest
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def auth_rai(api_client: APIClient, rai: User) -> APIClient:
    """Client authentifié en tant que RAI (réutilisé par les tests d'export/import)."""
    api_client.force_authenticate(user=rai)
    return api_client
