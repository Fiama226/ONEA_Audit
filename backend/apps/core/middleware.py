import time
from collections.abc import Callable
from typing import Any, cast

from auditlog.middleware import AuditlogMiddleware
from django.conf import settings
from django.contrib.auth import SESSION_KEY, logout
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.http.response import HttpResponseBase
from django.utils.functional import SimpleLazyObject, empty

from apps.core.reseau import PROXY_META, adresse_reelle

# Session keys (epoch seconds) written ONLY by the login endpoint (auth_views._ouvrir_session)
# after a full login. CLE_CONNEXION is also the marker of an API session: a session opened
# any other way (Django admin login, test client force_login) does not authenticate the API.
CLE_CONNEXION = "onea_connexion_le"
CLE_ACTIVITE = "onea_activite_le"
# The last-activity stamp is rewritten at most once a minute (one session write per minute).
ACTIVITE_PRECISION_SECONDES = 60

CHANGEMENT_OBLIGATOIRE = "Vous devez changer votre mot de passe avant de continuer."
# Paths a session flagged `doit_changer_mot_de_passe` may still call.
CHEMINS_AUTORISES_AVANT_CHANGEMENT = frozenset(
    f"/api/v1/auth/{suffixe}"
    for suffixe in (
        "login/",
        "login/otp/",
        "logout/",
        "session/",
        "csrf/",
        "password/change/",
    )
)


def _horodatage(valeur: object) -> float | None:
    return float(valeur) if isinstance(valeur, int | float) else None


def session_ouverte_par_connexion(session: Any) -> bool:
    """True when this authenticated session was opened by the API login endpoint."""
    return SESSION_KEY in session and _horodatage(session.get(CLE_CONNEXION)) is not None


class SessionLimiteeMiddleware:
    """Ends an API session after 8 h (absolute) or 30 min without a request.

    The absolute limit does not slide: it counts from the login stamp kept in the session
    (the session expiry itself is also set to a fixed date at login). Sessions not opened
    by the login endpoint carry no stamp and are never given one here: the API refuses them
    (``SessionAuthentication401``); only the Django admin pages accept them.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        session = getattr(request, "session", None)
        if session is not None and session_ouverte_par_connexion(session):
            self._controler(request)
        return self.get_response(request)

    @staticmethod
    def _controler(request: HttpRequest) -> None:
        session = request.session
        maintenant = time.time()
        debut = cast(float, _horodatage(session.get(CLE_CONNEXION)))
        activite = _horodatage(session.get(CLE_ACTIVITE))
        if activite is None:
            activite = maintenant
        if (
            maintenant - debut > settings.SESSION_COOKIE_AGE
            or maintenant - activite > settings.SESSION_INACTIVITE_SECONDES
        ):
            logout(request)  # flushes the session row and makes request.user anonymous
            return
        if maintenant - activite >= ACTIVITE_PRECISION_SECONDES or CLE_ACTIVITE not in session:
            session[CLE_ACTIVITE] = maintenant


class MotDePasseAChangerMiddleware:
    """While the session user must change their password, only the auth endpoints answer.

    A middleware rather than a DRF permission: many views set their own
    ``permission_classes``, which would silently drop a default permission. Every request
    carrying an authenticated session is gated, whatever opened the session (API login or
    Django admin login).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        session = getattr(request, "session", None)
        if (
            session is not None
            and SESSION_KEY in session
            and request.path_info not in CHEMINS_AUTORISES_AVANT_CHANGEMENT
            and getattr(request.user, "doit_changer_mot_de_passe", False)
        ):
            return JsonResponse({"detail": CHANGEMENT_OBLIGATOIRE, "errors": {}}, status=403)
        return self.get_response(request)


class AdresseClientMiddleware:
    """Remplace ``REMOTE_ADDR`` par l'adresse réelle du client (proxy de confiance seulement).

    L'adresse du proxy est conservée dans ``META["ONEA_PROXY_ADDR"]``.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        pair = request.META.get("REMOTE_ADDR")
        reelle = adresse_reelle(request.META)
        if reelle is not None and reelle != pair:
            request.META[PROXY_META] = pair
            request.META["REMOTE_ADDR"] = reelle
        return self.get_response(request)


class PasDeCacheApiMiddleware:
    """Mark every ``/api/`` response that sets no Cache-Control as ``no-store, private``.

    API payloads are per-user and sensitive: no browser or proxy cache may keep them.
    Responses that already choose their policy (file downloads) are left alone.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self.get_response(request)
        if request.path_info.startswith("/api/") and "Cache-Control" not in response:
            response["Cache-Control"] = "no-store, private"
        return response


class _LazyActor(SimpleLazyObject):  # type: ignore[type-arg]
    """Lazy actor that never caches "anonymous".

    A log entry written while the user is being authenticated (first login creates the
    row) would otherwise freeze the actor to None for the rest of the request.
    """

    def _setup(self) -> None:
        super()._setup()  # type: ignore[misc]
        if self._wrapped is None:  # type: ignore[has-type]
            self._wrapped = empty


class LazyActorAuditlogMiddleware(AuditlogMiddleware):  # type: ignore[misc]
    """AuditlogMiddleware that resolves the actor lazily.

    The stock middleware reads ``request.user`` before the view runs, i.e. before DRF
    authenticates the request (``SessionAuthentication401`` decides, not Django's session
    middleware), so API writes could be logged with the wrong actor. DRF's ``Request.user``
    setter writes through to ``HttpRequest.user``; resolving on first use (at the first
    model save) sees the user DRF authenticated.
    """

    def get_extra_data(self, request: HttpRequest) -> dict[str, Any]:
        data: dict[str, Any] = super().get_extra_data(request)
        data["actor"] = _LazyActor(lambda: self._get_actor(request))
        return data

    @staticmethod
    def _get_remote_port(request: HttpRequest) -> int | None:
        # X-Forwarded-Port est fourni par le client : on ne l'enregistre pas.
        return None

    @staticmethod
    def _get_remote_addr(request: HttpRequest) -> str | None:
        # Jamais X-Forwarded-For : REMOTE_ADDR a déjà été fiabilisé par AdresseClientMiddleware.
        return cast("str | None", request.META.get("REMOTE_ADDR"))
