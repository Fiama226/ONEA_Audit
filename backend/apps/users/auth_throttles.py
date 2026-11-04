"""Per-IP rate limit of the login endpoints (the per-account limit is the lockout).

The rate is ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["connexion"]`` (environment variable
``THROTTLE_RATE_CONNEXION``), read on each request so that tests can override it. The client
address is ``REMOTE_ADDR`` as fixed by ``AdresseClientMiddleware`` (never X-Forwarded-For).
If the cache is down the request goes through with a warning, like the other throttles: the
account lockout still applies.
"""

import logging
from typing import TYPE_CHECKING

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

    def get_cache_key(self, request: Request, view: "APIView") -> str:
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
