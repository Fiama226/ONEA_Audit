from typing import Any

import factory

from apps.notifications.models import Notification, TypeNotification
from tests.factories import UserFactory


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    destinataire = factory.SubFactory(UserFactory)
    type = TypeNotification.SUIVI_OUVERT
    titre = "Suivi ouvert"
    message = "Une action de votre responsabilité est à suivre."
    lien = "/recommandations/actions/1"


def creer_notification(**kwargs: Any) -> Notification:
    n = NotificationFactory(**kwargs)
    assert isinstance(n, Notification)
    return n
