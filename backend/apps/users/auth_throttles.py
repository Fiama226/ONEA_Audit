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


def _normaliser(identifiant: object) -> str:
    """Letter case, width and surrounding spaces do not make a new identifier."""
    return unicodedata.normalize("NFKC", str(identifiant or "").strip()).casefold()


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
        normalise = _normaliser(texte)
        empreinte = salted_hmac(
            "onea.throttle.identifiant", normalise, algorithm="sha256"
        ).hexdigest()
        return f"throttle_{self.scope}_{empreinte}"


class _EchecsParIp(_LimiteAuth):
    """Counts failures only (``enregistrer_echec``). ``allow_request`` adds nothing: it
    refuses once the address reached the cap, before any work is done.

    The window is cut into ``TRANCHES`` slices, one cache counter each, increased with an
    atomic ``incr`` (N4: no read-modify-write of a list, so concurrent failures are never
    lost); the count is the sum of the slices of the window. Reaching the cap logs one
    warning per address and window (N8).
    """

    TRANCHES = 10

    def _cles(self, request: Any, maintenant: float) -> tuple[list[str], float, float]:
        """Keys of the window's slices (oldest first), the slice length and the window."""
        assert self.rate is not None  # noqa: S101
        _, duree = analyser_taux(self.rate)
        tranche = duree / self.TRANCHES
        courante = int(maintenant // tranche)
        base = self.get_cache_key(request, None)
        cles = [f"{base}_{n}" for n in range(courante - self.TRANCHES + 1, courante + 1)]
        return cles, tranche, float(duree)

    def nombre_echecs(self, request: Any) -> int:
        """Failures of the address in the current window."""
        if self.rate is None:
            return 0
        cles, _, _ = self._cles(request, self.timer())
        return sum(int(v) for v in self.cache.get_many(cles).values())

    def allow_request(self, request: Any, view: Any) -> bool:
        if self.rate is None:
            return True
        nombre, _ = analyser_taux(self.rate)
        maintenant = self.timer()
        cles, tranche, duree = self._cles(request, maintenant)
        try:
            valeurs = self.cache.get_many(cles)
        except (RedisError, OSError) as exc:
            logger.warning(
                "Plafond d'échecs par adresse désactivé : cache indisponible (%s).",
                type(exc).__name__,
            )
            return True
        if sum(int(v) for v in valeurs.values()) < nombre:
            return True
        # Retry-After: until the oldest slice that holds failures leaves the window.
        premiere = next(i for i, cle in enumerate(cles) if valeurs.get(cle))
        indice = int(maintenant // tranche) - self.TRANCHES + 1 + premiere
        self._attente = max(1.0, (indice + self.TRANCHES) * tranche - maintenant)
        try:
            cle_avis = f"{self.get_cache_key(request, None)}_journalise"
            premier_avis = self.cache.add(cle_avis, 1, int(duree))
        except (RedisError, OSError):
            premier_avis = True
        if premier_avis:
            logger_securite.warning(
                "Plafond d'échecs atteint pour une adresse : portee=%s adresse=%s",
                self.scope,
                cle_adresse(request),
            )
        return False

    def wait(self) -> float | None:
        return getattr(self, "_attente", None)

    # At most this many refusals counted per (address, unknown identifier, window).
    INCONNUS_PAR_IDENTIFIANT = 5

    def compter_refus(
        self,
        request: Any,
        comptage: Any,
        *,
        compte_id: int | None = None,
        identifiant: object = None,
    ) -> None:
        """Count a refusal by its kind (`auth_services.Comptage`), never by whether the
        secret typed was right (D1):

        - wrong secret on a usable account: every refusal;
        - unusable account (locked, disabled, expired, blocked): once per (address, account,
          window), right or wrong secret alike; a site behind one NAT address retrying a
          locked account costs one unit;
        - unknown identifier: every refusal, at most 5 per (address, identifier, window);
        - a replaced code (``AUCUN``): nothing.
        """
        from .auth_services import Comptage

        if comptage is Comptage.SECRET_FAUX:
            self.enregistrer_echec(request)
        elif comptage is Comptage.COMPTE_INUTILISABLE:
            if self._dans_la_limite(request, f"compte:{compte_id}", 1):
                self.enregistrer_echec(request)
        elif comptage is Comptage.INCONNU:
            sujet = f"identifiant:{_normaliser(identifiant)}"
            if self._dans_la_limite(request, sujet, self.INCONNUS_PAR_IDENTIFIANT):
                self.enregistrer_echec(request)

    def compter_refus_reinitialisation(
        self, request: Any, comptage: Any, *, identifiant: object
    ) -> None:
        """Reset: every refusal (unknown, wrong code, disabled, blocked account) counts the
        same way, at most 5 per (address, typed identifier, window): the per-address counter
        tells nothing about whether the identifier exists or what state it is in (round 4).
        A replaced code counts nothing."""
        from .auth_services import Comptage

        if comptage is None or comptage is Comptage.AUCUN:
            return
        sujet = f"identifiant:{_normaliser(identifiant)}"
        if self._dans_la_limite(request, sujet, self.INCONNUS_PAR_IDENTIFIANT):
            self.enregistrer_echec(request)

    def _dans_la_limite(self, request: Any, sujet: str, maximum: int) -> bool:
        """Count one refusal for (address, subject) in the window; True while <= maximum.

        The key is a keyed hash (HMAC with SECRET_KEY): the cache never holds an account id
        next to an address, nor a typed identifier.
        """
        if self.rate is None:
            return False
        _, duree = analyser_taux(self.rate)
        empreinte = salted_hmac(
            "onea.throttle.refus",
            f"{self.scope}|{cle_adresse(request)}|{sujet}",
            algorithm="sha256",
        ).hexdigest()
        cle = f"throttle_{self.scope}_refus_{empreinte}"
        try:
            self.cache.add(cle, 0, duree)
            try:
                nombre = int(self.cache.incr(cle))
            except ValueError:  # expired between add and incr
                self.cache.set(cle, 1, duree)
                nombre = 1
        except (RedisError, OSError):
            return True  # the counter itself will fail open with a warning
        return nombre <= maximum

    def enregistrer_echec(self, request: Any) -> None:
        if self.rate is None or self.get_cache_key(request, None) is None:
            return
        cles, tranche, duree = self._cles(request, self.timer())
        cle = cles[-1]
        try:
            self.cache.add(cle, 0, int(duree + tranche) + 1)
            try:
                self.cache.incr(cle)
            except ValueError:  # expired between add and incr: a fresh slice
                self.cache.set(cle, 1, int(duree + tranche) + 1)
        except (RedisError, OSError) as exc:
            logger.warning(
                "Échec non compté par adresse : cache indisponible (%s).", type(exc).__name__
            )


class EchecsConnexionParIpThrottle(_EchecsParIp):
    """Wrong passwords and login codes per address, across accounts (AUTH-04)."""

    scope = "echecs_connexion"


class RefusParIpThrottle(_EchecsParIp):
    """Every refusal of a login, login code, reset or admin login, of any kind, per address
    (round 4). Looser than the caps above and independent of the secret (no oracle): it
    bounds the unauthenticated hashing work one address can cause (each refusal costs one
    to four Argon2 hashes) while leaving room for a head office behind one NAT address."""

    scope = "echecs_tous"


class EchecsReinitialisationParIpThrottle(_EchecsParIp):
    """Refused password resets per address, across accounts (AUTH-02, AUTH-04)."""

    scope = "echecs_reinitialisation"


def autoriser_connexion_hors_api(request: HttpRequest) -> bool:
    """The login limits of the API, for a login outside DRF (Django admin form, AUTH-06)."""
    return (
        ConnexionParIpThrottle().allow_request(request, None)
        and EchecsConnexionParIpThrottle().allow_request(request, None)
        and RefusParIpThrottle().allow_request(request, None)
    )
