"""API des notifications : isolement par destinataire, lecture, compteur, pagination."""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.users.models import Role, User
from tests.accomplissement.fixtures_api import client_de
from tests.factories import make_user

from .factories import creer_notification

pytestmark = pytest.mark.django_db

URL = "/api/v1/notifications/"


def test_liste_limitee_aux_siennes_du_plus_recent_au_plus_ancien(user: User, rai: User) -> None:
    # created_at fixé : deux créations dans la même milliseconde ne départagent pas le tri
    maintenant = timezone.now()
    with mock.patch("django.utils.timezone.now", return_value=maintenant - timedelta(hours=1)):
        ancienne = creer_notification(destinataire=user, titre="Ancienne")
    with mock.patch("django.utils.timezone.now", return_value=maintenant):
        recente = creer_notification(destinataire=user, titre="Recente")
    creer_notification(destinataire=rai, titre="Autrui")
    corps = client_de(user).get(URL).json()
    assert [n["titre"] for n in corps["results"]] == ["Recente", "Ancienne"]
    assert corps["count"] == 2
    assert {str(ancienne.pk), str(recente.pk)} == {n["id"] for n in corps["results"]}


def test_filtre_non_lues(user: User) -> None:
    creer_notification(destinataire=user, titre="Lue")
    non_lue = creer_notification(destinataire=user, titre="Non lue")
    client = client_de(user)
    client.post(f"{URL}{Notification.objects.get(titre='Lue').pk}/read/")
    corps = client.get(URL, {"non_lues": "true"}).json()
    assert [n["id"] for n in corps["results"]] == [str(non_lue.pk)]
    assert client.get(URL, {"non_lues": "false"}).json()["count"] == 2


def test_notifications_d_autrui_404(user: User, rai: User) -> None:
    autrui = creer_notification(destinataire=rai)
    reponse = client_de(user).post(f"{URL}{autrui.pk}/read/")
    assert reponse.status_code == 404
    assert set(reponse.json()) == {"detail", "errors"}
    autrui.refresh_from_db()
    assert autrui.lue_le is None
    assert client_de(user).post(f"{URL}pas-un-uuid/read/").status_code == 404


def test_read_marque_lue_et_est_idempotent(user: User) -> None:
    n = creer_notification(destinataire=user)
    client = client_de(user)
    premiere = client.post(f"{URL}{n.pk}/read/")
    assert premiere.status_code == 200
    assert premiere.json()["lue"] is True
    lue_le = premiere.json()["lue_le"]
    assert client.post(f"{URL}{n.pk}/read/").json()["lue_le"] == lue_le


def test_read_all_et_compteur(user: User, rai: User) -> None:
    for _ in range(3):
        creer_notification(destinataire=user)
    creer_notification(destinataire=rai)
    client = client_de(user)
    assert client.get(f"{URL}unread-count/").json() == {"count": 3}
    assert client.post(f"{URL}read-all/").json() == {"count": 3}
    assert client.get(f"{URL}unread-count/").json() == {"count": 0}
    assert client.post(f"{URL}read-all/").json() == {"count": 0}
    # les notifications d'autrui ne sont pas touchées
    assert client_de(rai).get(f"{URL}unread-count/").json() == {"count": 1}


def test_methodes_interdites_et_anonyme(user: User, api_client: APIClient) -> None:
    n = creer_notification(destinataire=user)
    client = client_de(user)
    assert client.post(URL, {}).status_code == 405
    assert client.delete(f"{URL}{n.pk}/").status_code in (404, 405)
    assert client.patch(f"{URL}{n.pk}/", {"titre": "x"}).status_code in (404, 405)
    assert api_client.get(URL).status_code == 401
    assert api_client.get(f"{URL}unread-count/").status_code == 401


def test_tous_les_roles_ont_leur_boite() -> None:
    for role in Role.values:
        utilisateur = make_user(role)
        creer_notification(destinataire=utilisateur)
        assert client_de(utilisateur).get(URL).json()["count"] == 1
