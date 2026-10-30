"""Contrat JSON d'une page de notifications et du compteur (fixtures MSW, lot 8 T14)."""

from pathlib import Path

import pytest

from apps.users.models import User
from tests.accomplissement.fixtures_api import client_de
from tests.contrat_forme import comparer

from .factories import creer_notification

pytestmark = pytest.mark.django_db
GOLDEN = Path(__file__).with_name("contrat_lot8.json")


def test_api_contrat_page_de_notifications(user: User) -> None:
    creer_notification(destinataire=user)
    comparer(GOLDEN, "page", client_de(user).get("/api/v1/notifications/").json())


def test_api_contrat_compteur(user: User) -> None:
    creer_notification(destinataire=user)
    comparer(GOLDEN, "compteur", client_de(user).get("/api/v1/notifications/unread-count/").json())
