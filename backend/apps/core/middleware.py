from collections.abc import Callable
from typing import Any, cast

from auditlog.middleware import AuditlogMiddleware
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.utils.functional import SimpleLazyObject, empty

from apps.core.reseau import PROXY_META, adresse_reelle


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

    The stock middleware reads ``request.user`` before the view runs, i.e. before
    DRF authenticates a Bearer token, so API writes were logged with actor=None.
    DRF's ``Request.user`` setter writes through to ``HttpRequest.user``; resolving
    on first use (at the first model save) sees the authenticated user.
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
