from typing import Any

from auditlog.middleware import AuditlogMiddleware
from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject, empty


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
