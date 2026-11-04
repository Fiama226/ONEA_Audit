"""Rate limits of the anonymous auth endpoints (login, its code, forgotten password, reset).

Per IP: scope ``connexion`` (``THROTTLE_RATE_CONNEXION``), one bucket shared by these
endpoints; the per-account limit of the login is the lockout. Per typed identifier: scope
``mot_de_passe_oublie`` (``THROTTLE_RATE_MOT_DE_PASSE_OUBLIE``) on the code requests. Rates
are read on each request so that tests can override them. The client address is
``REMOTE_ADDR`` as fixed by ``AdresseClientMiddleware`` (never X-Forwarded-For). If the cache
is down the request goes through with a warning, like the other throttles: the account
lockout and the per-account code quota still apply.
"""

import logging
import unicodedata
from typing import TYPE_CHECKING

from django.utils.crypto import salted_hmac
from redis.exceptions import RedisError
from rest_framework.request import Request
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

from apps.core.reseau import adresse_client

if TYPE_CHECKING:
    from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class ConnexionParIpThrottle(SimpleRateThrottle):
    scope = "connexion"

    def get_rate(self) -> str | None:
        return str(api_settings.DEFAULT_THROTTLE_RATES[self.scope])

    def get_cache_key(self, request: Request, view: "APIView") -> str | None:
        return f"throttle_{self.scope}_ip{adresse_client(request) or 'inconnue'}"

    def allow_request(self, request: Request, view: "APIView") -> bool:
        try:
            return super().allow_request(request, view)
        except (RedisError, OSError) as exc:  # ConnectionError is an OSError
            logger.warning(
                "Limitation de débit de la connexion désactivée : cache indisponible (%s).",
                type(exc).__name__,
            )
            return True


class MotDePasseOublieParIdentifiantThrottle(ConnexionParIpThrottle):
    """Code requests per typed identifier, known account or not (a 429 reveals nothing).

    The key is a keyed hash (HMAC with SECRET_KEY) of the normalized identifier: the cache
    never holds an address or a username, nor a plain hash a dictionary would reverse.
    Letter case and surrounding spaces do not make a new identifier.
    """

    scope = "mot_de_passe_oublie"

    def get_cache_key(self, request: Request, view: "APIView") -> str | None:
        donnees = request.data
        identifiant = donnees.get("identifiant") if hasattr(donnees, "get") else None
        # Same inputs as the serializer's CharField: a JSON number is its text (123456 and
        # "123456" share one bucket); anything else is refused by the serializer anyway and
        # the per-IP limit still applies.
        if isinstance(identifiant, bool) or not isinstance(identifiant, str | int | float):
            return None
        texte = str(identifiant).strip()
        if not texte:
            return None
        normalise = unicodedata.normalize("NFKC", texte).casefold()
        empreinte = salted_hmac(
            "onea.throttle.identifiant", normalise, algorithm="sha256"
        ).hexdigest()
        return f"throttle_{self.scope}_{empreinte}"
