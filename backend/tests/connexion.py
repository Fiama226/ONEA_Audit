"""Open an API session in tests, as POST /api/v1/auth/login/ does, without the password.

``force_login`` alone is not enough: the API only accepts the sessions that the login
endpoint marked (``CLE_CONNEXION``, see ``SessionAuthentication401``); a bare
``force_login`` session stays anonymous for the API, like a Django admin session.
"""

import time

from django.test import Client

from apps.core.middleware import CLE_ACTIVITE, CLE_CONNEXION
from apps.users.models import User

BACKEND = "django.contrib.auth.backends.ModelBackend"


def connecter[C: Client](client: C, user: User) -> C:
    """Log ``user`` in on ``client`` with a session the API accepts; returns the client."""
    client.force_login(user, backend=BACKEND)
    session = client.session
    maintenant = time.time()
    session[CLE_CONNEXION] = maintenant
    session[CLE_ACTIVITE] = maintenant
    session.save()
    return client
