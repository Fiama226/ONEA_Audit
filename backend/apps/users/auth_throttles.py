"""Rate limits of the authentication endpoints.

One bucket per endpoint (AUTH-05), so that the login of a head office behind one NAT address
is not spent by its forgotten-password or code requests. Per client address (an IPv6
address counts by its /64, AUTH-12):

==========================  =======================================  ===============
scope                       endpoint                                 default
==========================  =======================================  ===============
``connexion``               POST /auth/login/ (+ Django admin login)  60/min
``connexion_code``          POST /auth/login/otp/                    30/min
``mot_de_passe_oublie_ip``  POST /auth/password/forgot/              20/min
``reinitialisation``        POST /auth/password/reset/               20/min
``echecs_connexion``        wrong passwords and login codes          30/15min
``echecs_reinitialisation`` refused password resets                  30/hour
==========================  =======================================  ===============

Per typed identifier: ``mot_de_passe_oublie`` (5/hour) on the code requests. Per user, on the
authenticated password checks (change of password, removal of the login code):
``changement_mot_de_passe`` (10/min).

The two ``echecs_*`` scopes count failures only (AUTH-04): once an address reached the cap,
the endpoint answers 429 before any password or code is checked, so one address cannot keep
many accounts locked. Behind a NAT every agent shares these budgets: 30 failures in 15
minutes from the whole site then block the logins of that address for at most 15 minutes
(the per-account lockout is unchanged).

Every rate is read on each request (tests override it) and can be set by the environment,
``THROTTLE_RATE_<SCOPE>`` (e.g. ``THROTTLE_RATE_CONNEXION=120/min``,
``THROTTLE_RATE_ECHECS_CONNEXION=60/15min``): ``N/<k><sec|min|hour|day>``, ``k`` optional.
The client address is ``REMOTE_ADDR`` as fixed by ``AdresseClientMiddleware`` (never
X-Forwarded-For). If the cache is down the request goes through with a warning, like the
other throttles: the account lockout and the per-account code limits (database) still apply.
CSRF is checked before these limits count anything (``auth_views._CsrfObligatoireMixin``).
"""

import ipaddress
import logging
import re
import unicodedata
from typing import Any

from django.http import HttpRequest
from django.utils.crypto import salted_hmac
from redis.exceptions import RedisError
from rest_framework.request import Request
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

from apps.core.reseau import adresse_client

logger = logging.getLogger(__name__)
logger_securite = logging.getLogger("onea.securite")

_TAUX = re.compile(r"([1-9]\d*)/([1-9]\d*)?(sec|min|hour|day)")
_SECONDES = {"sec": 1, "min": 60, "hour": 3600, "day": 86400}


def analyser_taux(taux: str) -> tuple[int, int]:
    """``"30/15min"`` -> ``(30, 900)``: requests and window in seconds."""
    trouve = _TAUX.fullmatch(taux.strip())
    if trouve is None:
        raise ValueError(f"Invalid rate {taux!r}: expected N/<k><sec|min|hour|day>")
    nombre, multiple, unite = trouve.groups()
    return int(nombre), int(multiple or 1) * _SECONDES[unite]


def cle_adresse(request: HttpRequest | Request) -> str:
    """The client address as a throttle key; an IPv6 address by its /64 (AUTH-12)."""
    adresse = adresse_client(request)
    if not adresse:
        return "inconnue"
    try:
        ip = ipaddress.ip_address(adresse)
    except ValueError:
        return adresse
    if ip.version == 6:
        return f"{ipaddress.ip_network(f'{ip}/64', strict=False).network_address}/64"
    return adresse


class _LimiteAuth(SimpleRateThrottle):
    """Rate read from the settings on each request; fails open when the cache is down."""

    def get_rate(self) -> str | None:
        return str(api_settings.DEFAULT_THROTTLE_RATES[str(self.scope)])

    def parse_rate(self, rate: str | None) -> tuple[int | None, int | None]:
        if rate is None:
            return None, None
        return analyser_taux(rate)

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        return f"throttle_{self.scope}_ip{cle_adresse(request)}"

    def allow_request(self, request: Any, view: Any) -> bool:
        try:
            return super().allow_request(request, view)
        except (RedisError, OSError) as exc:  # ConnectionError is an OSError
            logger.warning(
                "Limitation de débit de l'authentification désactivée : cache indisponible (%s).",
                type(exc).__name__,
            )
            return True


class ConnexionParIpThrottle(_LimiteAuth):
    scope = "connexion"


class CodeConnexionParIpThrottle(_LimiteAuth):
    scope = "connexion_code"


class MotDePasseOublieParIpThrottle(_LimiteAuth):
    scope = "mot_de_passe_oublie_ip"


class ReinitialisationParIpThrottle(_LimiteAuth):
    scope = "reinitialisation"


class ChangementMotDePasseParUtilisateurThrottle(_LimiteAuth):
    """Authenticated password checks: per user, so that colleagues behind one NAT address
    never share it (the wrong passwords also count in the account lockout)."""

    scope = "changement_mot_de_passe"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return f"throttle_{self.scope}_{user.pk}"


class MotDePasseOublieParIdentifiantThrottle(_LimiteAuth):
    """Code requests per typed identifier, known account or not (a 429 reveals nothing).

    The key is a keyed hash (HMAC with SECRET_KEY) of the normalized identifier: the cache
    never holds an address or a username, nor a plain hash a dictionary would reverse.
    Letter case and surrounding spaces do not make a new identifier.
    """

    scope = "mot_de_passe_oublie"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
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


class _EchecsParIp(_LimiteAuth):
    """Counts failures only (``enregistrer_echec``). ``allow_request`` adds nothing: it
    refuses once the address reached the cap, before any work is done."""

    def allow_request(self, request: Any, view: Any) -> bool:
        if self.rate is None:
            return True
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        try:
            self.history = self.cache.get(self.key, [])
        except (RedisError, OSError) as exc:
            logger.warning(
                "Plafond d'échecs par adresse désactivé : cache indisponible (%s).",
                type(exc).__name__,
            )
            return True
        self.now = self.timer()
        nombre, duree = analyser_taux(self.rate)
        while self.history and self.history[-1] <= self.now - duree:
            self.history.pop()
        if len(self.history) >= nombre:
            logger_securite.warning(
                "Plafond d'échecs atteint pour une adresse : portee=%s adresse=%s",
                self.scope,
                cle_adresse(request),
            )
            return self.throttle_failure()
        return True

    def enregistrer_echec(self, request: Any) -> None:
        cle = self.get_cache_key(request, None)
        if self.rate is None or cle is None:
            return
        _, duree = analyser_taux(self.rate)
        try:
            maintenant = self.timer()
            historique = [h for h in self.cache.get(cle, []) if h > maintenant - duree]
            historique.insert(0, maintenant)
            self.cache.set(cle, historique, duree)
        except (RedisError, OSError) as exc:
            logger.warning(
                "Échec non compté par adresse : cache indisponible (%s).", type(exc).__name__
            )


class EchecsConnexionParIpThrottle(_EchecsParIp):
    """Wrong passwords and login codes per address, across accounts (AUTH-04)."""

    scope = "echecs_connexion"


class EchecsReinitialisationParIpThrottle(_EchecsParIp):
    """Refused password resets per address, across accounts (AUTH-02, AUTH-04)."""

    scope = "echecs_reinitialisation"


def autoriser_connexion_hors_api(request: HttpRequest) -> bool:
    """The login limits of the API, for a login outside DRF (Django admin form, AUTH-06)."""
    return ConnexionParIpThrottle().allow_request(
        request, None
    ) and EchecsConnexionParIpThrottle().allow_request(request, None)
